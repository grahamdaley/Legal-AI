#!/usr/bin/env python3
"""
Job runner for Hong Kong eLegislation scraper.

Usage:
    python -m jobs.run_elegislation --limit 100
    python -m jobs.run_elegislation --chapters 32 32A 571
    python -m jobs.run_elegislation --resume
"""

import argparse
import asyncio
import json
from datetime import date, datetime
from pathlib import Path

import structlog

from config.settings import get_settings
from scrapers.base import ScraperConfig
from scrapers.elegislation import ELegislationScraper, ELegislationConfig

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run the Hong Kong eLegislation scraper"
    )
    parser.add_argument(
        "--chapters",
        nargs="+",
        default=None,
        help="Specific chapters to scrape (e.g., 32 32A 571)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of legislation items to scrape",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from last saved state",
    )
    parser.add_argument(
        "--include-subsidiary",
        action="store_true",
        default=True,
        help="Include subsidiary legislation (default: True)",
    )
    parser.add_argument(
        "--no-subsidiary",
        action="store_true",
        help="Exclude subsidiary legislation",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./output/elegislation",
        help="Output directory for scraped data",
    )
    parser.add_argument(
        "--state-file",
        type=str,
        default="./state/elegislation_state.json",
        help="State file for resume capability",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=3.0,
        help="Delay between requests in seconds (default: 3.0)",
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Run browser in visible mode (for debugging)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only discover URLs, don't scrape content",
    )
    parser.add_argument(
        "--list-chapters",
        action="store_true",
        help="List all available chapters and exit",
    )
    return parser.parse_args()


async def run_elegislation_scraper(
    chapters: list[str] | None = None,
    limit: int | None = None,
    include_subsidiary: bool = True,
    output_dir: str = "./output/elegislation",
    state_file: str = "./state/elegislation_state.json",
    delay: float = 3.0,
    headless: bool = True,
    dry_run: bool = False,
    list_chapters: bool = False,
):
    """
    Run the eLegislation scraper with specified parameters.
    
    Args:
        chapters: Specific chapters to scrape (None = all)
        limit: Maximum items to scrape
        include_subsidiary: Include subsidiary legislation
        output_dir: Directory for output files
        state_file: Path to state file
        delay: Delay between requests
        headless: Run browser headless
        dry_run: Only discover URLs
        list_chapters: Just list chapters and exit
    """
    settings = get_settings()

    # Ensure directories exist
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    Path(state_file).parent.mkdir(parents=True, exist_ok=True)

    logger.info(
        "Starting eLegislation scraper",
        chapters=chapters,
        limit=limit,
        include_subsidiary=include_subsidiary,
        output_dir=output_dir,
        dry_run=dry_run,
    )

    # Configure scraper
    config = ScraperConfig(
        base_url="https://www.elegislation.gov.hk",
        request_delay=delay,
        max_concurrent=2,
        headless=headless,
        state_file=state_file,
    )

    elegislation_config = ELegislationConfig(
        include_subsidiary=include_subsidiary,
    )

    scraped_count = 0
    failed_count = 0

    async with ELegislationScraper(config, elegislation_config) as scraper:
        # List chapters mode
        if list_chapters:
            logger.info("Listing all available chapters")
            all_chapters = await scraper.get_all_chapters()
            print("\nAvailable chapters:")
            for i, ch in enumerate(all_chapters):
                print(f"  Cap. {ch}", end="")
                if (i + 1) % 10 == 0:
                    print()
            print(f"\n\nTotal: {len(all_chapters)} chapters")
            return

        # Dry run mode
        if dry_run:
            logger.info("Dry run - discovering URLs only")
            urls_file = output_path / "discovered_urls.txt"
            with open(urls_file, "w") as f:
                async for url in scraper.get_index_urls():
                    f.write(url + "\n")
                    scraped_count += 1
                    if limit and scraped_count >= limit:
                        break
            logger.info("Discovered URLs", count=scraped_count, file=str(urls_file))
            return

        # Full scrape
        results_file = output_path / f"legislation_{datetime.now().strftime('%Y%m%d')}.jsonl"

        with open(results_file, "a") as f:
            # Scrape specific chapters or all
            if chapters:
                items = scraper.run_for_chapters(chapters, limit=limit)
            else:
                items = scraper.run(limit=limit)

            async for item in items:
                if item.is_valid():
                    # Serialize sections
                    sections_data = [
                        {
                            "section_number": s.section_number,
                            "title": s.title,
                            "content": s.content,
                        }
                        for s in item.sections
                    ]

                    item_data = {
                        "chapter_number": item.chapter_number,
                        "title_en": item.title_en,
                        "title_zh": item.title_zh,
                        "type": item.type,
                        "enactment_date": str(item.enactment_date) if item.enactment_date else None,
                        "commencement_date": str(item.commencement_date) if item.commencement_date else None,
                        "status": item.status,
                        "long_title": item.long_title,
                        "preamble": item.preamble,
                        "sections": sections_data,
                        "schedules": item.schedules,
                        "version_date": str(item.version_date) if item.version_date else None,
                        "source_url": item.source_url,
                        "pdf_url": item.pdf_url,
                        "scraped_at": item.scraped_at.isoformat(),
                    }
                    f.write(json.dumps(item_data, ensure_ascii=False) + "\n")
                    scraped_count += 1

                    logger.info(
                        "Scraped legislation",
                        chapter=item.chapter_number,
                        title=item.title_en[:50] if item.title_en else None,
                        sections=len(item.sections),
                        count=scraped_count,
                    )
                else:
                    failed_count += 1
                    logger.warning(
                        "Failed to scrape legislation",
                        url=item.source_url,
                        error=item.error,
                    )

    logger.info(
        "Scraping complete",
        scraped=scraped_count,
        failed=failed_count,
        output_file=str(results_file) if not dry_run else None,
    )


def main():
    args = parse_args()

    include_subsidiary = args.include_subsidiary and not args.no_subsidiary

    asyncio.run(
        run_elegislation_scraper(
            chapters=args.chapters,
            limit=args.limit,
            include_subsidiary=include_subsidiary,
            output_dir=args.output_dir,
            state_file=args.state_file,
            delay=args.delay,
            headless=not args.no_headless,
            dry_run=args.dry_run,
            list_chapters=args.list_chapters,
        )
    )


if __name__ == "__main__":
    main()
