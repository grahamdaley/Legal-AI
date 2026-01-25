"""Generate embeddings for court_cases using AWS Bedrock Batch API.

This script provides a much faster alternative to the sequential embedding generation
by using AWS Bedrock's batch inference API for Amazon Titan Text Embeddings V2.

Usage (from batch/ directory, virtualenv active):

    # Step 1: Export cases to JSONL and upload to S3
    python -m jobs.generate_embeddings_batch export

    # Step 2: Submit batch job to Bedrock
    python -m jobs.generate_embeddings_batch submit

    # Step 3: Monitor job status
    python -m jobs.generate_embeddings_batch status --job-arn <arn>

    # Step 4: Download results and ingest into database
    python -m jobs.generate_embeddings_batch ingest --job-arn <arn>

    # All-in-one (export, submit, wait, ingest)
    python -m jobs.generate_embeddings_batch run --wait

Workflow:
1. Export: Query cases without embeddings, chunk them, write to JSONL, upload to S3
2. Submit: Create Bedrock batch inference job
3. Monitor: Poll job status until complete
4. Ingest: Download output from S3, parse embeddings, insert into database
"""

from __future__ import annotations

import argparse
import asyncio
import json
import signal
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import asyncpg
import boto3
import structlog

from config.settings import get_settings
from pipeline.chunking import chunk_case_text
from utils.text import truncate_to_token_limit

logger = structlog.get_logger(__name__)

# Graceful shutdown flag
_shutdown_requested = False


def _handle_shutdown(signum, frame):
    """Handle shutdown signals for graceful termination."""
    global _shutdown_requested
    _shutdown_requested = True
    logger.info("Shutdown requested, finishing current operation...")


def is_shutdown_requested() -> bool:
    """Check if shutdown has been requested."""
    return _shutdown_requested


def setup_signal_handlers():
    """Set up signal handlers for graceful shutdown."""
    signal.signal(signal.SIGINT, _handle_shutdown)
    signal.signal(signal.SIGTERM, _handle_shutdown)


@dataclass
class BatchJobInfo:
    """Information about a Bedrock batch job."""
    job_arn: str
    job_name: str
    status: str
    input_s3_uri: str
    output_s3_uri: str
    created_at: Optional[str] = None
    ended_at: Optional[str] = None


async def _get_db_connection() -> asyncpg.Connection:
    settings = get_settings()
    return await asyncpg.connect(settings.supabase_db_url)


async def export_cases_to_jsonl(
    output_file: Path,
    limit: Optional[int] = None,
    max_records_per_file: int = 50000,
) -> int:
    """Export cases without embeddings to JSONL format for Bedrock Batch.

    Args:
        output_file: Base path for output file(s)
        limit: Optional limit on number of cases to process
        max_records_per_file: Maximum records per file (Bedrock limit is 50,000)

    Returns the number of records written.
    """
    log = logger.bind(component="export", output_file=str(output_file))
    
    conn = await _get_db_connection()
    try:
        # Fetch cases without embeddings
        sql = """
        SELECT id::text, full_text
        FROM court_cases c
        WHERE full_text IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM case_embeddings_cohere e
              WHERE e.case_id = c.id
          )
        ORDER BY decision_date NULLS LAST, created_at
        """
        if limit:
            sql += " LIMIT $1"
            rows = await conn.fetch(sql, limit)
        else:
            rows = await conn.fetch(sql)
        
        if not rows:
            log.info("No cases found that require embeddings")
            return 0
        
        log.info("Fetched cases", count=len(rows))
        
        # Generate chunks and write to JSONL with splitting
        record_count = 0
        file_index = 0
        current_file = None
        current_file_records = 0
        
        def open_new_file():
            nonlocal current_file, current_file_records, file_index
            if current_file:
                current_file.close()
            
            if file_index == 0:
                file_path = output_file
            else:
                # Add suffix for additional files
                file_path = output_file.parent / f"{output_file.stem}_part{file_index}{output_file.suffix}"
            
            log.info("Opening new file", file_path=str(file_path), part=file_index)
            current_file = file_path.open("w")
            current_file_records = 0
            file_index += 1
            return current_file
        
        f = open_new_file()
        
        for row_idx, row in enumerate(rows):
            case_id = row["id"]
            full_text = row["full_text"]
            
            chunks = chunk_case_text(case_id, full_text)
            
            for chunk in chunks:
                # Check if we need to start a new file
                if current_file_records >= max_records_per_file:
                    f = open_new_file()
                
                # Truncate chunk text to prevent token limit errors
                truncated_text = truncate_to_token_limit(chunk.text, max_tokens=4000)
                
                record_id = f"case-{case_id}-chunk-{chunk.chunk_index}"
                record = {
                    "recordId": record_id,
                    "modelInput": {
                        "inputText": truncated_text,
                        "dimensions": 1024,
                        "normalize": True,
                    }
                }
                f.write(json.dumps(record) + "\n")
                record_count += 1
                current_file_records += 1
            
            if (row_idx + 1) % 100 == 0:
                log.info("Progress", processed_cases=row_idx + 1, total_records=record_count)
        
        if current_file:
            current_file.close()
        
        log.info("Exported records to JSONL", record_count=record_count, num_files=file_index)
        return record_count
        
    finally:
        await conn.close()


