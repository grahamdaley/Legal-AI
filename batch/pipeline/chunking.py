"""Semantic chunking utilities for court cases and legislation.

This module groups paragraphs/sections into semantically coherent chunks that are
used for embedding and summarization.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional
import re


PARA_MARKER_RE = re.compile(r"^\s*(\[\d+\]|(\d+)|\\d+\.)\s+")


@dataclass
class Chunk:
    """Represents a semantically coherent text chunk.

    Attributes:
        doc_type: "case" or "legislation".
        doc_id: Primary key of the source row (court_cases.id or legislation_sections.id).
        chunk_index: Zero-based index of the chunk within the document.
        text: The chunk text.
        chunk_type: High-level label such as "facts", "issues", "reasoning", "order",
            "section_body", or "schedule".
        paragraph_numbers: Optional list of paragraph numbers (for judgments).
        section_path: Optional structural path for legislation (e.g. "Part 3 > s.4 > (2)").
    """

    doc_type: str
    doc_id: str
    chunk_index: int
    text: str
    chunk_type: str
    paragraph_numbers: Optional[List[int]] = None
    section_path: Optional[str] = None


def _split_into_paragraphs(text: str) -> List[str]:
    """Split judgment text into paragraphs.

    This is a heuristic splitter that treats blank lines or paragraph markers
    like "[1]", "(1)" or "1." as paragraph boundaries.
    """

    # Normalize newlines
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    paras: List[str] = []
    current: List[str] = []

    def flush_current() -> None:
        nonlocal current
        if current:
            paras.append(" ".join(part.strip() for part in current if part.strip()))
            current = []

    for line in lines:
        if not line.strip():
            # Blank line always ends a paragraph
            flush_current()
            continue

        if PARA_MARKER_RE.match(line) and current:
            # New numbered paragraph; flush previous
            flush_current()

        current.append(line)

    flush_current()
    return [p for p in paras if p]


def _guess_paragraph_number(para: str) -> Optional[int]:
    """Best-effort extraction of a leading paragraph number, if present."""

    m = PARA_MARKER_RE.match(para)
    if not m:
        return None
    raw = m.group(1).strip("[]().")
    try:
        return int(raw)
    except ValueError:
        return None


def _group_paragraphs_into_chunks(
    paragraphs: List[str],
    *,
    max_chars: int = 2000,
    overlap_paras: int = 2,
) -> List[List[str]]:
    """Group paragraphs into chunks by character length with paragraph overlap.

    - Never splits a paragraph.
    - Uses whole-paragraph overlap between successive chunks.
    - Reduced from 6000 to 2000 chars to stay safely under token limits.
      (Token limit is ~8192; 2000 chars ≈ ~1000 tokens, providing safety margin)
    """

    chunks: List[List[str]] = []
    start = 0
    n = len(paragraphs)

    while start < n:
        current: List[str] = []
        length = 0
        i = start
        while i < n and length + len(paragraphs[i]) <= max_chars:
            current.append(paragraphs[i])
            length += len(paragraphs[i])
            i += 1
        if not current:
            # Fallback: ensure progress even if a single paragraph is huge
            current.append(paragraphs[start])
            i = start + 1
        chunks.append(current)
        if i >= n:
            break
        # Overlap by whole paragraphs
        start = max(i - overlap_paras, 0) if i - overlap_paras > start else i

    return chunks


def chunk_case_text(case_id: str, full_text: str) -> List[Chunk]:
    """Chunk a court judgment into semantically coherent blocks.

    This is heuristic and may be refined over time; for now we:
    - Split into paragraphs.
    - Group paragraphs by character budget (2000 chars max).
    - Attempt to infer a rough chunk_type based on position.
    """

    paragraphs = _split_into_paragraphs(full_text)
    para_chunks = _group_paragraphs_into_chunks(paragraphs, max_chars=2000)
    chunks: List[Chunk] = []

    total = len(para_chunks)
    for idx, para_group in enumerate(para_chunks):
        text = "\n".join(para_group)
        # Collect paragraph numbers where we can infer them
        para_nums = [n for n in (_guess_paragraph_number(p) for p in para_group) if n is not None]

        # Very simple heuristic for chunk_type based on position
        if idx == 0:
            ctype = "facts"
        elif idx == total - 1:
            ctype = "order"
        else:
            ctype = "reasoning"

        chunks.append(
            Chunk(
                doc_type="case",
                doc_id=case_id,
                chunk_index=idx,
                text=text,
                chunk_type=ctype,
                paragraph_numbers=para_nums or None,
                section_path=None,
            )
        )

    return chunks


def chunk_legislation_section(
    section_id: str,
    content: str,
    *,
    section_path: Optional[str] = None,
) -> List[Chunk]:
    """Chunk a legislation section.

    For now, each section is a single chunk unless it is extremely long,
    in which case we split on blank lines.
    """

    text = content.strip()
    if not text:
        return []

    if len(text) <= 2000:
        return [
            Chunk(
                doc_type="legislation",
                doc_id=section_id,
                chunk_index=0,
                text=text,
                chunk_type="section_body",
                paragraph_numbers=None,
                section_path=section_path,
            )
        ]

    # For long sections, split on blank lines but keep section_path
    paras = [p for p in text.split("\n\n") if p.strip()]
    para_chunks = _group_paragraphs_into_chunks(paras, max_chars=2000, overlap_paras=1)

    chunks: List[Chunk] = []
    for idx, group in enumerate(para_chunks):
        chunks.append(
            Chunk(
                doc_type="legislation",
                doc_id=section_id,
                chunk_index=idx,
                text="\n\n".join(group),
                chunk_type="section_body",
                paragraph_numbers=None,
                section_path=section_path,
            )
        )

    return chunks


__all__ = ["Chunk", "chunk_case_text", "chunk_legislation_section"]
