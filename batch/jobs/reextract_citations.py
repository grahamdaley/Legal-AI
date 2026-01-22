"""
Re-extract citations from existing cases to populate cited_cases and law_report_citations.

This job reads full_text and headnote from court_cases and extracts all citation formats,
updating both cited_cases (for matching) and law_report_citations (for alternate IDs).

Citations from headnote are validated against full_text to prevent hallucinations:
- A headnote citation is only included if the case name appears in full_text
- Invalid citations are removed from the headnote

Usage:
    python -m jobs.reextract_citations
    python -m jobs.reextract_citations --limit 100  # Process only 100 cases
    python -m jobs.reextract_citations --dry-run    # Show what would be updated
"""

import argparse
import asyncio
import json
import re
from typing import Optional

import asyncpg
import structlog

from config.settings import get_settings
from scrapers.utils.citation_parser import (
    ParsedCitation,
    parse_hk_citations,
    parse_hk_law_reports,
    parse_uk_citations,
    parse_au_citations,
)

logger = structlog.get_logger(__name__)

# Pattern to extract case name from citation context in headnote
# Looks for patterns like "Case Name [year] report page" or "Case Name (year) report page"
CASE_NAME_BEFORE_CITATION = re.compile(
    r"([A-Z][A-Za-z\s\.\,\'\-]+(?:\s+v\.?\s+[A-Z][A-Za-z\s\.\,\'\-]+)?)\s*[\[\(]\d{4}[\]\)]",
    re.IGNORECASE,
)


def extract_case_name_from_citation(citation: ParsedCitation, context: str) -> str | None:
    """
    Extract the case name associated with a citation from surrounding context.
    
    Args:
        citation: The parsed citation
        context: Text containing the citation (e.g., headnote)
        
    Returns:
        Case name if found, None otherwise
    """
    # Find the citation in context and look for case name before it
    citation_pos = context.find(citation.full_citation)
    if citation_pos == -1:
        return None
    
    # Look at text before the citation (up to 100 chars)
    start = max(0, citation_pos - 100)
    before_text = context[start:citation_pos]
    
    # Try to find case name pattern
    matches = list(CASE_NAME_BEFORE_CITATION.finditer(before_text + context[citation_pos:citation_pos+20]))
    if matches:
        # Get the last match (closest to citation)
        case_name = matches[-1].group(1).strip()
        # Clean up common prefixes
        for prefix in ["in ", "see ", "per ", "following ", "citing "]:
            if case_name.lower().startswith(prefix):
                case_name = case_name[len(prefix):].strip()
        return case_name if len(case_name) > 3 else None
    
    return None


def validate_headnote_citation(
    citation: ParsedCitation,
    headnote: str,
    full_text: str,
) -> bool:
    """
    Validate a citation from headnote by checking if case name exists in full_text.
    
    Args:
        citation: The parsed citation from headnote
        headnote: The headnote text
        full_text: The full judgment text
        
    Returns:
        True if citation is valid (case name found in full_text), False otherwise
    """
    # Extract case name from headnote context
    case_name = extract_case_name_from_citation(citation, headnote)
    
    if not case_name:
        # If we can't extract case name, check if citation itself appears in full_text
        # This handles cases where the full citation format is in the judgment
        return citation.full_citation in full_text
    
    # Check if case name appears in full_text (case-insensitive)
    # Use word boundaries to avoid partial matches
    case_name_pattern = re.escape(case_name)
    if re.search(case_name_pattern, full_text, re.IGNORECASE):
        return True
    
    # Try with just the first party name (before "v" or "v.")
    if " v" in case_name.lower():
        first_party = case_name.split(" v")[0].strip()
        if len(first_party) > 3 and re.search(re.escape(first_party), full_text, re.IGNORECASE):
            return True
    
    return False


