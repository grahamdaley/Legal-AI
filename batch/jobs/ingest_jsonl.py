"""
Ingestion job to load scraped JSONL data into Supabase database.

Usage:
    python -m jobs.ingest_jsonl --source judiciary --file output/judiciary/cases_20260103.jsonl
    python -m jobs.ingest_jsonl --source elegislation --file output/elegislation/legislation_20260103.jsonl
    python -m jobs.ingest_jsonl --source judiciary --all  # Process all JSONL files
"""

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import sys

import asyncpg
import structlog

from config.settings import get_settings

logger = structlog.get_logger(__name__)


async def get_db_connection() -> asyncpg.Connection:
    """Get database connection from settings."""
    settings = get_settings()
    return await asyncpg.connect(settings.supabase_db_url)


async def get_court_id(conn: asyncpg.Connection, court_code: str) -> Optional[str]:
    """Look up court ID by code."""
    if not court_code:
        return None
    row = await conn.fetchrow(
        "SELECT id FROM courts WHERE code = $1",
        court_code.upper()
    )
    return str(row["id"]) if row else None


async def ingest_judiciary_record(
    conn: asyncpg.Connection,
    record: dict,
) -> tuple[bool, Optional[str]]:
    """
    Ingest a single judiciary case record.
    
    Returns (success, error_message).
    """
    try:
        case_number = record.get("case_number")
        if not case_number:
            return False, "Missing case_number"
        
        court_code = record.get("court")
        court_id = await get_court_id(conn, court_code) if court_code else None
        
        # Parse decision_date
        decision_date = None
        if record.get("decision_date"):
            try:
                decision_date = datetime.fromisoformat(record["decision_date"]).date()
            except (ValueError, TypeError):
                pass
        
        # Parse scraped_at
        scraped_at = datetime.now(timezone.utc)
        if record.get("scraped_at"):
            try:
                scraped_at = datetime.fromisoformat(record["scraped_at"].replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass
        
        await conn.execute(
            """
            INSERT INTO court_cases (
                neutral_citation, case_number, case_name,
                court_id, court_code, decision_date,
                judges, parties, headnote, catchwords,
                full_text, word_count, language, cited_cases,
                source_url, pdf_url, raw_html, scraped_at
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                $11, $12, $13, $14, $15, $16, $17, $18
            )
            ON CONFLICT (case_number, court_code) DO UPDATE SET
                neutral_citation = EXCLUDED.neutral_citation,
                case_name = EXCLUDED.case_name,
                court_id = EXCLUDED.court_id,
                decision_date = EXCLUDED.decision_date,
                judges = EXCLUDED.judges,
                parties = EXCLUDED.parties,
                headnote = EXCLUDED.headnote,
                catchwords = EXCLUDED.catchwords,
                full_text = EXCLUDED.full_text,
                word_count = EXCLUDED.word_count,
                language = EXCLUDED.language,
                cited_cases = EXCLUDED.cited_cases,
                pdf_url = EXCLUDED.pdf_url,
                raw_html = EXCLUDED.raw_html,
                scraped_at = EXCLUDED.scraped_at,
                updated_at = NOW()
            """,
            record.get("neutral_citation"),
            case_number,
            record.get("case_name"),
            court_id,
            court_code,
            decision_date,
            json.dumps(record.get("judges", [])),
            json.dumps(record.get("parties", {})),
            record.get("headnote"),
            json.dumps(record.get("catchwords", [])),
            record.get("full_text"),
            record.get("word_count", 0),
            record.get("language", "en"),
            json.dumps(record.get("cited_cases", [])),
            record.get("source_url"),
            record.get("pdf_url"),
            record.get("raw_html"),
            scraped_at,
        )
        return True, None
        
    except Exception as e:
        return False, str(e)


async def ingest_elegislation_record(
    conn: asyncpg.Connection,
    record: dict,
) -> tuple[bool, Optional[str]]:
    """
    Ingest a single legislation record with sections.
    
    Returns (success, error_message).
    """
    try:
        chapter_number = record.get("chapter_number")
        if not chapter_number:
            return False, "Missing chapter_number"
        
        # Parse dates
        def parse_date(date_str):
            if not date_str:
                return None
            try:
                return datetime.fromisoformat(date_str).date()
            except (ValueError, TypeError):
                return None
        
        enactment_date = parse_date(record.get("enactment_date"))
        commencement_date = parse_date(record.get("commencement_date"))
        version_date = parse_date(record.get("version_date"))
        
        scraped_at = datetime.now(timezone.utc)
        if record.get("scraped_at"):
            try:
                scraped_at = datetime.fromisoformat(record["scraped_at"].replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass
        
        # Map type to enum
        leg_type = record.get("type", "ordinance")
        if leg_type not in ("ordinance", "regulation", "rule", "order", "notice", "bylaw", "subsidiary"):
            leg_type = "ordinance"
        
        # Map status to enum
        status = record.get("status", "active")
        if status not in ("active", "repealed", "amended", "expired", "not_yet_in_force"):
            status = "active"
        
        # Insert or update legislation
        row = await conn.fetchrow(
            """
            INSERT INTO legislation (
                chapter_number, title_en, title_zh, type, status,
                enactment_date, commencement_date, version_date,
                long_title, preamble, source_url, pdf_url, raw_html, scraped_at
            ) VALUES (
                $1, $2, $3, $4::legislation_type, $5::legislation_status,
                $6, $7, $8, $9, $10, $11, $12, $13, $14
            )
            ON CONFLICT (chapter_number, version_date) DO UPDATE SET
                title_en = EXCLUDED.title_en,
                title_zh = EXCLUDED.title_zh,
                type = EXCLUDED.type,
                status = EXCLUDED.status,
                enactment_date = EXCLUDED.enactment_date,
                commencement_date = EXCLUDED.commencement_date,
                long_title = EXCLUDED.long_title,
                preamble = EXCLUDED.preamble,
                pdf_url = EXCLUDED.pdf_url,
                raw_html = EXCLUDED.raw_html,
                scraped_at = EXCLUDED.scraped_at,
                updated_at = NOW()
            RETURNING id
            """,
            chapter_number,
            record.get("title_en"),
            record.get("title_zh"),
            leg_type,
            status,
            enactment_date,
            commencement_date,
            version_date,
            record.get("long_title"),
            record.get("preamble"),
            record.get("source_url"),
            record.get("pdf_url"),
            record.get("raw_html"),
            scraped_at,
        )
        
        legislation_id = str(row["id"])
        
        # Insert sections
        sections = record.get("sections", [])
        for idx, section in enumerate(sections):
            await conn.execute(
                """
                INSERT INTO legislation_sections (
                    legislation_id, section_number, title, content, sort_order, source_url
                ) VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (legislation_id, section_number) DO UPDATE SET
                    title = EXCLUDED.title,
                    content = EXCLUDED.content,
                    sort_order = EXCLUDED.sort_order,
                    source_url = EXCLUDED.source_url,
                    updated_at = NOW()
                """,
                legislation_id,
                section.get("section_number", str(idx + 1)),
                section.get("title"),
                section.get("content", ""),
                idx,
                section.get("source_url"),
            )
        
        # Insert schedules
        schedules = record.get("schedules", [])
        for idx, schedule in enumerate(schedules):
            await conn.execute(
                """
                INSERT INTO legislation_schedules (
                    legislation_id, schedule_number, title, content, sort_order
                ) VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (legislation_id, schedule_number) DO UPDATE SET
                    title = EXCLUDED.title,
                    content = EXCLUDED.content,
                    sort_order = EXCLUDED.sort_order
                """,
                legislation_id,
                schedule.get("schedule_number", str(idx + 1)),
                schedule.get("title"),
                schedule.get("content"),
                idx,
            )
        
        return True, None
        
    except Exception as e:
        return False, str(e)


async def ingest_file(
    conn: asyncpg.Connection,
    source: str,
    file_path: Path,
) -> dict:
    """
    Ingest a single JSONL file.
    
    Returns stats dict with total, processed, failed counts.
    """
    log = logger.bind(source=source, file=str(file_path))
    
    # Check if already processed
    existing = await conn.fetchrow(
        "SELECT id, status FROM ingestion_jobs WHERE source = $1 AND file_path = $2",
        source,
        str(file_path),
    )
    
    if existing and existing["status"] == "completed":
        log.info("File already ingested, skipping")
        return {"total": 0, "processed": 0, "failed": 0, "skipped": True}
    
    # Create or update ingestion job record
    job_id = None
    if existing:
        job_id = existing["id"]
        await conn.execute(
            "UPDATE ingestion_jobs SET status = 'running', started_at = NOW() WHERE id = $1",
            job_id,
        )
    else:
        row = await conn.fetchrow(
            """
            INSERT INTO ingestion_jobs (source, file_path, status, started_at)
            VALUES ($1, $2, 'running', NOW())
            RETURNING id
            """,
            source,
            str(file_path),
        )
        job_id = row["id"]
    
    # Read and process file
    total = 0
    processed = 0
    failed = 0
    errors = []
    
    ingest_func = ingest_judiciary_record if source == "judiciary" else ingest_elegislation_record
    
    with open(file_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            
            total += 1
            
            try:
                record = json.loads(line)
            except json.JSONDecodeError as e:
                failed += 1
                errors.append(f"Line {line_num}: Invalid JSON - {e}")
                continue
            
            # Skip records with errors from scraping
            if record.get("error"):
                failed += 1
                errors.append(f"Line {line_num}: Scrape error - {record['error']}")
                continue
            
            success, error = await ingest_func(conn, record)
            if success:
                processed += 1
            else:
                failed += 1
                errors.append(f"Line {line_num}: {error}")
            
            if total % 100 == 0:
                log.info("Progress", total=total, processed=processed, failed=failed)
    
    # Update job record
    status = "completed" if failed == 0 else "completed"  # Still mark complete even with some failures
    error_message = "\n".join(errors[:50]) if errors else None  # Keep first 50 errors
    
    await conn.execute(
        """
        UPDATE ingestion_jobs SET
            status = $1,
            records_total = $2,
            records_processed = $3,
            records_failed = $4,
            error_message = $5,
            completed_at = NOW()
        WHERE id = $6
        """,
        status,
        total,
        processed,
        failed,
        error_message,
        job_id,
    )
    
    log.info("Ingestion complete", total=total, processed=processed, failed=failed)
    
    return {"total": total, "processed": processed, "failed": failed, "skipped": False}


async def run_ingestion(
    source: str,
    file_path: Optional[str] = None,
    all_files: bool = False,
) -> None:
    """Main ingestion entry point."""
    log = logger.bind(source=source)
    
    settings = get_settings()
    
    # Determine files to process
    files_to_process = []
    
    if file_path:
        fp = Path(file_path)
        if not fp.exists():
            log.error("File not found", file=file_path)
            sys.exit(1)
        files_to_process.append(fp)
    elif all_files:
        output_dir = Path(settings.output_dir) / source
        if output_dir.exists():
            files_to_process = sorted(output_dir.glob("*.jsonl"))
    
    if not files_to_process:
        log.warning("No files to process")
        return
    
    log.info("Starting ingestion", files=len(files_to_process))
    
    # Connect to database
    conn = await get_db_connection()
    
    try:
        total_stats = {"total": 0, "processed": 0, "failed": 0, "skipped": 0}
        
        for fp in files_to_process:
            stats = await ingest_file(conn, source, fp)
            total_stats["total"] += stats["total"]
            total_stats["processed"] += stats["processed"]
            total_stats["failed"] += stats["failed"]
            if stats.get("skipped"):
                total_stats["skipped"] += 1
        
        log.info("All files processed", **total_stats)
        
    finally:
        await conn.close()


def main():
    parser = argparse.ArgumentParser(description="Ingest JSONL data into Supabase")
    parser.add_argument(
        "--source",
        required=True,
        choices=["judiciary", "elegislation"],
        help="Data source type",
    )
    parser.add_argument(
        "--file",
        help="Path to specific JSONL file to ingest",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        dest="all_files",
        help="Process all JSONL files in the source output directory",
    )
    
    args = parser.parse_args()
    
    if not args.file and not args.all_files:
        parser.error("Either --file or --all must be specified")
    
    # Configure logging
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.dev.ConsoleRenderer(),
        ],
    )
    
    asyncio.run(run_ingestion(
        source=args.source,
        file_path=args.file,
        all_files=args.all_files,
    ))


if __name__ == "__main__":
    main()
