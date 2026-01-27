"""Re-parse identifiers from stored HTML files and update the database.

This job reads HTML files from batch/output/judiciary/html/, re-parses
judgment metadata using the improved parsing logic, and updates ONLY
identifier-related fields in the database:

- neutral_citation
- case_number
- court_code / court_id (derived from citation / case number)
- decision_date
- language

It does NOT touch headnotes, embeddings, chunks, or other fields.

Usage:
    python -m jobs.reparse_identifiers
    python -m jobs.reparse_identifiers --limit 100      # Process only 100 cases
    python -m jobs.reparse_identifiers --dry-run        # Show what would be updated
    python -m jobs.reparse_identifiers --sample 10      # Show sample before/after
"""

import argparse
import asyncio
import json
from datetime import date
from pathlib import Path
from typing import Optional

import asyncpg
import structlog

from config.settings import get_settings
from scrapers.judiciary.parsers import parse_judgment_html
from scrapers.utils.html_storage import load_html, get_html_dir
from scrapers.judiciary.config import COURTS as JUDICIARY_COURTS

logger = structlog.get_logger(__name__)

# Base output directory
OUTPUT_DIR = Path("output")


async def get_db_connection() -> asyncpg.Connection:
    """Get database connection from settings."""
    settings = get_settings()
    return await asyncpg.connect(settings.supabase_db_url)


def get_all_html_case_ids() -> list[str]:
    """Get all case IDs that have HTML files stored."""
    case_ids: list[str] = []
    html_dir = get_html_dir("judiciary", OUTPUT_DIR)

    if not html_dir.exists():
        return case_ids

    for subdir in html_dir.iterdir():
        if subdir.is_dir():
            for html_file in subdir.glob("*.html.gz"):
                case_id = html_file.stem.replace(".html", "")
                case_ids.append(case_id)

    return case_ids


async def get_court_id(conn: asyncpg.Connection, court_code: Optional[str]) -> Optional[str]:
    """Look up court ID by code.

    Mirrors logic used in ingest_jsonl/get_court_id.
    """
    if not court_code:
        return None

    row = await conn.fetchrow(
        "SELECT id FROM courts WHERE code = $1",
        court_code.upper(),
    )
    return str(row["id"]) if row else None


def _normalize_court_code(court_code: Optional[str]) -> Optional[str]:
    """Normalize parsed court code to DB court_code.

    Judiciary parser typically returns HKCFA / HKCA / HKCFI / HKDC / HKFC / HKLT.
    Our courts table uses short codes like CFA / CA / CFI / DC / FC / LT (see
    scrapers.judiciary.config.COURTS).
    """
    if not court_code:
        return None

    court_code = court_code.upper()

    # Direct match against configured courts first
    if court_code in JUDICIARY_COURTS:
        return court_code

    # Map HK-prefixed citation code back to our short code
    if court_code.startswith("HK"):
        base = court_code[2:]
        if base in JUDICIARY_COURTS:
            return base

    return court_code