def remove_citation_from_text(text: str, citation: str) -> str:
    """
    Remove a citation and its surrounding context from text.
    
    Args:
        text: The text to modify
        citation: The citation to remove
        
    Returns:
        Text with citation removed
    """
    # Find the citation
    pos = text.find(citation)
    if pos == -1:
        return text
    
    # Find the start of the line/bullet containing the citation
    start = text.rfind("\n", 0, pos)
    if start == -1:
        start = 0
    else:
        start += 1  # Move past the newline
    
    # Find the end of the line
    end = text.find("\n", pos)
    if end == -1:
        end = len(text)
    
    # Check if this is a list item (starts with - or *)
    line = text[start:end]
    if line.strip().startswith(("-", "*", "•")):
        # Remove the entire list item
        return text[:start] + text[end:].lstrip("\n")
    else:
        # Just remove the citation itself
        return text[:pos] + text[pos + len(citation):]


async def get_db_connection() -> asyncpg.Connection:
    """Get database connection from settings."""
    settings = get_settings()
    return await asyncpg.connect(settings.supabase_db_url)


async def reextract_citations(
    limit: Optional[int] = None,
    dry_run: bool = False,
    batch_size: int = 500,
) -> dict:
    """
    Re-extract citations from all cases using batch processing.
    
    Args:
        limit: Maximum number of cases to process (None for all)
        dry_run: If True, don't actually update the database
        batch_size: Number of cases to fetch per batch
        
    Returns:
        Stats dict with counts
    """
    log = logger.bind(dry_run=dry_run, limit=limit)
    log.info("Starting citation re-extraction")
    
    conn = await get_db_connection()
    
    try:
        # Get total count first
        count_query = "SELECT COUNT(*) FROM court_cases WHERE full_text IS NOT NULL AND full_text != ''"
        total_count = await conn.fetchval(count_query)
        if limit:
            total_count = min(total_count, limit)
        log.info("Total cases to process", count=total_count)
        
        stats = {
            "total": total_count,
            "updated": 0,
            "skipped": 0,
            "errors": 0,
            "headnote_citations_added": 0,
            "headnote_citations_removed": 0,
            "headnotes_modified": 0,
        }
        
        offset = 0
        processed = 0
        
        while processed < total_count:
            # Fetch a batch (now including headnote)
            query = """
                SELECT id, neutral_citation, full_text, headnote
                FROM court_cases
                WHERE full_text IS NOT NULL AND full_text != ''
                ORDER BY id
                LIMIT $1 OFFSET $2
            """
            rows = await conn.fetch(query, batch_size, offset)
            
            if not rows:
                break
            
            for row in rows:
                if limit and processed >= limit:
                    break
                    
                case_id = row["id"]
                neutral_citation = row["neutral_citation"]
                full_text = row["full_text"]
                headnote = row["headnote"] or ""
                
                try:
                    # Extract all citations from full_text (HK, UK, AU)
                    hk_neutral = parse_hk_citations(full_text)
                    hk_law_reports = parse_hk_law_reports(full_text)
                    uk_citations = parse_uk_citations(full_text)
                    au_citations = parse_au_citations(full_text)
                    
                    # Build cited_cases as list of objects with citation and case_name
                    all_ft_citations = hk_neutral + hk_law_reports + uk_citations + au_citations
                    cited_cases = []
                    cited_cases_set = set()
                    
                    for citation in all_ft_citations:
                        if citation.full_citation not in cited_cases_set:
                            # Try to extract case name from full_text context
                            case_name = extract_case_name_from_citation(citation, full_text)
                            cited_cases.append({
                                "citation": citation.full_citation,
                                "case_name": case_name,
                            })
                            cited_cases_set.add(citation.full_citation)
                    
                    # Extract citations from headnote and validate them
                    headnote_hk_neutral = parse_hk_citations(headnote)
                    headnote_hk_law_reports = parse_hk_law_reports(headnote)
                    headnote_uk_citations = parse_uk_citations(headnote)
                    headnote_au_citations = parse_au_citations(headnote)
                    
                    headnote_citations = (
                        headnote_hk_neutral + headnote_hk_law_reports +
                        headnote_uk_citations + headnote_au_citations
                    )
                    
                    # Track headnote modifications
                    modified_headnote = headnote
                    invalid_citations = []
                    
                    for citation in headnote_citations:
                        # Skip if already in full_text citations
                        if citation.full_citation in cited_cases_set:
                            # Update case_name if we have it from headnote but not from full_text
                            case_name = extract_case_name_from_citation(citation, headnote)
                            if case_name:
                                for c in cited_cases:
                                    if c["citation"] == citation.full_citation and not c["case_name"]:
                                        c["case_name"] = case_name
                            continue
                        
                        # Validate: check if case name exists in full_text
                        if validate_headnote_citation(citation, headnote, full_text):
                            # Valid citation - add to cited_cases with case name from headnote
                            case_name = extract_case_name_from_citation(citation, headnote)
                            cited_cases.append({
                                "citation": citation.full_citation,
                                "case_name": case_name,
                            })
                            cited_cases_set.add(citation.full_citation)
                            stats["headnote_citations_added"] += 1
                        else:
                            # Invalid/hallucinated citation - remove from headnote
                            invalid_citations.append(citation.full_citation)
                            modified_headnote = remove_citation_from_text(
                                modified_headnote, citation.full_citation
                            )
                            stats["headnote_citations_removed"] += 1
                    
                    # Remove self-citation (now cited_cases is list of dicts)
                    if neutral_citation:
                        cited_cases = [c for c in cited_cases if c["citation"] != neutral_citation]
                    
                    # Extract law report citations for THIS case from its own text
                    # Check first 2000 chars for law report citations (usually in header)
                    law_report_citations = []
                    header_text = full_text[:2000] if len(full_text) > 2000 else full_text
                    header_law_reports = parse_hk_law_reports(header_text)
                    
                    # Only include law report citations that likely refer to THIS case
                    for lr in header_law_reports:
                        if lr.full_citation not in cited_cases_set:
                            law_report_citations.append(lr.full_citation)
                    
                    # Check if headnote was modified
                    headnote_modified = modified_headnote != headnote
                    if headnote_modified:
                        stats["headnotes_modified"] += 1
                    
                    if dry_run:
                        if cited_cases or law_report_citations or headnote_modified:
                            log.info(
                                "Would update case",
                                case_id=str(case_id),
                                neutral_citation=neutral_citation,
                                cited_count=len(cited_cases),
                                law_report_count=len(law_report_citations),
                                headnote_modified=headnote_modified,
                                invalid_citations=invalid_citations if invalid_citations else None,
                            )
                    else:
                        if headnote_modified:
                            await conn.execute(
                                """
                                UPDATE court_cases
                                SET cited_cases = $1::jsonb,
                                    law_report_citations = $2::jsonb,
                                    headnote = $3,
                                    updated_at = NOW()
                                WHERE id = $4
                                """,
                                json.dumps(cited_cases),
                                json.dumps(law_report_citations),
                                modified_headnote,
                                case_id,
                            )
                        else:
                            await conn.execute(
                                """
                                UPDATE court_cases
                                SET cited_cases = $1::jsonb,
                                    law_report_citations = $2::jsonb,
                                    updated_at = NOW()
                                WHERE id = $3
                                """,
                                json.dumps(cited_cases),
                                json.dumps(law_report_citations),
                                case_id,
                            )
                    
                    stats["updated"] += 1
                        
                except Exception as e:
                    log.error("Error processing case", case_id=str(case_id), error=str(e))
                    stats["errors"] += 1
                
                processed += 1
            
            offset += batch_size
            log.info("Progress", processed=processed, total=total_count, pct=f"{100*processed/total_count:.1f}%")
        
        log.info("Citation re-extraction complete", **stats)
        return stats
        
    finally:
        await conn.close()


def main():
    parser = argparse.ArgumentParser(description="Re-extract citations from cases")
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
    
    args = parser.parse_args()
    
    # Configure logging
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.dev.ConsoleRenderer(),
        ],
    )
    
    asyncio.run(reextract_citations(
        limit=args.limit,
        dry_run=args.dry_run,
    ))


if __name__ == "__main__":
    main()