def upload_to_s3(local_file: Path, s3_key: str) -> str:
    """Upload file to S3 input bucket.

    Returns the S3 URI.
    """
    settings = get_settings()
    log = logger.bind(component="upload", local_file=str(local_file), s3_key=s3_key)
    
    s3_client = boto3.client(
        "s3",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )
    
    bucket = settings.bedrock_batch_input_bucket
    
    log.info("Uploading to S3", bucket=bucket)
    s3_client.upload_file(str(local_file), bucket, s3_key)
    
    s3_uri = f"s3://{bucket}/{s3_key}"
    log.info("Upload complete", s3_uri=s3_uri)
    
    return s3_uri


def submit_batch_job(input_s3_uri: str, output_s3_prefix: str) -> BatchJobInfo:
    """Submit a Bedrock batch inference job.

    Returns job information including ARN.
    """
    settings = get_settings()
    log = logger.bind(component="submit")
    
    bedrock_client = boto3.client(
        "bedrock",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )
    
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    job_name = f"legal-ai-embeddings-{timestamp}"
    
    output_bucket = settings.bedrock_batch_output_bucket
    output_s3_uri = f"s3://{output_bucket}/{output_s3_prefix}"
    
    log.info(
        "Submitting batch job",
        job_name=job_name,
        input_uri=input_s3_uri,
        output_uri=output_s3_uri,
    )
    
    response = bedrock_client.create_model_invocation_job(
        roleArn=settings.bedrock_batch_role_arn,
        modelId="amazon.titan-embed-text-v2:0",
        jobName=job_name,
        inputDataConfig={
            "s3InputDataConfig": {
                "s3Uri": input_s3_uri,
            }
        },
        outputDataConfig={
            "s3OutputDataConfig": {
                "s3Uri": output_s3_uri,
            }
        },
    )
    
    job_arn = response["jobArn"]
    log.info("Batch job submitted", job_arn=job_arn)
    
    return BatchJobInfo(
        job_arn=job_arn,
        job_name=job_name,
        status="Submitted",
        input_s3_uri=input_s3_uri,
        output_s3_uri=output_s3_uri,
    )


def get_job_status(job_arn: str) -> BatchJobInfo:
    """Get the status of a batch job."""
    settings = get_settings()
    
    bedrock_client = boto3.client(
        "bedrock",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )
    
    response = bedrock_client.get_model_invocation_job(jobIdentifier=job_arn)
    
    return BatchJobInfo(
        job_arn=response["jobArn"],
        job_name=response["jobName"],
        status=response["status"],
        input_s3_uri=response["inputDataConfig"]["s3InputDataConfig"]["s3Uri"],
        output_s3_uri=response["outputDataConfig"]["s3OutputDataConfig"]["s3Uri"],
        created_at=response.get("submitTime"),
        ended_at=response.get("endTime"),
    )


