"""
Re-fetch raw HTML for existing court cases and save to files.

This job queries the database for all court cases, fetches the raw HTML from
the source URL, and saves it to files under batch/output/judiciary/html/.

The HTML files are named by case ID (UUID) for easy lookup during re-parsing.

Usage:
    python -m jobs.refetch_html
    python -m jobs.refetch_html --limit 100  # Process only 100 cases
    python -m jobs.refetch_html --dry-run    # Show what would be fetched
    python -m jobs.refetch_html --skip-existing  # Skip cases with existing HTML files
"""

import argparse
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional

import asyncpg
import httpx
import structlog

from config.settings import get_settings
from scrapers.utils.html_storage import (
    save_html,
    load_html,
    get_html_file_path,
    html_file_exists,
)

logger = structlog.get_logger(__name__)


async def get_db_connection() -> asyncpg.Connection:
    """Get database connection from settings."""
    settings = get_settings()
    return await asyncpg.connect(settings.supabase_db_url)


async def fetch_html(
    client: httpx.AsyncClient,
    url: str,
    delay: float = 3.0,
) -> Optional[str]:
    """Fetch HTML from a URL with rate limiting.
    
    Args:
        client: HTTP client
        url: URL to fetch
        delay: Delay after request (rate limiting)
        
    Returns:
        HTML content or None if failed
    """
    try:
        response = await client.get(url, timeout=30.0)
        response.raise_for_status()
        
        # Rate limiting
        await asyncio.sleep(delay)
        
        return response.text
    except Exception as e:
        logger.error("Failed to fetch URL", url=url, error=str(e))
        return None


async def refetch_html(
    limit: Optional[int] = None,
    dry_run: bool = False,
    skip_existing: bool = False,
    delay: float = 3.0,
    batch_size: int = 100,
) -> dict:
    """
    Re-fetch HTML for all cases in the database.
    
    Args:
        limit: Maximum number of cases to process (None for all)
        dry_run: If True, don't actually fetch or save
        skip_existing: If True, skip cases that already have HTML files
        delay: Delay between requests in seconds
        batch_size: Number of cases to fetch per batch
        
    Returns:
        Stats dict with counts
    """
    log = logger.bind(dry_run=dry_run, limit=limit, skip_existing=skip_existing)
    log.info("Starting HTML re-fetch")
    
    # Output directory
    output_dir = Path("output")
    
    conn = await get_db_connection()
    
    try:
        # Get total count
        count_query = "SELECT COUNT(*) FROM court_cases WHERE source_url IS NOT NULL"
        total_count = await conn.fetchval(count_query)
        if limit:
            total_count = min(total_count, limit)
        log.info("Total cases to process", count=total_count)
        
        stats = {
            "total": total_count,
            "fetched": 0,
            "skipped": 0,
            "failed": 0,
            "already_exists": 0,
        }
        
        # Create HTTP client with browser-like headers
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
        
        async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
            offset = 0
            processed = 0
            
            while processed < total_count:
                # Fetch a batch of cases
                query = """
                    SELECT id::text, source_url, case_number, neutral_citation
                    FROM court_cases
                    WHERE source_url IS NOT NULL
                    ORDER BY decision_date DESC NULLS LAST, id
                    LIMIT $1 OFFSET $2
                """
                rows = await conn.fetch(query, batch_size, offset)
                
                if not rows:
                    break
                
                for row in rows:
                    if limit and processed >= limit:
                        break
                    
                    case_id = row["id"]
                    source_url = row["source_url"]
                    
                    # Check if HTML file already exists
                    if skip_existing:
                        if html_file_exists(case_id, "judiciary", output_dir):
                            stats["already_exists"] += 1
                            processed += 1
                            continue
                    
                    if dry_run:
                        log.info(
                            "Would fetch",
                            case_id=case_id,
                            url=source_url,
                            citation=row["neutral_citation"],
                        )
                        stats["fetched"] += 1
                    else:
                        html = await fetch_html(client, source_url, delay=delay)
                        
                        if html:
                            save_html(case_id, html, "judiciary", output_dir)
                            stats["fetched"] += 1
                            
                            if stats["fetched"] % 50 == 0:
                                log.info(
                                    "Progress",
                                    fetched=stats["fetched"],
                                    failed=stats["failed"],
                                    total=total_count,
                                    pct=f"{100*processed/total_count:.1f}%",
                                )
                        else:
                            stats["failed"] += 1
                    
                    processed += 1
                
                offset += batch_size
        
        log.info("HTML re-fetch complete", **stats)
        return stats
        
    finally:
        await conn.close()


def main():
    parser = argparse.ArgumentParser(description="Re-fetch HTML for court cases")
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of cases to process",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be fetched without actually fetching",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip cases that already have HTML files",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=3.0,
        help="Delay between requests in seconds (default: 3.0)",
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
    
    asyncio.run(refetch_html(
        limit=args.limit,
        dry_run=args.dry_run,
        skip_existing=args.skip_existing,
        delay=args.delay,
    ))


if __name__ == "__main__":
    main()
