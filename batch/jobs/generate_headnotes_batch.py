"""Generate headnotes for court_cases using Azure OpenAI Batch API.

This script provides a much faster alternative to the sequential headnote generation
by using Azure OpenAI's batch API for GPT-4o-mini.

Usage (from batch/ directory, virtualenv active):

    # Step 1: Export cases to JSONL and upload as batch file
    python -m jobs.generate_headnotes_batch export

    # Step 2: Submit batch job to Azure OpenAI
    python -m jobs.generate_headnotes_batch submit

    # Step 3: Monitor job status
    python -m jobs.generate_headnotes_batch status --batch-id <batch_id>

    # Step 4: Download results and ingest into database
    python -m jobs.generate_headnotes_batch ingest --batch-id <batch_id>

    # All-in-one (export, submit, wait, ingest)
    python -m jobs.generate_headnotes_batch run --wait

Workflow:
1. Export: Query cases without headnotes, fetch few-shot examples, write to JSONL, upload to Azure
2. Submit: Create Azure OpenAI batch job
3. Monitor: Poll job status until complete
4. Ingest: Download output file, parse headnotes, update database
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import asyncpg
import structlog

from config.settings import get_settings

logger = structlog.get_logger(__name__)


# Reuse headnote template from summarizer
HEADNOTE_TEMPLATE = """You are a senior law reporter preparing official-style headnotes for Hong Kong judgments.

Write a concise, structured headnote (max 300 words) for the judgment below using THIS EXACT FORMAT:

Citation: <neutral citation, or "N/A" if missing>
Court: <full court name>
Procedural posture:
- <one bullet>
Issues:
- <issue 1>
- <issue 2>
Holdings:
- <holding 1>
- <holding 2>
Legal principles:
- <principle 1>
- <principle 2>
Disposition:
- <outcome and key orders>
Key citations:
- <[YYYY] HKCFA N / [YYYY] HKCA N or other leading authorities>

Guidelines:
- Focus on points of law, not a narrative of all facts.
- Use neutral, formal style (no advocacy, no speculation).
- If some sections are not clearly stated in the judgment, write "Not clearly stated" or omit that bullet.
- For Key citations, list only the most important cases, not every authority mentioned.

Below are a few example headnotes for similar Hong Kong cases:

{few_shots}

Now draft the headnote for this judgment:

