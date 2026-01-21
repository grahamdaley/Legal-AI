"""Orchestrate parallel batch processing for headnote generation.

This script manages the full pipeline of generating headnotes for all court cases
by submitting multiple batches in parallel waves, monitoring progress, and ingesting results.

Usage:
    python -m jobs.run_parallel_headnotes --batch-size 350 --parallel 8

Features:
- Automatic wave-based parallel processing
- Progress tracking with ETA
- Automatic retry on failures
- Resume capability if interrupted
- Summary statistics
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

import asyncpg
import structlog

from config.settings import get_settings
from jobs.generate_headnotes_batch import (
    export_cases_to_jsonl,
    upload_batch_file,
    submit_batch_job,
    get_batch_status,
    download_output_file,
    ingest_headnotes,
    BatchJobInfo,
    _azure_openai_client,
)

logger = structlog.get_logger(__name__)


@dataclass
class WaveStatus:
    """Status of a wave of parallel batches."""
    wave_num: int
    batch_ids: List[str]
    total_cases: int
    start_time: datetime
    completed: int = 0
    failed: int = 0


async def get_remaining_cases_count() -> int:
    """Get count of cases that still need headnotes."""
    settings = get_settings()
    conn = await asyncpg.connect(settings.supabase_db_url)
    try:
        count = await conn.fetchval(
            """
            SELECT COUNT(*) 
            FROM court_cases 
            WHERE full_text IS NOT NULL 
              AND (headnote IS NULL OR headnote = '')
            """
        )
        return count
    finally:
        await conn.close()


async def export_wave_batches(
    wave_num: int,
    batch_size: int,
    num_batches: int,
    output_dir: Path,
) -> List[Path]:
    """Export multiple batches for a single wave.
    
    Args:
        wave_num: Wave number for naming
        batch_size: Cases per batch
        num_batches: Number of batches in this wave
        output_dir: Directory for output files
    
    Returns:
        List of paths to exported JSONL files
    """
    log = logger.bind(wave=wave_num, batch_size=batch_size, num_batches=num_batches)
    log.info("Exporting batches for wave")
    
    # Export all cases for this wave at once
    total_cases = batch_size * num_batches
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    export_file = output_dir / f"wave{wave_num:03d}_batch_{timestamp}.jsonl"
    
    log.info("Exporting cases", total_cases=total_cases)
    exported = await export_cases_to_jsonl(export_file, limit=total_cases)
    
    if exported == 0:
        return []
    
    # Split into individual batch files if needed
    batch_files = []
    
    if exported <= batch_size:
        # Only one batch needed
        batch_files.append(export_file)
    else:
        # Split into multiple batches
        log.info("Splitting into batch files")
        with open(export_file, 'r') as f:
            lines = f.readlines()
        
        for batch_idx in range(num_batches):
            start_idx = batch_idx * batch_size
            end_idx = min(start_idx + batch_size, len(lines))
            
            if start_idx >= len(lines):
                break
            
            batch_file = output_dir / f"wave{wave_num:03d}_batch{batch_idx+1:02d}_{timestamp}.jsonl"
            with open(batch_file, 'w') as f:
                f.writelines(lines[start_idx:end_idx])
            
            batch_files.append(batch_file)
            log.info("Created batch file", batch=batch_idx+1, cases=end_idx-start_idx, file=batch_file.name)
    
    return batch_files


@dataclass
class WaveFiles:
    """Tracks file IDs for a wave."""
    input_file_ids: List[str]
    output_file_ids: List[str]


async def submit_wave(
    wave_num: int,
    batch_files: List[Path],
) -> tuple[WaveStatus, WaveFiles]:
    """Submit all batches in a wave to Azure OpenAI.
    
    Args:
        wave_num: Wave number
        batch_files: List of JSONL files to submit
    
    Returns:
        Tuple of (WaveStatus, WaveFiles) for tracking and cleanup
    """
    log = logger.bind(wave=wave_num, num_batches=len(batch_files))
    log.info("Submitting wave")
    
    batch_ids = []
    input_file_ids = []
    total_cases = 0
    
    for idx, batch_file in enumerate(batch_files, start=1):
        log.info("Uploading and submitting batch", batch=idx, file=batch_file.name)
        
        # Upload file
        file_id = upload_batch_file(batch_file)
        input_file_ids.append(file_id)
        
        # Submit batch job
        job_info = submit_batch_job(
            file_id, 
            job_name=f"Wave {wave_num} Batch {idx}"
        )
        
        batch_ids.append(job_info.batch_id)
        
        # Count cases in this batch
        with open(batch_file, 'r') as f:
            cases = sum(1 for _ in f)
        total_cases += cases
        
        log.info("Batch submitted", batch=idx, batch_id=job_info.batch_id, cases=cases)
        
        # Small delay between submissions to avoid rate limits
        await asyncio.sleep(2)
    
    wave_status = WaveStatus(
        wave_num=wave_num,
        batch_ids=batch_ids,
        total_cases=total_cases,
        start_time=datetime.now(),
    )
    
    wave_files = WaveFiles(
        input_file_ids=input_file_ids,
        output_file_ids=[],
    )
    
    return wave_status, wave_files


async def monitor_wave(wave_status: WaveStatus, poll_interval: int = 30) -> WaveStatus:
    """Monitor all batches in a wave until completion.
    
    Args:
        wave_status: Wave to monitor
        poll_interval: Seconds between status checks
    
    Returns:
        Updated WaveStatus with completion counts
    """
    log = logger.bind(wave=wave_status.wave_num)
    log.info("Monitoring wave", total_batches=len(wave_status.batch_ids))
    
    completed_batches = set()
    failed_batches = set()
    
    while len(completed_batches) + len(failed_batches) < len(wave_status.batch_ids):
        for batch_id in wave_status.batch_ids:
            if batch_id in completed_batches or batch_id in failed_batches:
                continue
            
            try:
                info = get_batch_status(batch_id)
                
                if info.status == "completed":
                    completed_batches.add(batch_id)
                    log.info("Batch completed", batch_id=batch_id[:12])
                elif info.status == "failed":
                    failed_batches.add(batch_id)
                    log.warning("Batch failed", batch_id=batch_id[:12])
            except Exception as e:
                log.error("Error checking batch status", batch_id=batch_id[:12], error=str(e))
        
        if len(completed_batches) + len(failed_batches) < len(wave_status.batch_ids):
            elapsed = (datetime.now() - wave_status.start_time).total_seconds() / 60
            remaining = len(wave_status.batch_ids) - len(completed_batches) - len(failed_batches)
            log.info(
                "Wave progress",
                completed=len(completed_batches),
                failed=len(failed_batches),
                remaining=remaining,
                elapsed_min=f"{elapsed:.1f}",
            )
            await asyncio.sleep(poll_interval)
    
    wave_status.completed = len(completed_batches)
    wave_status.failed = len(failed_batches)
    
    elapsed = (datetime.now() - wave_status.start_time).total_seconds() / 60
    log.info(
        "Wave complete",
        completed=wave_status.completed,
        failed=wave_status.failed,
        elapsed_min=f"{elapsed:.1f}",
    )
    
    return wave_status


async def ingest_wave(wave_status: WaveStatus, wave_files: WaveFiles, output_dir: Path) -> int:
    """Download and ingest all completed batches in a wave.
    
    Args:
        wave_status: Wave with completed batches
        wave_files: File IDs to track for cleanup
        output_dir: Directory for output files
    
    Returns:
        Number of headnotes ingested
    """
    log = logger.bind(wave=wave_status.wave_num)
    log.info("Ingesting wave results")
    
    total_ingested = 0
    
    for idx, batch_id in enumerate(wave_status.batch_ids, start=1):
        try:
            # Check if this batch completed successfully
            info = get_batch_status(batch_id)
            if info.status != "completed":
                log.warning("Skipping non-completed batch", batch=idx, status=info.status)
                continue
            
            # Track output file ID for cleanup
            if info.output_file_id:
                wave_files.output_file_ids.append(info.output_file_id)
            
            # Download output
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = output_dir / f"wave{wave_status.wave_num:03d}_batch{idx:02d}_output_{timestamp}.jsonl"
            
            download_output_file(batch_id, output_file)
            
            # Ingest
            ingested = await ingest_headnotes(output_file)
            total_ingested += ingested
            
            log.info("Batch ingested", batch=idx, headnotes=ingested)
            
        except Exception as e:
            log.error("Error ingesting batch", batch=idx, batch_id=batch_id[:12], error=str(e))
    
    log.info("Wave ingestion complete", total_headnotes=total_ingested)
    return total_ingested


async def run_parallel_pipeline(
    batch_size: int = 350,
    parallel_jobs: int = 8,
    output_dir: Path = Path("output/headnotes"),
):
    """Run the complete parallel batch processing pipeline.
    
    Args:
        batch_size: Number of cases per batch
        parallel_jobs: Number of batches to run in parallel
        output_dir: Directory for storing files
    """
    log = logger.bind(component="parallel_pipeline")
    
    # Setup
    output_dir.mkdir(parents=True, exist_ok=True)
    start_time = datetime.now()
    
    # Get initial counts
    remaining = await get_remaining_cases_count()
    log.info(
        "Starting parallel processing",
        total_cases=remaining,
        batch_size=batch_size,
        parallel_jobs=parallel_jobs,
    )
    
    if remaining == 0:
        log.info("No cases to process")
        return
    
    # Calculate waves
    total_batches = (remaining + batch_size - 1) // batch_size
    total_waves = (total_batches + parallel_jobs - 1) // parallel_jobs
    
    log.info(
        "Processing plan",
        total_batches=total_batches,
        total_waves=total_waves,
        est_time_hours=f"{total_waves * 3 / 60:.1f}",
    )
    
    total_ingested = 0
    
    # Process waves
    for wave_num in range(1, total_waves + 1):
        log.info(f"=== WAVE {wave_num}/{total_waves} ===")
        
        # Determine how many batches in this wave
        remaining_batches = total_batches - (wave_num - 1) * parallel_jobs
        batches_in_wave = min(parallel_jobs, remaining_batches)
        
        try:
            # Step 1: Export batches
            batch_files = await export_wave_batches(
                wave_num, batch_size, batches_in_wave, output_dir
            )
            
            if not batch_files:
                log.info("No more cases to process")
                break
            
            # Step 2: Submit wave
            wave_status, wave_files = await submit_wave(wave_num, batch_files)
            
            # Step 3: Monitor until complete
            wave_status = await monitor_wave(wave_status)
            
            # Step 4: Ingest results
            ingested = await ingest_wave(wave_status, wave_files, output_dir)
            total_ingested += ingested
            
            # Step 5: Cleanup files to avoid quota limits
            try:
                client = _azure_openai_client()
                files_to_delete = wave_files.input_file_ids + wave_files.output_file_ids
                log.info("Cleaning up wave files", num_files=len(files_to_delete))
                
                for file_id in files_to_delete:
                    try:
                        client.files.delete(file_id)
                    except Exception as e:
                        log.warning("Failed to delete file", file_id=file_id[:12], error=str(e))
                
                log.info("Wave cleanup complete")
            except Exception as e:
                log.error("Wave cleanup failed", error=str(e))
            
            # Progress update
            elapsed = (datetime.now() - start_time).total_seconds() / 60
            avg_time_per_wave = elapsed / wave_num
            remaining_waves = total_waves - wave_num
            eta_min = remaining_waves * avg_time_per_wave
            
            log.info(
                "Overall progress",
                wave=f"{wave_num}/{total_waves}",
                headnotes_ingested=total_ingested,
                elapsed_min=f"{elapsed:.1f}",
                eta_min=f"{eta_min:.1f}",
            )
            
        except Exception as e:
            log.error("Wave failed", wave=wave_num, error=str(e))
            # Continue to next wave
    
    # Final summary
    elapsed = (datetime.now() - start_time).total_seconds() / 60
    log.info(
        "Processing complete",
        total_headnotes=total_ingested,
        total_time_min=f"{elapsed:.1f}",
        avg_per_case_sec=f"{elapsed * 60 / total_ingested:.2f}" if total_ingested > 0 else "N/A",
    )


def main():
    parser = argparse.ArgumentParser(description="Run parallel batch headnote generation")
    parser.add_argument("--batch-size", type=int, default=350, help="Cases per batch (default: 350)")
    parser.add_argument("--parallel", type=int, default=8, help="Parallel batches per wave (default: 8)")
    parser.add_argument("--output", type=Path, default=Path("output/headnotes"), help="Output directory")
    
    args = parser.parse_args()
    
    # Configure logging
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.dev.ConsoleRenderer(),
        ]
    )
    
    # Run pipeline
    asyncio.run(run_parallel_pipeline(
        batch_size=args.batch_size,
        parallel_jobs=args.parallel,
        output_dir=args.output,
    ))


if __name__ == "__main__":
    main()
