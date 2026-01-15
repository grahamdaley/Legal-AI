"""Generate embeddings for legislation_sections using semantic chunking.

Usage (from batch/ directory, virtualenv active):

    python -m jobs.generate_embeddings_legislation --limit 100

This job:
- Selects legislation rows and their sections.
- Skips sections that already have embeddings in legislation_embeddings_cohere.
- Generates chunk-level embeddings for each section via Bedrock and Azure OpenAI.
"""

from __future__ import annotations

import argparse
import asyncio
from typing import List, Optional

import asyncpg
import structlog

from config.settings import get_settings
from pipeline.embeddings import (
    AzureOpenAIEmbeddingBackend,
    BedrockCohereBackend,
    generate_legislation_embeddings,
)

logger = structlog.get_logger(__name__)


async def _get_db_connection() -> asyncpg.Connection:
    settings = get_settings()
    return await asyncpg.connect(settings.supabase_db_url)


async def _fetch_legislation_with_sections(
    conn: asyncpg.Connection,
    *,
    limit: Optional[int] = None,
) -> List[asyncpg.Record]:
    """Fetch legislation with associated sections that need embeddings.

    Returns rows with: id, chapter_number, title_en, sections (JSON array).
    """

    sql = """
    SELECT l.id::text AS id,
           l.chapter_number,
           l.title_en,
           (
               SELECT json_agg(row_to_json(s))
               FROM (
                   SELECT s.id, s.section_number, s.title, s.content
                   FROM legislation_sections s
                   WHERE s.legislation_id = l.id
                     AND s.content IS NOT NULL
                     AND NOT EXISTS (
                         SELECT 1 FROM legislation_embeddings_cohere e
                         WHERE e.section_id = s.id
                     )
                   ORDER BY s.section_number
               ) AS s
           ) AS sections
    FROM legislation l
    WHERE EXISTS (
        SELECT 1 FROM legislation_sections s2
        WHERE s2.legislation_id = l.id
          AND s2.content IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM legislation_embeddings_cohere e2
              WHERE e2.section_id = s2.id
          )
    )
    ORDER BY l.chapter_number
    """

    if limit:
        sql += " LIMIT $1"
        rows = await conn.fetch(sql, limit)
    else:
        rows = await conn.fetch(sql)
    return rows


async def run(limit: Optional[int] = None) -> None:
    settings = get_settings()

    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.dev.ConsoleRenderer(),
        ]
    )

    log = logger.bind(component="generate_embeddings_legislation")

    conn = await _get_db_connection()
    try:
        rows = await _fetch_legislation_with_sections(conn, limit=limit)
        if not rows:
            log.info("No legislation sections found that require embeddings")
            return

        log.info("Starting legislation embeddings generation", count=len(rows))

        cohere_backend = BedrockCohereBackend(name="bedrock-cohere")

        azure_backend: Optional[AzureOpenAIEmbeddingBackend] = None
        if settings.azure_openai_endpoint and settings.azure_openai_api_key and settings.azure_openai_embed_deployment:
            azure_backend = AzureOpenAIEmbeddingBackend(
                name="azure-openai",
                deployment=settings.azure_openai_embed_deployment,
            )
        else:
            log.info("Azure OpenAI embedding backend not configured; skipping secondary embeddings")

        processed_legislation = 0
        for row in rows:
            legislation_id = row["id"]
            sections_json = row["sections"] or []
            sections: List[dict] = sections_json

            if not sections:
                continue

            try:
                await generate_legislation_embeddings(
                    conn,
                    legislation_id=str(legislation_id),
                    sections=sections,
                    cohere_backend=cohere_backend,
                    azure_backend=azure_backend,
                )
                processed_legislation += 1
                if processed_legislation % 5 == 0:
                    log.info("Progress", processed=processed_legislation)
            except Exception as exc:  # pragma: no cover - operational logging
                log.exception(
                    "Failed to generate embeddings for legislation",
                    legislation_id=legislation_id,
                    exc=exc,
                )

        log.info("Legislation embedding generation complete", processed=processed_legislation)
    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate embeddings for legislation_sections")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of legislation rows to process",
    )
    args = parser.parse_args()

    asyncio.run(run(limit=args.limit))


if __name__ == "__main__":  # pragma: no cover
    main()