[Judgment text begins]
{judgment_text}
[Judgment text ends]
"""


@dataclass
class BatchJobInfo:
    """Information about an Azure OpenAI batch job."""
    batch_id: str
    status: str
    input_file_id: str
    output_file_id: Optional[str] = None
    error_file_id: Optional[str] = None
    created_at: Optional[str] = None
    completed_at: Optional[str] = None


async def _get_db_connection() -> asyncpg.Connection:
    settings = get_settings()
    return await asyncpg.connect(settings.supabase_db_url)


def _azure_openai_client():
    """Get Azure OpenAI client."""
    settings = get_settings()
    try:
        from openai import AzureOpenAI
    except ImportError:
        raise ImportError(
            "openai package required for Azure OpenAI. Install with: pip install openai"
        )
    
    return AzureOpenAI(
        api_key=settings.azure_openai_api_key,
        api_version=settings.azure_openai_api_version,
        azure_endpoint=settings.azure_openai_endpoint,
    )


async def _fetch_dynamic_few_shots(
    conn: asyncpg.Connection,
    *,
    subject_limit: int = 3,
) -> List[str]:
    """Fetch a small set of candidate headnotes from headnote_corpus."""
    rows = await conn.fetch(
        """
        SELECT headnote_text
        FROM headnote_corpus
        ORDER BY created_at DESC
        LIMIT $1
        """,
        subject_limit,
    )
    return [r["headnote_text"] for r in rows]


def _build_prompt(judgment_text: str, few_shots: List[str]) -> str:
    """Build the prompt with few-shot examples."""
    joined_examples = "\n\n".join(f"[EXAMPLE {i+1}]\n" + ex for i, ex in enumerate(few_shots))
    return HEADNOTE_TEMPLATE.format(few_shots=joined_examples, judgment_text=judgment_text)


def _truncate_judgment(full_text: str, max_chars: int = 150000) -> str:
    """Truncate judgment text to fit within context limits."""
    if len(full_text) <= max_chars:
        return full_text
    return full_text[:max_chars]


async def export_cases_to_jsonl(
    output_file: Path,
    limit: Optional[int] = None,
    max_records_per_file: int = 50000,
) -> int:
    """Export cases without headnotes to JSONL format for Azure OpenAI Batch.

    Args:
        output_file: Base path for output file(s)
        limit: Optional limit on number of cases to process
        max_records_per_file: Maximum records per file (Azure OpenAI limit is 50,000)

    Returns the number of records written.
    """
    log = logger.bind(component="export", output_file=str(output_file))
    
    conn = await _get_db_connection()
    try:
        # Fetch few-shot examples once (reused for all cases)
        few_shots = await _fetch_dynamic_few_shots(conn)
        log.info("Fetched few-shot examples", count=len(few_shots))
        
        # Fetch cases without headnotes
        sql = """
        SELECT id::text, full_text, neutral_citation, case_name
        FROM court_cases c
        WHERE full_text IS NOT NULL
          AND (headnote IS NULL OR headnote = '')
        ORDER BY decision_date NULLS LAST, created_at
        """
        if limit:
            sql += " LIMIT $1"
            rows = await conn.fetch(sql, limit)
        else:
            rows = await conn.fetch(sql)
        
        if not rows:
            log.info("No cases found that require headnotes")
            return 0
        
        log.info("Fetched cases", count=len(rows))
        
        # Get batch deployment name from settings
        settings = get_settings()
        deployment_name = settings.azure_openai_gpt4o_mini_batch_deployment
        
        # Write to JSONL with splitting
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
        
        for row in rows:
            case_id = row["id"]
            full_text = row["full_text"]
            
            # Check if we need to start a new file
            if current_file_records >= max_records_per_file:
                f = open_new_file()
            
            # Truncate judgment text
            truncated_text = _truncate_judgment(full_text, max_chars=150000)
            
            # Build prompt with few-shot examples
            prompt = _build_prompt(truncated_text, few_shots)
            
            # Create Azure OpenAI batch request format
            record = {
                "custom_id": f"case-{case_id}",
                "method": "POST",
                "url": "/chat/completions",
                "body": {
                    "model": deployment_name,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": 600,
                    "temperature": 0.1,
                }
            }
            f.write(json.dumps(record) + "\n")
            record_count += 1
            current_file_records += 1
            
            if (rows.index(row) + 1) % 100 == 0:
                log.info("Progress", processed_cases=rows.index(row) + 1, total_records=record_count)
        
        if current_file:
            current_file.close()
        
        log.info("Exported records to JSONL", record_count=record_count, num_files=file_index)
        return record_count
        
    finally:
        await conn.close()


def upload_batch_file(local_file: Path) -> str:
    """Upload JSONL file to Azure OpenAI for batch processing.

    Returns the file_id.
    """
    log = logger.bind(component="upload", local_file=str(local_file))
    
    client = _azure_openai_client()
    
    log.info("Uploading file to Azure OpenAI")
    with open(local_file, "rb") as f:
        batch_file = client.files.create(
            file=f,
            purpose="batch"
        )
    
    log.info("File uploaded", file_id=batch_file.id)
    return batch_file.id


def submit_batch_job(file_id: str, job_name: Optional[str] = None) -> BatchJobInfo:
    """Submit a batch job to Azure OpenAI.

    Args:
        file_id: The file_id returned from upload_batch_file
        job_name: Optional descriptive name

    Returns BatchJobInfo with batch_id and initial status.
    """
    log = logger.bind(component="submit", file_id=file_id)
    
    client = _azure_openai_client()
    settings = get_settings()
    deployment_name = settings.azure_openai_gpt4o_mini_batch_deployment
    
    log.info("Creating batch job", deployment=deployment_name)
    
    batch = client.batches.create(
        input_file_id=file_id,
        endpoint="/chat/completions",
        completion_window="24h",
        metadata={"description": job_name or "Headnote generation batch"}
    )
    
    log.info("Batch job created", batch_id=batch.id, status=batch.status)
    
    return BatchJobInfo(
        batch_id=batch.id,
        status=batch.status,
        input_file_id=file_id,
        created_at=str(batch.created_at) if batch.created_at else None,
    )


def get_batch_status(batch_id: str) -> BatchJobInfo:
    """Get the status of a batch job.

    Returns BatchJobInfo with current status.
    """
    log = logger.bind(component="status", batch_id=batch_id)
    
    client = _azure_openai_client()
    batch = client.batches.retrieve(batch_id)
    
    log.info(
        "Batch status",
        status=batch.status,
        request_counts=batch.request_counts,
    )
    
    return BatchJobInfo(
        batch_id=batch.id,
        status=batch.status,
        input_file_id=batch.input_file_id,
        output_file_id=batch.output_file_id,
        error_file_id=batch.error_file_id,
        created_at=str(batch.created_at) if batch.created_at else None,
        completed_at=str(batch.completed_at) if batch.completed_at else None,
    )


def download_output_file(batch_id: str, output_path: Path) -> Path:
    """Download the output file from a completed batch job.

    Args:
        batch_id: The batch job ID
        output_path: Local path to save the output

    Returns the path to the downloaded file.
    """
    log = logger.bind(component="download", batch_id=batch_id)
    
    client = _azure_openai_client()
    batch = client.batches.retrieve(batch_id)
    
    if not batch.output_file_id:
        raise ValueError(f"Batch {batch_id} does not have an output file yet")
    
    log.info("Downloading output file", file_id=batch.output_file_id)
    
    # Download file content
    file_response = client.files.content(batch.output_file_id)
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(file_response.read())
    
    log.info("Downloaded output file", path=str(output_path), size_bytes=output_path.stat().st_size)
    return output_path


async def ingest_headnotes(output_file: Path) -> int:
    """Parse output JSONL and update court_cases.headnote column.

    Args:
        output_file: Path to the downloaded output JSONL file

    Returns the number of headnotes ingested.
    """
    log = logger.bind(component="ingest", output_file=str(output_file))
    
    conn = await _get_db_connection()
    try:
        ingested = 0
        skipped = 0
        
        with open(output_file, "r") as f:
            for line_num, line in enumerate(f, start=1):
                if not line.strip():
                    continue
                
                try:
                    record = json.loads(line)
                    custom_id = record["custom_id"]
                    
                    # Extract case_id from custom_id: "case-<uuid>"
                    if not custom_id.startswith("case-"):
                        log.warning("Invalid custom_id format", custom_id=custom_id)
                        skipped += 1
                        continue
                    
                    case_id = custom_id[5:]  # Remove "case-" prefix
                    
                    # Check for errors
                    if record.get("error"):
                        log.warning("Record has error", case_id=case_id, error=record["error"])
                        skipped += 1
                        continue
                    
                    # Extract headnote from response
                    response = record.get("response")
                    if not response:
                        log.warning("Record missing response", case_id=case_id)
                        skipped += 1
                        continue
                    
                    body = response.get("body")
                    if not body:
                        log.warning("Response missing body", case_id=case_id)
                        skipped += 1
                        continue
                    
                    choices = body.get("choices", [])
                    if not choices:
                        log.warning("Response has no choices", case_id=case_id)
                        skipped += 1
                        continue
                    
                    headnote_text = choices[0].get("message", {}).get("content")
                    if not headnote_text:
                        log.warning("No headnote text in response", case_id=case_id)
                        skipped += 1
                        continue
                    
                    # Update database
                    await conn.execute(
                        """
                        UPDATE court_cases
                        SET headnote = $1, updated_at = NOW()
                        WHERE id = $2::uuid
                        """,
                        headnote_text,
                        case_id,
                    )
                    
                    ingested += 1
                    
                    if ingested % 1000 == 0:
                        log.info("Progress", ingested=ingested, skipped=skipped)
                
                except json.JSONDecodeError as e:
                    log.error("Failed to parse JSON", line_num=line_num, error=str(e))
                    skipped += 1
                except Exception as e:
                    log.error("Failed to process record", line_num=line_num, error=str(e))
                    skipped += 1
        
        log.info("Ingestion complete", ingested=ingested, skipped=skipped)
        return ingested
        
    finally:
        await conn.close()


async def wait_for_completion(batch_id: str, poll_interval: int = 60) -> BatchJobInfo:
    """Poll batch job status until completion.

    Args:
        batch_id: The batch job ID
        poll_interval: Seconds between status checks

    Returns the final BatchJobInfo.
    """
    log = logger.bind(component="wait", batch_id=batch_id)
    
    while True:
        info = get_batch_status(batch_id)
        
        if info.status in ["completed", "failed", "cancelled"]:
            log.info("Batch job finished", status=info.status)
            return info
        
        log.info("Batch job still running", status=info.status)
        await asyncio.sleep(poll_interval)


async def run_full_pipeline(
    output_dir: Path,
    limit: Optional[int] = None,
    wait: bool = False,
) -> None:
    """Run the full pipeline: export, submit, optionally wait, and ingest.

    Args:
        output_dir: Directory for storing JSONL files
        limit: Optional limit on number of cases to process
        wait: If True, wait for batch completion before ingesting
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    input_file = output_dir / f"headnotes-batch-{timestamp}.jsonl"
    output_file = output_dir / f"headnotes-output-{timestamp}.jsonl"
    
    log = logger.bind(component="pipeline")
    
    # Step 1: Export
    log.info("Step 1: Exporting cases to JSONL")
    record_count = await export_cases_to_jsonl(input_file, limit=limit)
    if record_count == 0:
        log.info("No cases to process, exiting")
        return
    
    # Step 2: Upload and submit
    log.info("Step 2: Uploading to Azure OpenAI and submitting batch job")
    file_id = upload_batch_file(input_file)
    job_info = submit_batch_job(file_id, job_name=f"Headnotes {timestamp}")
    
    log.info("Batch job submitted", batch_id=job_info.batch_id)
    print(f"\nBatch ID: {job_info.batch_id}")
    print(f"Monitor with: python -m jobs.generate_headnotes_batch status --batch-id {job_info.batch_id}")
    print(f"Ingest with: python -m jobs.generate_headnotes_batch ingest --batch-id {job_info.batch_id}")
    
    if wait:
        # Step 3: Wait for completion
        log.info("Step 3: Waiting for batch completion")
        final_info = await wait_for_completion(job_info.batch_id)
        
        if final_info.status != "completed":
            log.error("Batch job did not complete successfully", status=final_info.status)
            return
        
        # Step 4: Download and ingest
        log.info("Step 4: Downloading output and ingesting headnotes")
        download_output_file(job_info.batch_id, output_file)
        ingested = await ingest_headnotes(output_file)
        
        log.info("Pipeline complete", ingested=ingested)