def wait_for_job_completion(job_arn: str, poll_interval: int = 60) -> BatchJobInfo:
    """Poll job status until it completes (or fails).

    Args:
        job_arn: The job ARN to monitor
        poll_interval: Seconds between status checks

    Returns:
        Final job info
    """
    log = logger.bind(component="monitor", job_arn=job_arn)
    
    while True:
        job_info = get_job_status(job_arn)
        log.info("Job status", status=job_info.status)
        
        if job_info.status in ["Completed", "Failed", "Stopped"]:
            return job_info
        
        time.sleep(poll_interval)


def download_output_files(output_s3_uri: str, local_dir: Path) -> list[Path]:
    """Download all output files from S3.

    Returns list of local file paths.
    """
    settings = get_settings()
    log = logger.bind(component="download", output_uri=output_s3_uri)
    
    # Parse S3 URI
    if not output_s3_uri.startswith("s3://"):
        raise ValueError(f"Invalid S3 URI: {output_s3_uri}")
    
    parts = output_s3_uri[5:].split("/", 1)
    bucket = parts[0]
    prefix = parts[1] if len(parts) > 1 else ""
    
    s3_client = boto3.client(
        "s3",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )
    
    # List all objects with prefix
    response = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
    
    if "Contents" not in response:
        log.warning("No output files found")
        return []
    
    local_dir.mkdir(parents=True, exist_ok=True)
    downloaded_files = []
    
    for obj in response["Contents"]:
        key = obj["Key"]
        if key.endswith(".jsonl.out"):
            local_file = local_dir / Path(key).name
            log.info("Downloading output file", key=key, local_file=str(local_file))
            s3_client.download_file(bucket, key, str(local_file))
            downloaded_files.append(local_file)
    
    log.info("Downloaded output files", count=len(downloaded_files))
    return downloaded_files


async def ingest_embeddings(output_files: list[Path]) -> int:
    """Parse output files and insert embeddings into database.

    Returns the number of embeddings inserted.
    """
    log = logger.bind(component="ingest")
    
    conn = await _get_db_connection()
    try:
        inserted_count = 0
        
        for output_file in output_files:
            log.info("Processing output file", file=str(output_file))
            
            with output_file.open("r") as f:
                for line in f:
                    record = json.loads(line)
                    
                    # Skip records without modelOutput (error records)
                    if "modelOutput" not in record:
                        log.warning("Record missing modelOutput, skipping", record_id=record.get("recordId", "unknown"))
                        continue
                    
                    # Parse recordId: "case-{case_id}-chunk-{chunk_index}"
                    # Note: case_id is a UUID with hyphens, so we need to parse more carefully
                    record_id = record["recordId"]
                    
                    if not record_id.startswith("case-"):
                        log.warning("Invalid recordId format - missing 'case-' prefix", record_id=record_id)
                        continue
                    
                    # Remove "case-" prefix
                    remainder = record_id[5:]
                    
                    # Find "-chunk-" separator
                    chunk_marker = "-chunk-"
                    chunk_pos = remainder.rfind(chunk_marker)
                    if chunk_pos == -1:
                        log.warning("Invalid recordId format - missing '-chunk-' separator", record_id=record_id)
                        continue
                    
                    case_id = remainder[:chunk_pos]
                    chunk_index_str = remainder[chunk_pos + len(chunk_marker):]
                    
                    try:
                        chunk_index = int(chunk_index_str)
                    except ValueError:
                        log.warning("Invalid recordId format - chunk_index not an integer", record_id=record_id)
                        continue
                    
                    # Extract embedding and metadata
                    model_output = record["modelOutput"]
                    embedding = model_output["embedding"]
                    
                    # Get chunk text from input (if available)
                    chunk_text = ""
                    if "modelInput" in record and "inputText" in record["modelInput"]:
                        chunk_text = record["modelInput"]["inputText"]
                    
                    sql = """
                    INSERT INTO case_embeddings_cohere (case_id, chunk_index, chunk_type, chunk_text, embedding)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (case_id, chunk_index)
                    DO UPDATE SET
                        chunk_text = EXCLUDED.chunk_text,
                        embedding = EXCLUDED.embedding,
                        created_at = NOW()
                    """
                    
                    await conn.execute(
                        sql,
                        case_id,
                        chunk_index,
                        "unknown",  # chunk_type not available from batch output
                        chunk_text,  # Use actual chunk text from input
                        json.dumps(embedding),
                    )
                    
                    inserted_count += 1
                    
                    if inserted_count % 1000 == 0:
                        log.info("Ingestion progress", inserted=inserted_count)
        
        log.info("Ingestion complete", total_inserted=inserted_count)
        return inserted_count
        
    finally:
        await conn.close()


