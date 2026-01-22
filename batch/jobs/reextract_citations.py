"""
Re-extract citations from existing cases to populate cited_cases and law_report_citations.

This job reads full_text from court_cases and extracts all citation formats,
updating both cited_cases (for matching) and law_report_citations (for alternate IDs).

Usage:
    python -m jobs.reextract_citations
    python -m jobs.reextract_citations --limit 100  # Process only 100 cases
    python -m jobs.reextract_citations --dry-run    # Show what would be updated
"""

import argparse
import asyncio
import json
from typing import Optional

import asyncpg
import structlog

from config.settings import get_settings
from scrapers.utils.citation_parser import (
    parse_hk_citations,
    parse_hk_law_reports,
    extract_all_citations,
)

logger = structlog.get_logger(__name__)


async def get_db_connection() -> asyncpg.Connection:
    """Get database connection from settings."""
    settings = get_settings()
    return await asyncpg.connect(settings.supabase_db_url)


async def reextract_citations(
    limit: Optional[int] = None,
    dry_run: bool = False,
    batch_size: int = 500,
) -> dict:
    """
    Re-extract citations from all cases using batch processing.
    
    Args:
        limit: Maximum number of cases to process (None for all)
        dry_run: If True, don't actually update the database
        batch_size: Number of cases to fetch per batch
        
    Returns:
        Stats dict with counts
    """
    log = logger.bind(dry_run=dry_run, limit=limit)
    log.info("Starting citation re-extraction")
    
    conn = await get_db_connection()
    
    try:
        # Get total count first
        count_query = "SELECT COUNT(*) FROM court_cases WHERE full_text IS NOT NULL AND full_text != ''"
        total_count = await conn.fetchval(count_query)
        if limit:
            total_count = min(total_count, limit)
        log.info("Total cases to process", count=total_count)
        
        stats = {
            "total": total_count,
            "updated": 0,
            "skipped": 0,
            "errors": 0,
        }
        
        offset = 0
        processed = 0
        
        while processed < total_count:
            # Fetch a batch
            query = """
                SELECT id, neutral_citation, full_text
                FROM court_cases
                WHERE full_text IS NOT NULL AND full_text != ''
                ORDER BY id
                LIMIT $1 OFFSET $2
            """
            rows = await conn.fetch(query, batch_size, offset)
            
            if not rows:
                break
            
            for row in rows:
                if limit and processed >= limit:
                    break
                    
                case_id = row["id"]
                neutral_citation = row["neutral_citation"]
                full_text = row["full_text"]
                
                try:
                    # Extract all HK citations (neutral + law reports)
                    hk_neutral = parse_hk_citations(full_text)
                    hk_law_reports = parse_hk_law_reports(full_text)
                    
                    # Get citation strings
                    cited_cases = [c.full_citation for c in hk_neutral + hk_law_reports]
                    
                    # Remove self-citation
                    if neutral_citation and neutral_citation in cited_cases:
                        cited_cases.remove(neutral_citation)
                    
                    # Extract law report citations for THIS case from its own text
                    # Check first 2000 chars for law report citations (usually in header)
                    law_report_citations = []
                    header_text = full_text[:2000] if len(full_text) > 2000 else full_text
                    header_law_reports = parse_hk_law_reports(header_text)
                    
                    # Only include law report citations that likely refer to THIS case
                    for lr in header_law_reports:
                        if lr.full_citation not in cited_cases:
                            law_report_citations.append(lr.full_citation)
                    
                    if dry_run:
                        if cited_cases or law_report_citations:
                            log.info(
                                "Would update case",
                                case_id=str(case_id),
                                neutral_citation=neutral_citation,
                                cited_count=len(cited_cases),
                                law_report_count=len(law_report_citations),
                            )
                    else:
                        await conn.execute(
                            """
                            UPDATE court_cases
                            SET cited_cases = $1::jsonb,
                                law_report_citations = $2::jsonb,
                                updated_at = NOW()
                            WHERE id = $3
                            """,
                            json.dumps(cited_cases),
                            json.dumps(law_report_citations),
                            case_id,
                        )
                    
                    stats["updated"] += 1
                        
                except Exception as e:
                    log.error("Error processing case", case_id=str(case_id), error=str(e))
                    stats["errors"] += 1
                
                processed += 1
            
            offset += batch_size
            log.info("Progress", processed=processed, total=total_count, pct=f"{100*processed/total_count:.1f}%")
        
        log.info("Citation re-extraction complete", **stats)
        return stats
        
    finally:
        await conn.close()


def main():
    parser = argparse.ArgumentParser(description="Re-extract citations from cases")
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
    
    args = parser.parse_args()
    
    # Configure logging
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.dev.ConsoleRenderer(),
        ],
    )
    
    asyncio.run(reextract_citations(
        limit=args.limit,
        dry_run=args.dry_run,
    ))


if __name__ == "__main__":
    main()