def main():
    parser = argparse.ArgumentParser(description="Generate headnotes using Azure OpenAI Batch API")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Export command
    export_parser = subparsers.add_parser("export", help="Export cases to JSONL")
    export_parser.add_argument("--output", type=Path, default=Path("output/headnotes"))
    export_parser.add_argument("--limit", type=int, help="Limit number of cases")
    
    # Submit command
    submit_parser = subparsers.add_parser("submit", help="Submit batch job")
    submit_parser.add_argument("--file", type=Path, required=True, help="Input JSONL file")
    submit_parser.add_argument("--name", help="Job name")
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Check batch job status")
    status_parser.add_argument("--batch-id", required=True, help="Batch job ID")
    
    # Ingest command
    ingest_parser = subparsers.add_parser("ingest", help="Download and ingest results")
    ingest_parser.add_argument("--batch-id", required=True, help="Batch job ID")
    ingest_parser.add_argument("--output", type=Path, default=Path("output/headnotes"))
    
    # Run command (all-in-one)
    run_parser = subparsers.add_parser("run", help="Run full pipeline")
    run_parser.add_argument("--output", type=Path, default=Path("output/headnotes"))
    run_parser.add_argument("--limit", type=int, help="Limit number of cases")
    run_parser.add_argument("--wait", action="store_true", help="Wait for completion and auto-ingest")
    
    args = parser.parse_args()
    
    # Configure logging
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.dev.ConsoleRenderer(),
        ]
    )
    
    if args.command == "export":
        args.output.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = args.output / f"headnotes-batch-{timestamp}.jsonl"
        
        asyncio.run(export_cases_to_jsonl(output_file, limit=args.limit))
        
    elif args.command == "submit":
        file_id = upload_batch_file(args.file)
        job_info = submit_batch_job(file_id, job_name=args.name)
        print(f"Batch ID: {job_info.batch_id}")
        print(f"Status: {job_info.status}")
        
    elif args.command == "status":
        job_info = get_batch_status(args.batch_id)
        print(f"Batch ID: {job_info.batch_id}")
        print(f"Status: {job_info.status}")
        print(f"Input File ID: {job_info.input_file_id}")
        if job_info.output_file_id:
            print(f"Output File ID: {job_info.output_file_id}")
        if job_info.error_file_id:
            print(f"Error File ID: {job_info.error_file_id}")
        
    elif args.command == "ingest":
        args.output.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = args.output / f"headnotes-output-{timestamp}.jsonl"
        
        download_output_file(args.batch_id, output_file)
        asyncio.run(ingest_headnotes(output_file))
        
    elif args.command == "run":
        args.output.mkdir(parents=True, exist_ok=True)
        asyncio.run(run_full_pipeline(args.output, limit=args.limit, wait=args.wait))


if __name__ == "__main__":
    main()