async def run_export_step(limit: Optional[int] = None) -> list[str]:
    """Run export step: generate JSONL file(s) and upload to S3.

    Returns list of S3 URIs (may be multiple files if >50k records).
    """
    log = logger.bind(step="export")
    log.info("Starting export step")
    
    # Create output directory
    output_dir = Path("./batch_output")
    output_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base_file = output_dir / f"embeddings-batch-{timestamp}.jsonl"
    
    # Export cases to JSONL (may create multiple files)
    record_count = await export_cases_to_jsonl(base_file, limit=limit)
    
    if record_count == 0:
        log.info("No records to process")
        return []
    
    # Find all created files (base file + any _partN files)
    pattern = f"embeddings-batch-{timestamp}*.jsonl"
    created_files = sorted(output_dir.glob(pattern))
    
    log.info("Created files", count=len(created_files), total_records=record_count)
    
    # Upload all files to S3
    s3_uris = []
    for i, local_file in enumerate(created_files):
        s3_key = f"embeddings/{timestamp}/input_part{i}.jsonl"
        s3_uri = upload_to_s3(local_file, s3_key)
        s3_uris.append(s3_uri)
    
    log.info("Export step complete", files=len(s3_uris), total_records=record_count)
    return s3_uris


def run_submit_step(input_s3_uri: str) -> BatchJobInfo:
    """Run submit step: create Bedrock batch job.

    Returns job info.
    """
    log = logger.bind(step="submit")
    log.info("Starting submit step", input_uri=input_s3_uri)
    
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_prefix = f"embeddings/{timestamp}/output/"
    
    job_info = submit_batch_job(input_s3_uri, output_prefix)
    
    log.info("Submit step complete", job_arn=job_info.job_arn)
    return job_info


async def run_ingest_step(job_arn: str) -> int:
    """Run ingest step: download output and insert into database.

    Returns number of embeddings inserted.
    """
    log = logger.bind(step="ingest")
    log.info("Starting ingest step", job_arn=job_arn)
    
    # Get job info to find output location
    job_info = get_job_status(job_arn)
    
    if job_info.status != "Completed":
        raise ValueError(f"Job is not completed. Status: {job_info.status}")
    
    # Download output files
    output_dir = Path("./batch_output") / "downloads"
    output_files = download_output_files(job_info.output_s3_uri, output_dir)
    
    if not output_files:
        log.warning("No output files to process")
        return 0
    
    # Ingest embeddings
    count = await ingest_embeddings(output_files)
    
    log.info("Ingest step complete", inserted=count)
    return count


