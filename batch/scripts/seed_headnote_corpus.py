"""Seed the headnote_corpus table with initial examples.

This script is intentionally minimal and uses a small in-code list of examples.
You should review and extend it with real or higher-quality synthetic headnotes
when available.

Usage (from batch/ directory, virtualenv active):

    python -m scripts.seed_headnote_corpus
"""

from __future__ import annotations

import asyncio
from typing import List

import asyncpg
import structlog

from config.settings import get_settings

logger = structlog.get_logger(__name__)


EXAMPLES: List[dict] = [
    {
        "neutral_citation": "[2024] HKCFA 15",
        "court_code": "HKCFA",
        "subject_tags": ["criminal", "joint enterprise"],
        "headnote_text": (
            "Citation: [2024] HKCFA 15\n"
            "Court: Court of Final Appeal\n"
            "Procedural posture:\n"
            "- Appeal against conviction from the Court of First Instance\n\n"
            "Issues:\n"
            "- Whether the trial judge misdirected the jury on the mental element for joint enterprise murder.\n"
            "- Whether foresight of the possibility of the principal offender committing murder is sufficient mens rea after Chan Kam Shing.\n\n"
            "Holdings:\n"
            "- The trial judge's directions, based on the earlier Chan Wing-Siu line, were inconsistent with the principles subsequently affirmed in HKSAR v Chan Kam Shing.\n"
            "- Foresight of the possibility of murder is evidence from which intent may be inferred but is not itself sufficient mens rea.\n\n"
            "Legal principles:\n"
            "- Joint enterprise liability for murder requires proof that the secondary party intended to assist or encourage the principal's commission of the offence, not merely foresaw its possibility.\n"
            "- Appellate courts should carefully review jury directions given before clarification of the law in Chan Kam Shing where foresight was treated as sufficient.\n\n"
            "Disposition:\n"
            "- Appeal allowed; conviction quashed and retrial ordered.\n\n"
            "Key citations:\n"
            "- HKSAR v Chan Kam Shing [2016] 19 HKCFAR 640\n"
            "- R v Jogee [2016] UKSC 8\n"
        ),
        "source": "synthetic",
    },
    {
        "neutral_citation": "[2023] HKCFI 1023",
        "court_code": "HKCFI",
        "subject_tags": ["public law", "judicial review", "freedom of assembly"],
        "headnote_text": (
            "Citation: [2023] HKCFI 1023\n"
            "Court: Court of First Instance\n"
            "Procedural posture:\n"
            "- Application for judicial review of a decision of the Commissioner of Police\n\n"
            "Issues:\n"
            "- Whether refusal to issue a 'no objection' letter for a public procession was a lawful and proportionate restriction on the right of peaceful assembly.\n"
            "- Whether the Commissioner properly considered less intrusive measures and relevant constitutional standards.\n\n"
            "Holdings:\n"
            "- The Commissioner misdirected himself in law by failing to conduct a proper proportionality analysis under the Basic Law and Bill of Rights.\n"
            "- The refusal decision was disproportionate because less restrictive crowd management measures were not adequately considered.\n\n"
            "Legal principles:\n"
            "- Restrictions on peaceful assembly must satisfy the four-step proportionality test: legitimate aim, rational connection, necessity, and fair balance.\n"
            "- Decision-makers must actively consider less intrusive measures before prohibiting assemblies.\n\n"
            "Disposition:\n"
            "- Application allowed; decision quashed and remitted for reconsideration.\n\n"
            "Key citations:\n"
            "- Leung Kwok Hung v HKSAR (2005) 8 HKCFAR 229\n"
        ),
        "source": "synthetic",
    },
]


async def _get_db_connection() -> asyncpg.Connection:
    settings = get_settings()
    return await asyncpg.connect(settings.supabase_db_url)


async def seed_headnotes() -> None:
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.dev.ConsoleRenderer(),
        ]
    )
    log = logger.bind(component="seed_headnote_corpus")

    conn = await _get_db_connection()
    try:
        for ex in EXAMPLES:
            await conn.execute(
                """
                INSERT INTO headnote_corpus (
                    neutral_citation,
                    court_code,
                    subject_tags,
                    headnote_text,
                    source
                ) VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (neutral_citation, court_code) DO NOTHING;
                """,
                ex["neutral_citation"],
                ex["court_code"],
                ex["subject_tags"],
                ex["headnote_text"],
                ex["source"],
            )
        log.info("Seeded headnote_corpus", inserted=len(EXAMPLES))
    finally:
        await conn.close()


def main() -> None:
    asyncio.run(seed_headnotes())


if __name__ == "__main__":  # pragma: no cover
    main()
