#!/usr/bin/env python3
"""
Job runner for Hong Kong Judiciary scraper.

Usage:
    python -m jobs.run_judiciary --courts CFA CA --year-from 2020 --limit 100
    python -m jobs.run_judiciary --resume  # Resume from last state
"""

import argparse
import asyncio
import json
import sys
from datetime import date, datetime
from pathlib import Path

import httpx
import structlog

from config.settings import get_settings
from scrapers.base import ScraperConfig
from scrapers.judiciary import JudiciaryScraper, JudiciaryConfig, COURTS
from scrapers.utils.html_storage import save_html, generate_item_id_from_url
from scrapers.utils.pdf_storage import save_pdf, pdf_file_exists

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
        description="Run the Hong Kong Judiciary scraper"
    )
    parser.add_argument(
        "--courts",
        nargs="+",
        choices=list(COURTS.keys()),
        default=["CFA", "CA", "CFI"],
        help="Courts to scrape (default: CFA CA CFI)",
    )
    parser.add_argument(
        "--year-from",
        type=int,
        default=2000,
        help="Start year (default: 2000)",
    )
    parser.add_argument(
        "--year-to",
        type=int,
        default=datetime.now().year,
        help="End year (default: current year)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of cases to scrape",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from last saved state",
    )
    parser.add_argument(
        "--resume-from-date",
        type=str,
        default=None,
        help="Resume from specific date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./output/judiciary",
        help="Output directory for scraped data",
    )
    parser.add_argument(
        "--state-file",
        type=str,
        default="./state/judiciary_state.json",
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
    return parser.parse_args()


async def run_judiciary_scraper(
    courts: list[str],
    year_from: int,
    year_to: int,
    limit: int | None = None,
    resume_from_date: date | None = None,
    output_dir: str = "./output/judiciary",
    state_file: str = "./state/judiciary_state.json",
    delay: float = 3.0,
    headless: bool = True,
    dry_run: bool = False,
):
    """
    Run the Judiciary scraper with specified parameters.
    
    Args:
        courts: List of court codes to scrape
        year_from: Start year
        year_to: End year
        limit: Maximum cases to scrape
        resume_from_date: Date to resume from
        output_dir: Directory for output files
        state_file: Path to state file
        delay: Delay between requests
        headless: Run browser headless
        dry_run: Only discover URLs
    """
    settings = get_settings()

    # Ensure directories exist
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    Path(state_file).parent.mkdir(parents=True, exist_ok=True)

    # Setup logging to file
    log_file = output_path / f"scrape_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    logger.info(
        "Starting Judiciary scraper",
        courts=courts,
        year_from=year_from,
        year_to=year_to,
        limit=limit,
        resume_from_date=str(resume_from_date) if resume_from_date else None,
        output_dir=output_dir,
        dry_run=dry_run,
    )

    # Configure scraper
    config = ScraperConfig(
        base_url="https://legalref.judiciary.hk",
        request_delay=delay,
        max_concurrent=2,
        headless=headless,
        state_file=state_file,
    )

    judiciary_config = JudiciaryConfig(
        courts=courts,
        start_year=year_from,
        end_year=year_to,
    )

    # Run scraper
    scraped_count = 0
    failed_count = 0
    results_file = output_path / f"cases_{datetime.now().strftime('%Y%m%d')}.jsonl"

    async with JudiciaryScraper(config, judiciary_config) as scraper:
        if dry_run:
            # Just list URLs
            logger.info("Dry run - discovering URLs only")
            urls_file = output_path / "discovered_urls.txt"
            with open(urls_file, "w") as f:
                async for url in scraper.get_index_urls(
                    courts=courts,
                    year_from=year_from,
                    year_to=year_to,
                ):
                    f.write(url + "\n")
                    scraped_count += 1
                    if limit and scraped_count >= limit:
                        break
            logger.info("Discovered URLs", count=scraped_count, file=str(urls_file))
            return

        # HTTP client for downloading PDFs
        pdf_headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/pdf,application/octet-stream;q=0.9,*/*;q=0.8",
        }

        async with httpx.AsyncClient(headers=pdf_headers, follow_redirects=True, timeout=60.0) as pdf_client:
            # Full scrape
            with open(results_file, "a") as f:
                async for case in scraper.run(
                    resume_from_date=resume_from_date,
                    limit=limit,
                ):
                    if case.is_valid():
                        # Use URL-based ID since we don't have DB UUID yet
                        item_id = generate_item_id_from_url(case.source_url)

                        # Save raw HTML to file for future re-parsing
                        if case.raw_html:
                            # Store HTML under the shared storage root: output/judiciary/html
                            save_html(item_id, case.raw_html, "judiciary", Path("output"))

                        # Download and store PDF if available
                        # Store PDFs alongside HTML under output/judiciary/pdf
                        if case.pdf_url and not pdf_file_exists(item_id, "judiciary", Path("output")):
                            try:
                                response = await pdf_client.get(case.pdf_url)
                                if response.status_code < 400 and response.content:
                                    save_pdf(item_id, response.content, "judiciary", Path("output"))
                                else:
                                    logger.warning(
                                        "Failed to download PDF",
                                        url=case.pdf_url,
                                        status=response.status_code,
                                    )
                                # Respect rate limiting between PDF requests
                                await asyncio.sleep(delay)
                            except Exception as e:
                                logger.warning(
                                    "Error downloading PDF",
                                    url=case.pdf_url,
                                    error=str(e),
                                )

                        # Write to JSONL
                        case_data = {
                            "neutral_citation": case.neutral_citation,
                            "case_number": case.case_number,
                            "case_name": case.case_name,
                            "court": case.court,
                            "decision_date": str(case.decision_date) if case.decision_date else None,
                            "judges": case.judges,
                            "parties": case.parties,
                            "headnote": case.headnote,
                            "catchwords": case.catchwords,
                            "full_text": case.full_text,
                            "word_count": case.word_count,
                            "language": case.language,
                            "cited_cases": case.cited_cases,
                            "source_url": case.source_url,
                            "pdf_url": case.pdf_url,
                            "scraped_at": case.scraped_at.isoformat(),
                        }
                        f.write(json.dumps(case_data, ensure_ascii=False) + "\n")
                        scraped_count += 1

                        logger.info(
                            "Scraped case",
                            citation=case.neutral_citation,
                            name=case.case_name[:50] if case.case_name else None,
                            count=scraped_count,
                        )
                    else:
                        failed_count += 1
                        logger.warning(
                            "Failed to scrape case",
                            url=case.source_url,
                            error=case.error,
                        )

    logger.info(
        "Scraping complete",
        scraped=scraped_count,
        failed=failed_count,
        output_file=str(results_file),
    )


def main():
    args = parse_args()

    resume_from_date = None
    if args.resume_from_date:
        resume_from_date = date.fromisoformat(args.resume_from_date)

    asyncio.run(
        run_judiciary_scraper(
            courts=args.courts,
            year_from=args.year_from,
            year_to=args.year_to,
            limit=args.limit,
            resume_from_date=resume_from_date,
            output_dir=args.output_dir,
            state_file=args.state_file,
            delay=args.delay,
            headless=not args.no_headless,
            dry_run=args.dry_run,
        )
    )


if __name__ == "__main__":
    main()
