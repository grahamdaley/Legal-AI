"""
Re-parse judges from stored HTML files and update the database.

This job reads HTML files from batch/output/judiciary/html/, re-parses the
judges using the improved parsing logic, and updates ONLY the judges field
in the database. This avoids re-running expensive operations like chunking,
embedding, or summarization.

Usage:
    python -m jobs.reparse_judges
    python -m jobs.reparse_judges --limit 100  # Process only 100 cases
    python -m jobs.reparse_judges --dry-run    # Show what would be updated
"""

import argparse
import asyncio
import json
from pathlib import Path
from typing import Optional

import asyncpg
import structlog

from config.settings import get_settings
from scrapers.judiciary.parsers import parse_judgment_html
from scrapers.utils.html_storage import load_html, get_html_dir

logger = structlog.get_logger(__name__)

# Base output directory
OUTPUT_DIR = Path("output")


async def get_db_connection() -> asyncpg.Connection:
    """Get database connection from settings."""
    settings = get_settings()
    return await asyncpg.connect(settings.supabase_db_url)


def get_all_html_case_ids() -> list[str]:
    """Get all case IDs that have HTML files stored."""
    case_ids = []
    html_dir = get_html_dir("judiciary", OUTPUT_DIR)
    
    if not html_dir.exists():
        return case_ids
    
    for subdir in html_dir.iterdir():
        if subdir.is_dir():
            for html_file in subdir.glob("*.html.gz"):
                case_id = html_file.stem.replace(".html", "")
                case_ids.append(case_id)
    
    return case_ids


async def reparse_judges(
    limit: Optional[int] = None,
    dry_run: bool = False,
    batch_size: int = 100,
) -> dict:
    """
    Re-parse judges from stored HTML files and update the database.
    
    Only updates the judges field - does not touch headnote, embeddings, etc.
    
    Args:
        limit: Maximum number of cases to process (None for all)
        dry_run: If True, don't actually update the database
        batch_size: Number of cases to process per batch
        
    Returns:
        Stats dict with counts
    """
    log = logger.bind(dry_run=dry_run, limit=limit)
    log.info("Starting judges re-parse")
    
    # Get all case IDs with HTML files
    case_ids = get_all_html_case_ids()
    total_count = len(case_ids)
    
    if limit:
        case_ids = case_ids[:limit]
        total_count = len(case_ids)
    
    log.info("Found HTML files", count=total_count)
    
    if total_count == 0:
        log.warning("No HTML files found. Run refetch_html first.")
        return {"total": 0, "updated": 0, "skipped": 0, "failed": 0}
    
    stats = {
        "total": total_count,
        "updated": 0,
        "skipped": 0,
        "failed": 0,
        "no_change": 0,
    }
    
    conn = await get_db_connection()
    
    try:
        processed = 0
        
        for case_id in case_ids:
            try:
                # Load HTML
                html = load_html(case_id, "judiciary", OUTPUT_DIR)
                if not html:
                    stats["skipped"] += 1
                    processed += 1
                    continue
                
                # Get current judges from database
                row = await conn.fetchrow(
                    "SELECT source_url, judges FROM court_cases WHERE id = $1::uuid",
                    case_id,
                )
                
                if not row:
                    log.warning("Case not found in database", case_id=case_id)
                    stats["skipped"] += 1
                    processed += 1
                    continue
                
                source_url = row["source_url"] or ""
                current_judges = row["judges"]
                
                # Parse HTML to extract judges
                parsed = parse_judgment_html(html, source_url)
                new_judges = parsed.judges
                
                # Compare judges
                current_judges_list = []
                if current_judges:
                    if isinstance(current_judges, str):
                        try:
                            current_judges_list = json.loads(current_judges)
                        except json.JSONDecodeError:
                            current_judges_list = []
                    elif isinstance(current_judges, list):
                        current_judges_list = current_judges
                
                if set(new_judges) == set(current_judges_list):
                    stats["no_change"] += 1
                    processed += 1
                    continue
                
                if dry_run:
                    log.info(
                        "Would update judges",
                        case_id=case_id,
                        old_judges=current_judges_list,
                        new_judges=new_judges,
                    )
                    stats["updated"] += 1
                else:
                    # Update only the judges field
                    await conn.execute(
                        """
                        UPDATE court_cases
                        SET judges = $1::jsonb,
                            updated_at = NOW()
                        WHERE id = $2::uuid
                        """,
                        json.dumps(new_judges),
                        case_id,
                    )
                    stats["updated"] += 1
                    
                    if stats["updated"] % 100 == 0:
                        log.info(
                            "Progress",
                            updated=stats["updated"],
                            no_change=stats["no_change"],
                            total=total_count,
                            pct=f"{100*processed/total_count:.1f}%",
                        )
                
            except Exception as e:
                log.error("Failed to process case", case_id=case_id, error=str(e))
                stats["failed"] += 1
            
            processed += 1
        
        log.info("Judges re-parse complete", **stats)
        return stats
        
    finally:
        await conn.close()


async def show_sample_changes(limit: int = 10) -> None:
    """Show sample of what changes would be made."""
    log = logger.bind(limit=limit)
    
    case_ids = get_all_html_case_ids()[:limit]
    
    if not case_ids:
        log.warning("No HTML files found")
        return
    
    conn = await get_db_connection()
    
    try:
        for case_id in case_ids:
            html = load_html(case_id, "judiciary", OUTPUT_DIR)
            if not html:
                continue
            
            row = await conn.fetchrow(
                """
                SELECT case_name, neutral_citation, source_url, judges 
                FROM court_cases WHERE id = $1::uuid
                """,
                case_id,
            )
            
            if not row:
                continue
            
            source_url = row["source_url"] or ""
            current_judges = row["judges"]
            
            parsed = parse_judgment_html(html, source_url)
            new_judges = parsed.judges
            
            current_judges_list = []
            if current_judges:
                if isinstance(current_judges, str):
                    try:
                        current_judges_list = json.loads(current_judges)
                    except json.JSONDecodeError:
                        pass
                elif isinstance(current_judges, list):
                    current_judges_list = current_judges
            
            if set(new_judges) != set(current_judges_list):
                print(f"\n{'='*60}")
                print(f"Case: {row['case_name']}")
                print(f"Citation: {row['neutral_citation']}")
                print(f"Current judges: {current_judges_list}")
                print(f"New judges:     {new_judges}")
    
    finally:
        await conn.close()


def main():
    parser = argparse.ArgumentParser(description="Re-parse judges from HTML files")
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of cases to process",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be updated without making changes",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=0,
        help="Show sample of N changes that would be made",
    )
    
    args = parser.parse_args()
    
    # Configure logging
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.dev.ConsoleRenderer(),
        ],
    )
    
    if args.sample > 0:
        asyncio.run(show_sample_changes(limit=args.sample))
    else:
        asyncio.run(reparse_judges(
            limit=args.limit,
            dry_run=args.dry_run,
        ))


if __name__ == "__main__":
    main()
