"""Headnote generation using AI models (Azure GPT-4o/GPT-5-mini or Bedrock Claude).

This module:
- Builds a structured legal prompt for Hong Kong judgments
- Retrieves dynamic few-shot examples from headnote_corpus using embeddings
- Calls Azure OpenAI (Phase 1) or Bedrock Claude (Phase 2) to generate an AI headnote
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


def _azure_openai_client():
    """Get Azure OpenAI client for GPT-4o."""
    settings = get_settings()
    try:
        from openai import AzureOpenAI
    except ImportError:
        raise ImportError(
            "openai package required for Azure OpenAI. Install with: pip install openai"
        )
    
    return AzureOpenAI(
        api_key=settings.azure_openai_api_key,
        api_version=settings.azure_openai_api_version,
        azure_endpoint=settings.azure_openai_endpoint,
    )


async def generate_headnote(case_id: str, *, max_chars: int = 150000) -> Optional[str]:
    """Generate a structured AI headnote for a given court case ID.

    This function:
    - Loads the case from court_cases
    - Fetches a small set of dynamic few-shot headnotes from headnote_corpus
    - Calls Azure OpenAI (Phase 1) or Bedrock Claude (Phase 2) to generate the headnote
    - Returns the headnote text (does not persist it; caller should store it)
    """

    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.dev.ConsoleRenderer(),
        ]
    )

    settings = get_settings()
    log = logger.bind(component="summarizer", case_id=case_id, model=settings.headnote_model)

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

        # Route to appropriate model based on configuration
        if settings.headnote_model.startswith("azure-"):
            # Use Azure OpenAI (Phase 1)
            log.info("Using Azure OpenAI for headnote generation")
            client = _azure_openai_client()
            
            # Map headnote_model to deployment name
            deployment_map = {
                "azure-gpt-4o": settings.azure_openai_gpt4o_deployment,
                "azure-gpt-4o-mini": settings.azure_openai_gpt4o_mini_deployment,
                "azure-gpt-5-mini": settings.azure_openai_gpt5_mini_deployment,
            }
            deployment_name = deployment_map.get(settings.headnote_model)
            if not deployment_name:
                log.error(f"Unknown Azure model: {settings.headnote_model}")
                return None
            
            import asyncio
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: client.chat.completions.create(
                    model=deployment_name,
                    messages=[
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=600,
                    temperature=0.1,
                ),
            )
            return response.choices[0].message.content
        
        else:
            # Use Bedrock (Phase 2 - Claude models)
            log.info("Using Bedrock for headnote generation")
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
                    modelId=settings.headnote_model,
                    body=body,
                    contentType="application/json",
                    accept="application/json",
                ),
            )
            payload = json.loads(response["body"].read())
            return payload["content"][0]["text"]

    finally:
        await conn.close()


__all__ = ["generate_headnote"]
