"""Generate embeddings for court_cases using semantic chunking.

Usage (from batch/ directory, virtualenv active):

    python -m jobs.generate_embeddings_cases --limit 100

This job:
- Selects court_cases that do not yet have entries in case_embeddings_cohere.
- Chunks full_text into semantic chunks.
- Generates embeddings via Bedrock Cohere backend and (optionally) Azure OpenAI backend.
- Persists embeddings into case_embeddings_cohere and case_embeddings_openai.
"""

from __future__ import annotations

import argparse
import asyncio
from typing import Optional

import asyncpg
import structlog

from config.settings import get_settings
from pipeline.embeddings import (
    AzureOpenAIEmbeddingBackend,
    BedrockCohereBackend,
    generate_case_embeddings,
)

logger = structlog.get_logger(__name__)


async def _get_db_connection() -> asyncpg.Connection:
    settings = get_settings()
    return await asyncpg.connect(settings.supabase_db_url)


async def _fetch_cases_to_process(
    conn: asyncpg.Connection,
    *,
    limit: Optional[int] = None,
) -> list[tuple[str, str]]:
    """Return list of (id, full_text) for cases lacking cohere embeddings."""

    sql = """
    SELECT id::text, full_text
    FROM court_cases c
    WHERE full_text IS NOT NULL
      AND NOT EXISTS (
          SELECT 1 FROM case_embeddings_cohere e
          WHERE e.case_id = c.id
      )
    ORDER BY decision_date NULLS LAST, created_at
    """
    if limit:
        sql += " LIMIT $1"
        rows = await conn.fetch(sql, limit)
    else:
        rows = await conn.fetch(sql)
    return [(r["id"], r["full_text"]) for r in rows]


async def run(limit: Optional[int] = None) -> None:
    settings = get_settings()

    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.dev.ConsoleRenderer(),
        ]
    )

    log = logger.bind(component="generate_embeddings_cases")

    conn = await _get_db_connection()
    try:
        cases = await _fetch_cases_to_process(conn, limit=limit)
        if not cases:
            log.info("No cases found that require embeddings")
            return

        log.info("Starting embeddings generation", count=len(cases))

        cohere_backend = BedrockCohereBackend(name="bedrock-cohere")

        azure_backend: Optional[AzureOpenAIEmbeddingBackend] = None
        if settings.azure_openai_endpoint and settings.azure_openai_api_key and settings.azure_openai_embed_deployment:
            azure_backend = AzureOpenAIEmbeddingBackend(
                name="azure-openai",
                deployment=settings.azure_openai_embed_deployment,
            )
        else:
            log.info("Azure OpenAI embedding backend not configured; skipping secondary embeddings")

        processed = 0
        for case_id, full_text in cases:
            try:
                await generate_case_embeddings(
                    conn,
                    case_id=case_id,
                    full_text=full_text,
                    cohere_backend=cohere_backend,
                    azure_backend=azure_backend,
                )
                processed += 1
                if processed % 10 == 0:
                    log.info("Progress", processed=processed)
            except Exception as exc:  # pragma: no cover - operational logging
                log.exception("Failed to generate embeddings for case", case_id=case_id, exc=exc)

        log.info("Embedding generation complete", processed=processed)
    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate embeddings for court_cases")
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
