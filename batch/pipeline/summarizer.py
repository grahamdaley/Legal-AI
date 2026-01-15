"""Headnote generation using Claude 3.7 Sonnet via Amazon Bedrock.

This module:
- Builds a structured legal prompt for Hong Kong judgments
- Retrieves dynamic few-shot examples from headnote_corpus using embeddings
- Calls Claude 3.7 Sonnet through Amazon Bedrock to generate an AI headnote
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Sequence

import asyncpg
import boto3
import structlog

from config.settings import get_settings

logger = structlog.get_logger(__name__)


HEADNOTE_TEMPLATE = """You are a senior law reporter preparing official-style headnotes for Hong Kong judgments.

Write a concise, structured headnote (max 300 words) for the judgment below using THIS EXACT FORMAT:

Citation: <neutral citation, or "N/A" if missing>
Court: <full court name>
Procedural posture:
- <one bullet>
Issues:
- <issue 1>
- <issue 2>
Holdings:
- <holding 1>
- <holding 2>
Legal principles:
- <principle 1>
- <principle 2>
Disposition:
- <outcome and key orders>
Key citations:
- <[YYYY] HKCFA N / [YYYY] HKCA N or other leading authorities>

Guidelines:
- Focus on points of law, not a narrative of all facts.
- Use neutral, formal style (no advocacy, no speculation).
- If some sections are not clearly stated in the judgment, write "Not clearly stated" or omit that bullet.
- For Key citations, list only the most important cases, not every authority mentioned.

Below are a few example headnotes for similar Hong Kong cases:

{few_shots}

Now draft the headnote for this judgment:

[Judgment text begins]
{judgment_text}
[Judgment text ends]
"""


async def _get_db_connection() -> asyncpg.Connection:
    settings = get_settings()
    return await asyncpg.connect(settings.supabase_db_url)


async def _fetch_case_for_headnote(conn: asyncpg.Connection, case_id: str) -> Optional[Dict[str, Any]]:
    row = await conn.fetchrow(
        """
        SELECT id::text, neutral_citation, case_name, full_text, court_code
        FROM court_cases
        WHERE id = $1
        """,
        case_id,
    )
    if not row:
        return None
    return dict(row)


async def _fetch_dynamic_few_shots(
    conn: asyncpg.Connection,
    *,
    subject_limit: int = 3,
) -> List[str]:
    """Fetch a small set of candidate headnotes from headnote_corpus.

    For now this uses a simple random/top-N selection; you can refine it later to
    use vector similarity against the current judgment.
    """

    rows = await conn.fetch(
        """
        SELECT headnote_text
        FROM headnote_corpus
        ORDER BY created_at DESC
        LIMIT $1
        """,
        subject_limit,
    )
    return [r["headnote_text"] for r in rows]


def _build_prompt(judgment_text: str, few_shots: Sequence[str]) -> str:
    joined_examples = "\n\n".join(f"[EXAMPLE {i+1}]\n" + ex for i, ex in enumerate(few_shots))
    return HEADNOTE_TEMPLATE.format(few_shots=joined_examples, judgment_text=judgment_text)


def _bedrock_client():
    settings = get_settings()
    return boto3.client("bedrock-runtime", region_name=settings.aws_region)


async def generate_headnote(case_id: str, *, max_chars: int = 150000) -> Optional[str]:
    """Generate a structured AI headnote for a given court case ID.

    This function:
    - Loads the case from court_cases
    - Fetches a small set of dynamic few-shot headnotes from headnote_corpus
    - Calls Claude 3.7 Sonnet via Bedrock to generate the headnote
    - Returns the headnote text (does not persist it; caller should store it)
    """

    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.dev.ConsoleRenderer(),
        ]
    )

    log = logger.bind(component="summarizer", case_id=case_id)

    conn = await _get_db_connection()
    try:
        case = await _fetch_case_for_headnote(conn, case_id)
        if not case:
            log.warning("Case not found")
            return None

        full_text: str = case.get("full_text") or ""
        if not full_text:
            log.warning("Case has no full_text; skipping")
            return None

        truncated = full_text[:max_chars]
        few_shots = await _fetch_dynamic_few_shots(conn)
        prompt = _build_prompt(truncated, few_shots)

        client = _bedrock_client()

        body = json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 600,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
            }
        )

        import asyncio

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.invoke_model(
                modelId=get_settings().headnote_model,
                body=body,
                contentType="application/json",
                accept="application/json",
            ),
        )
        payload = json.loads(response["body"].read())
        text = payload["content"][0]["text"]
        return text

    finally:
        await conn.close()


__all__ = ["generate_headnote"]
