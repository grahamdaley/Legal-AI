"""Generate AI headnotes for court_cases using Bedrock/Claude 3.7 Sonnet.

Usage (from batch/ directory, virtualenv active):

    python -m jobs.generate_headnotes --limit 100
"""

from __future__ import annotations

import argparse
import asyncio
from typing import Optional

import asyncpg
import structlog

from config.settings import get_settings
from pipeline.summarizer import generate_headnote

logger = structlog.get_logger(__name__)


async def _get_db_connection() -> asyncpg.Connection:
    settings = get_settings()
    return await asyncpg.connect(settings.supabase_db_url)


async def _fetch_cases_needing_headnotes(
    conn: asyncpg.Connection,
    *,
    limit: Optional[int] = None,
) -> list[str]:
    """Return list of case_ids that do not yet have a headnote."""

    sql = """
    SELECT id::text
    FROM court_cases
    WHERE (headnote IS NULL OR headnote = '')
      AND full_text IS NOT NULL
    ORDER BY decision_date NULLS LAST, created_at
    """
    if limit:
        sql += " LIMIT $1"
        rows = await conn.fetch(sql, limit)
    else:
        rows = await conn.fetch(sql)
    return [r["id"] for r in rows]


async def run(limit: Optional[int] = None) -> None:
    settings = get_settings()

    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.dev.ConsoleRenderer(),
        ]
    )

    log = logger.bind(component="generate_headnotes")

    conn = await _get_db_connection()
    try:
        case_ids = await _fetch_cases_needing_headnotes(conn, limit=limit)
        if not case_ids:
            log.info("No cases without headnotes found")
            return

        log.info("Starting headnote generation", count=len(case_ids))

        processed = 0
        for case_id in case_ids:
            try:
                headnote = await generate_headnote(case_id)
                if headnote:
                    await conn.execute(
                        """
                        UPDATE court_cases
                        SET headnote = $1, updated_at = NOW()
                        WHERE id = $2
                        """,
                        headnote,
                        case_id,
                    )
                    processed += 1
                    if processed % 10 == 0:
                        log.info("Progress", processed=processed)
                else:
                    log.warning("No headnote generated", case_id=case_id)
            except Exception as exc:  # pragma: no cover - operational logging
                log.exception("Failed to generate headnote", case_id=case_id, exc=exc)

        log.info("Headnote generation complete", processed=processed)
    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate AI headnotes for court cases")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of cases to process",
    )
    args = parser.parse_args()

    asyncio.run(run(limit=args.limit))


if __name__ == "__main__":  # pragma: no cover
    main()