async def reparse_identifiers(
    limit: Optional[int] = None,
    dry_run: bool = False,
    batch_size: int = 100,
) -> dict:
    """Re-parse identifiers from stored HTML files and update the database.

    Args:
        limit: Maximum number of cases to process (None for all)
        dry_run: If True, don't actually update the database
        batch_size: Number of cases to process per batch (currently unused but
            reserved for future batching by DB queries)

    Returns:
        Stats dict with counts
    """
    log = logger.bind(dry_run=dry_run, limit=limit)
    log.info("Starting identifier re-parse")

    # Get all case IDs with HTML files
    case_ids = get_all_html_case_ids()
    total_count = len(case_ids)

    if limit:
        case_ids = case_ids[:limit]
        total_count = len(case_ids)

    log.info("Found HTML files", count=total_count)

    if total_count == 0:
        log.warning("No HTML files found. Run refetch_html first.")
        return {
            "total": 0,
            "updated": 0,
            "skipped": 0,
            "failed": 0,
            "no_change": 0,
        }

    stats = {
        "total": total_count,
        "updated": 0,
        "skipped": 0,
        "failed": 0,
        "no_change": 0,
        "missing_html": 0,
    }

    conn = await get_db_connection()

    try:
        processed = 0

        for case_id in case_ids:
            try:
                # Load HTML from disk
                html = load_html(case_id, "judiciary", OUTPUT_DIR)
                if not html:
                    stats["missing_html"] += 1
                    stats["skipped"] += 1
                    processed += 1
                    continue

                # Fetch current identifiers from DB
                row = await conn.fetchrow(
                    """
                    SELECT
                        id,
                        source_url,
                        neutral_citation,
                        case_number,
                        court_code,
                        decision_date,
                        language
                    FROM court_cases
                    WHERE id = $1::uuid
                    """,
                    case_id,
                )

                if not row:
                    log.warning("Case not found in database", case_id=case_id)
                    stats["skipped"] += 1
                    processed += 1
                    continue

                source_url = row["source_url"] or ""
                current_neutral = row["neutral_citation"]
                current_case_number = row["case_number"]
                current_court_code = row["court_code"]
                current_decision_date: Optional[date] = row["decision_date"]
                current_language = row["language"]

                # Parse HTML using improved parser
                parsed = parse_judgment_html(html, source_url)

                new_neutral = parsed.neutral_citation
                new_case_number = parsed.case_number
                new_court_code = _normalize_court_code(parsed.court)
                new_decision_date = parsed.decision_date
                new_language = parsed.language

                # Decide if anything actually changed
                if (
                    current_neutral == new_neutral
                    and current_case_number == new_case_number
                    and current_court_code == new_court_code
                    and current_decision_date == new_decision_date
                    and current_language == new_language
                ):
                    stats["no_change"] += 1
                    processed += 1
                    continue

                # Compute new court_id if court_code changed
                new_court_id: Optional[str] = None
                if new_court_code and new_court_code != current_court_code:
                    new_court_id = await get_court_id(conn, new_court_code)

                if dry_run:
                    log.info(
                        "Would update identifiers",
                        case_id=case_id,
                        source_url=source_url,
                        neutral_before=current_neutral,
                        neutral_after=new_neutral,
                        case_number_before=current_case_number,
                        case_number_after=new_case_number,
                        court_code_before=current_court_code,
                        court_code_after=new_court_code,
                        decision_date_before=str(current_decision_date)
                        if current_decision_date
                        else None,
                        decision_date_after=str(new_decision_date)
                        if new_decision_date
                        else None,
                        language_before=current_language,
                        language_after=new_language,
                    )
                    stats["updated"] += 1
                else:
                    # Build partial UPDATE with only changed fields
                    # We always set updated_at = NOW()
                    await conn.execute(
                        """
                        UPDATE court_cases
                        SET
                            neutral_citation = $1,
                            case_number = $2,
                            court_code = COALESCE($3, court_code),
                            court_id = COALESCE($4, court_id),
                            decision_date = COALESCE($5, decision_date),
                            language = COALESCE($6, language),
                            updated_at = NOW()
                        WHERE id = $7::uuid
                        """,
                        new_neutral or current_neutral,
                        new_case_number or current_case_number,
                        new_court_code,
                        new_court_id,
                        new_decision_date,
                        new_language,
                        case_id,
                    )
                    stats["updated"] += 1

                    if stats["updated"] % 100 == 0:
                        log.info(
                            "Progress",
                            updated=stats["updated"],
                            no_change=stats["no_change"],
                            skipped=stats["skipped"],
                            total=total_count,
                            pct=f"{100*processed/total_count:.1f}%",
                        )

            except Exception as e:  # noqa: BLE001
                log.error("Failed to process case", case_id=case_id, error=str(e))
                stats["failed"] += 1

            processed += 1

        log.info("Identifier re-parse complete", **stats)
        return stats

    finally:
        await conn.close()


async def show_sample_changes(limit: int = 10) -> None:
    """Show sample of identifier changes that would be made."""
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
                SELECT
                    case_name,
                    neutral_citation,
                    case_number,
                    court_code,
                    decision_date,
                    language,
                    source_url
                FROM court_cases
                WHERE id = $1::uuid
                """,
                case_id,
            )

            if not row:
                continue

            source_url = row["source_url"] or ""
            current_neutral = row["neutral_citation"]
            current_case_number = row["case_number"]
            current_court_code = row["court_code"]
            current_decision_date: Optional[date] = row["decision_date"]
            current_language = row["language"]

            parsed = parse_judgment_html(html, source_url)

            new_neutral = parsed.neutral_citation
            new_case_number = parsed.case_number
            new_court_code = _normalize_court_code(parsed.court)
            new_decision_date = parsed.decision_date
            new_language = parsed.language

            changed = any(
                [
                    current_neutral != new_neutral,
                    current_case_number != new_case_number,
                    current_court_code != new_court_code,
                    current_decision_date != new_decision_date,
                    current_language != new_language,
                ]
            )

            if not changed:
                continue

            print("\n" + "=" * 60)
            print(f"Case: {row['case_name']}")
            print(f"URL: {source_url}")
            print(f"Neutral citation: {current_neutral!r} -> {new_neutral!r}")
            print(f"Case number:      {current_case_number!r} -> {new_case_number!r}")
            print(f"Court code:       {current_court_code!r} -> {new_court_code!r}")
            print(
                f"Decision date:    {current_decision_date!r} -> {new_decision_date!r}",
            )
            print(f"Language:         {current_language!r} -> {new_language!r}")

    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Re-parse identifiers from HTML files and update database",
    )
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
        help="Show sample of N identifier changes and exit",
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
        asyncio.run(
            reparse_identifiers(
                limit=args.limit,
                dry_run=args.dry_run,
            ),
        )


if __name__ == "__main__":
    main()
