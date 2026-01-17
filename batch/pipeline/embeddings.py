"""Embedding generation via Amazon Bedrock (Cohere) and Azure OpenAI.

This module provides:
- Backend abstractions for calling embedding models
- Helper functions to generate chunk-level embeddings
- Utility functions to write embeddings into Postgres (via asyncpg)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

import asyncpg
import boto3
from pydantic import BaseModel

from config.settings import get_settings
from . import chunking

try:  # type: ignore[import]
    import openai
except Exception:  # pragma: no cover - optional dependency
    openai = None


def _estimate_tokens(text: str) -> int:
    """Rough token estimation for Bedrock models.
    
    Uses a more conservative heuristic: ~3 characters per token on average.
    Legal text with long words and references tends to use more tokens.
    This is approximate but helps us avoid hitting hard token limits.
    """
    return len(text) // 3


def _truncate_to_token_limit(text: str, max_tokens: int = 4000) -> str:
    """Truncate text to fit within a very conservative token limit.

    We *do not* try to estimate true tokens here because the Titan tokenizer can
    be much more token-dense than typical "~4 chars per token" heuristics for
    legal text. Instead, we assume **1 char ≈ 1 token** and cap the number of
    characters directly. This guarantees we stay well below the 8192-token
    model limit even in worst-case tokenization.
    """

    # Hard cap: 1 character per "token" for safety.
    max_chars = max_tokens
    if len(text) <= max_chars:
        return text

    # Truncate at character boundary, then at word boundary if possible
    truncated = text[:max_chars]
    last_space = truncated.rfind(" ")
    if last_space > max_chars * 0.8:  # Only use space break if reasonably close
        truncated = truncated[:last_space]

    return truncated.rstrip()


@dataclass
class EmbeddingResult:
    """Single embedding for a chunk of text."""

    doc_type: str
    doc_id: str
    chunk_index: int
    chunk_type: str
    text: str
    embedding: List[float]


class EmbeddingBackend(BaseModel):
    """Abstract base class for embedding backends."""

    name: str

    class Config:
        arbitrary_types_allowed = True

    async def embed(self, texts: Sequence[str]) -> List[List[float]]:  # pragma: no cover - interface
        raise NotImplementedError


class BedrockCohereBackend(EmbeddingBackend):
    """Embedding backend using Amazon Bedrock with Amazon Titan Text Embeddings V2.

    Uses synchronous boto3 client under the hood; safe to call from async code
    via the default thread pool.
    """

    model_id: str = "amazon.titan-embed-text-v2:0"
    region_name: Optional[str] = None

    def _client(self):
        settings = get_settings()
        region = self.region_name or settings.aws_region
        return boto3.client("bedrock-runtime", region_name=region)

    async def embed(self, texts: Sequence[str]) -> List[List[float]]:
        import asyncio

        if not texts:
            return []

        client = self._client()

        async def _one(text: str) -> List[float]:
            # Truncate text aggressively before sending to Titan.
            # Titan has an 8192 token limit; we cap at ~4000 "tokens" using a
            # 1 char ≈ 1 token heuristic to stay well under the hard limit.
            safe_text = _truncate_to_token_limit(text, max_tokens=4000)
            body = json.dumps(
                {
                    "inputText": safe_text,
                    "dimensions": 1024,
                    "normalize": True,
                }
            )

            # Run blocking call in thread pool
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: client.invoke_model(
                    modelId=self.model_id,
                    body=body,
                    contentType="application/json",
                    accept="application/json",
                ),
            )
            payload = json.loads(response["body"].read())
            return payload.get("embedding", [])

        return [await _one(t) for t in texts]


class AzureOpenAIEmbeddingBackend(EmbeddingBackend):
    """Embedding backend for Azure OpenAI (text-embedding-3-large).

    This implementation uses the `openai` Python library configured to talk to
    the Azure OpenAI endpoint via environment variables provided in settings.
    """

    deployment: str

    async def embed(self, texts: Sequence[str]) -> List[List[float]]:
        import asyncio

        if not texts:
            return []
        if openai is None:
            raise RuntimeError("openai package is required for Azure OpenAI backend")

        settings = get_settings()

        # Configure openai client for Azure
        # Expect settings.azure_openai_endpoint like "https://<resource>.openai.azure.com"
        openai.base_url = f"{settings.azure_openai_endpoint.rstrip('/')}/openai/deployments/{self.deployment}"
        openai.api_key = settings.azure_openai_api_key
        # Azure OpenAI uses `api_version` query parameter
        openai.default_headers = {"api-key": settings.azure_openai_api_key}

        async def _one(text: str) -> List[float]:
            # Truncate text for Azure as well (assume similar limits ~8k tokens).
            # Use the same conservative 1 char ≈ 1 token heuristic.
            safe_text = _truncate_to_token_limit(text, max_tokens=4000)
            # openai-python 1.x async client
            resp = await openai.embeddings.create(
                input=safe_text,
                model=self.deployment,
                dimensions=1536,  # Reduced from default 3072 for pgvector compatibility
            )
            # In Azure mode, embeddings are under resp.data[0].embedding
            return resp.data[0].embedding  # type: ignore[attr-defined]

        return [await _one(t) for t in texts]


async def generate_case_embeddings(
    conn: asyncpg.Connection,
    case_id: str,
    full_text: str,
    *,
    cohere_backend: BedrockCohereBackend,
    azure_backend: Optional[AzureOpenAIEmbeddingBackend] = None,
) -> List[EmbeddingResult]:
    """Generate embeddings for a single court case and persist them.

    Returns the list of generated EmbeddingResult objects.
    """

    chunks = chunking.chunk_case_text(case_id, full_text)
    if not chunks:
        return []

    texts = [c.text for c in chunks]

    # Generate Cohere/Titan embeddings
    cohere_vectors = await cohere_backend.embed(texts)

    results: List[EmbeddingResult] = []
    for c, vec in zip(chunks, cohere_vectors):
        results.append(
            EmbeddingResult(
                doc_type=c.doc_type,
                doc_id=c.doc_id,
                chunk_index=c.chunk_index,
                chunk_type=c.chunk_type,
                text=c.text,
                embedding=list(vec),
            )
        )

    # Persist to case_embeddings_cohere
    await _insert_case_embeddings(
        conn,
        table="case_embeddings_cohere",
        embeddings=results,
    )

    # Optionally also generate Azure OpenAI embeddings into case_embeddings_openai
    if azure_backend is not None:
        azure_vectors = await azure_backend.embed(texts)
        azure_results: List[EmbeddingResult] = []
        for c, vec in zip(chunks, azure_vectors):
            azure_results.append(
                EmbeddingResult(
                    doc_type=c.doc_type,
                    doc_id=c.doc_id,
                    chunk_index=c.chunk_index,
                    chunk_type=c.chunk_type,
                    text=c.text,
                    embedding=list(vec),
                )
            )
        await _insert_case_embeddings(
            conn,
            table="case_embeddings_openai",
            embeddings=azure_results,
        )

    return results


async def generate_legislation_embeddings(
    conn: asyncpg.Connection,
    legislation_id: str,
    sections: Sequence[Dict[str, Any]],
    *,
    cohere_backend: BedrockCohereBackend,
    azure_backend: Optional[AzureOpenAIEmbeddingBackend] = None,
) -> None:
    """Generate and persist embeddings for all sections of a legislation item.

    Args:
        conn: asyncpg connection
        legislation_id: ID of the legislation row (currently unused but kept for logging).
        sections: iterable of dicts with keys: "id", "content", and optional
            metadata like "section_number" and "title".
    """

    for section in sections:
        section_id = str(section["id"])
        content = section.get("content") or ""
        if not content:
            continue

        section_number = section.get("section_number")
        title = section.get("title")
        path_parts = []
        if section_number:
            path_parts.append(str(section_number))
        if title:
            path_parts.append(str(title))
        section_path = " - ".join(path_parts) if path_parts else None

        chunks = chunking.chunk_legislation_section(section_id, content, section_path=section_path)
        if not chunks:
            continue

        texts = [c.text for c in chunks]

        # Cohere/Titan side
        cohere_vectors = await cohere_backend.embed(texts)
        cohere_embeddings: List[EmbeddingResult] = []
        for c, vec in zip(chunks, cohere_vectors):
            cohere_embeddings.append(
                EmbeddingResult(
                    doc_type=c.doc_type,
                    doc_id=section_id,
                    chunk_index=c.chunk_index,
                    chunk_type=c.chunk_type,
                    text=c.text,
                    embedding=list(vec),
                )
            )

        await _insert_section_embeddings(
            conn,
            table="legislation_embeddings_cohere",
            embeddings=cohere_embeddings,
        )

        # Azure OpenAI side (optional)
        if azure_backend is not None:
            azure_vectors = await azure_backend.embed(texts)
            azure_embeddings: List[EmbeddingResult] = []
            for c, vec in zip(chunks, azure_vectors):
                azure_embeddings.append(
                    EmbeddingResult(
                        doc_type=c.doc_type,
                        doc_id=section_id,
                        chunk_index=c.chunk_index,
                        chunk_type=c.chunk_type,
                        text=c.text,
                        embedding=list(vec),
                    )
                )

            await _insert_section_embeddings(
                conn,
                table="legislation_embeddings_openai",
                embeddings=azure_embeddings,
            )


async def _insert_case_embeddings(
    conn: asyncpg.Connection,
    *,
    table: str,
    embeddings: Sequence[EmbeddingResult],
) -> None:
    if not embeddings:
        return

    rows = [
        (
            e.doc_id,
            e.chunk_index,
            e.chunk_type,
            e.text,
            json.dumps(e.embedding),
        )
        for e in embeddings
    ]

    # Note: using simple INSERT with ON CONFLICT to keep logic straightforward.
    # Assumes `table` has columns (case_id, chunk_index, chunk_type, chunk_text, embedding, created_at).
    sql = f"""
    INSERT INTO {table} (case_id, chunk_index, chunk_type, chunk_text, embedding)
    VALUES ($1, $2, $3, $4, $5)
    ON CONFLICT (case_id, chunk_index)
    DO UPDATE SET
        chunk_type = EXCLUDED.chunk_type,
        chunk_text = EXCLUDED.chunk_text,
        embedding = EXCLUDED.embedding,
        created_at = NOW();
    """

    async with conn.transaction():
        for row in rows:
            await conn.execute(sql, *row)


async def _insert_section_embeddings(
    conn: asyncpg.Connection,
    *,
    table: str,
    embeddings: Sequence[EmbeddingResult],
) -> None:
    """Insert or update embeddings for legislation sections.

    Assumes `table` has columns (section_id, chunk_index, chunk_type, chunk_text, embedding, created_at).
    """

    if not embeddings:
        return

    rows = [
        (
            e.doc_id,  # section_id
            e.chunk_index,
            e.chunk_type,
            e.text,
            json.dumps(e.embedding),
        )
        for e in embeddings
    ]

    sql = f"""
    INSERT INTO {table} (section_id, chunk_index, chunk_type, chunk_text, embedding)
    VALUES ($1, $2, $3, $4, $5)
    ON CONFLICT (section_id, chunk_index)
    DO UPDATE SET
        chunk_type = EXCLUDED.chunk_type,
        chunk_text = EXCLUDED.chunk_text,
        embedding = EXCLUDED.embedding,
        created_at = NOW();
    """

    async with conn.transaction():
        for row in rows:
            await conn.execute(sql, *row)


__all__ = [
    "EmbeddingBackend",
    "BedrockCohereBackend",
    "AzureOpenAIEmbeddingBackend",
    "EmbeddingResult",
    "generate_case_embeddings",
    "generate_legislation_embeddings",
]