async def run_all_steps(limit: Optional[int] = None, wait: bool = False) -> None:
    """Run all steps in sequence: export, submit, optionally wait, and ingest."""
    log = logger.bind(workflow="all")
    
    # Step 1: Export
    s3_uris = await run_export_step(limit=limit)
    if not s3_uris:
        log.info("Nothing to process")
        return
    
    log.info("Submitting batch jobs", num_files=len(s3_uris))
    
    # Step 2: Submit batch job for each file
    job_arns = []
    for i, s3_uri in enumerate(s3_uris):
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_prefix = f"embeddings/{timestamp}/output_part{i}/"
        job_info = submit_batch_job(s3_uri, output_prefix)
        job_arns.append(job_info.job_arn)
        log.info("Batch job submitted", job_num=i+1, job_arn=job_info.job_arn)
        print(f"\nJob {i+1}/{len(s3_uris)} ARN: {job_info.job_arn}")
    
    if wait:
        # Step 3: Wait for all jobs to complete
        log.info("Waiting for all jobs to complete (this may take hours)...", num_jobs=len(job_arns))
        
        all_completed = True
        for job_arn in job_arns:
            job_info = wait_for_job_completion(job_arn)
            if job_info.status != "Completed":
                log.error("Job did not complete successfully", job_arn=job_arn, status=job_info.status)
                all_completed = False
        
        if not all_completed:
            log.error("Some jobs failed")
            return
        
        # Step 4: Ingest all results
        total_count = 0
        for job_arn in job_arns:
            count = await run_ingest_step(job_arn)
            total_count += count
        
        log.info("All steps complete", embeddings_inserted=total_count)
    else:
        log.info("Jobs submitted. Use 'status' command to monitor progress.")
        print(f"\n{len(job_arns)} batch jobs submitted. Save these ARNs:")
        for i, job_arn in enumerate(job_arns):
            print(f"Job {i+1}: {job_arn}")
        print(f"\nTo check status: python -m jobs.generate_embeddings_batch status --job-arn <arn>")
        print(f"To ingest results: python -m jobs.generate_embeddings_batch ingest --job-arn <arn>")


def main() -> None:
    # Set up graceful shutdown handling
    setup_signal_handlers()
    
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.dev.ConsoleRenderer(),
        ]
    )
    
    parser = argparse.ArgumentParser(description="Generate embeddings using Bedrock Batch API")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Export command
    export_parser = subparsers.add_parser("export", help="Export cases to JSONL and upload to S3")
    export_parser.add_argument("--limit", type=int, help="Limit number of cases")
    
    # Submit command
    submit_parser = subparsers.add_parser("submit", help="Submit batch job to Bedrock")
    submit_parser.add_argument("--input-uri", required=True, help="S3 URI of input JSONL file")
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Check job status")
    status_parser.add_argument("--job-arn", required=True, help="Job ARN")
    
    # Ingest command
    ingest_parser = subparsers.add_parser("ingest", help="Download and ingest results")
    ingest_parser.add_argument("--job-arn", required=True, help="Job ARN")
    
    # Run command (all steps)
    run_parser = subparsers.add_parser("run", help="Run all steps")
    run_parser.add_argument("--limit", type=int, help="Limit number of cases")
    run_parser.add_argument("--wait", action="store_true", help="Wait for job completion")
    
    args = parser.parse_args()
    
    if args.command == "export":
        s3_uris = asyncio.run(run_export_step(limit=args.limit))
        if s3_uris:
            print(f"\n{len(s3_uris)} file(s) exported and uploaded:")
            for i, uri in enumerate(s3_uris):
                print(f"  File {i+1}: {uri}")
        else:
            print("\nNo records to export.")
        
    elif args.command == "submit":
        job_info = run_submit_step(args.input_uri)
        print(f"\nJob submitted!")
        print(f"Job ARN: {job_info.job_arn}")
        print(f"Status: {job_info.status}")
        
    elif args.command == "status":
        job_info = get_job_status(args.job_arn)
        print(f"\nJob Status: {job_info.status}")
        print(f"Job Name: {job_info.job_name}")
        print(f"Input: {job_info.input_s3_uri}")
        print(f"Output: {job_info.output_s3_uri}")
        if job_info.created_at:
            print(f"Created: {job_info.created_at}")
        if job_info.ended_at:
            print(f"Ended: {job_info.ended_at}")
        
    elif args.command == "ingest":
        count = asyncio.run(run_ingest_step(args.job_arn))
        print(f"\nIngested {count} embeddings")
        
    elif args.command == "run":
        asyncio.run(run_all_steps(limit=args.limit, wait=args.wait))
        
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
