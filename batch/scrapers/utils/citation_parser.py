"""
Citation parser for Hong Kong and other common law jurisdictions.

Supports parsing and normalizing legal citations from judgment text.
"""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ParsedCitation:
    """Parsed legal citation."""

    full_citation: str
    year: int
    court: str
    number: int
    jurisdiction: str = "HK"
    volume: Optional[int] = None  # For law reports like [2024] 1 AC 123


# Hong Kong neutral citation patterns (e.g., [2024] HKCFI 123)
HK_CITATION_PATTERN = re.compile(
    r"\[(\d{4})\]\s*(HK(?:CFA|CA|CFI|DC|FC|LT|LAB|SCT|EC|MC|HKEC))\s*(\d+)",
    re.IGNORECASE,
)

# Hong Kong Law Reports patterns (e.g., [1996] 2 HKLR 401, [2000] 3 HKCFAR 125)
HK_LAW_REPORTS_PATTERN = re.compile(
    r"\[(\d{4})\]\s*(\d+)\s*(HKLR|HKLRD|HKCFAR|HKC)\s*(\d+)",
    re.IGNORECASE,
)

# Alternative HK patterns (case numbers)
HK_CASE_NUMBER_PATTERN = re.compile(
    r"(FACV|CACV|CACC|CAAR|HCAL|HCMP|HCCT|HCCL|HCSD|HCPI|HCMC|HCCW|HCAJ|"
    r"DCCC|DCEC|DCMP|DCPI|DCCJ|FCMC|FCMP|LDBM|LDMR|LDCS|LDPD|LDRT|"
    r"ESCC|KCCC|KTCC|STCC|FLCC|TMCC|TWCC|WKCC)\s*(\d+)/(\d{4})",
    re.IGNORECASE,
)

# UK citation patterns
UK_CITATION_PATTERN = re.compile(
    r"\[(\d{4})\]\s*(?:(\d+)\s+)?(AC|QB|WLR|All\s*ER|UKSC|UKHL|UKPC|EWCA\s*(?:Civ|Crim)?|EWHC)\s*(\d+)?",
    re.IGNORECASE,
)

# Australian citation patterns
AU_CITATION_PATTERN = re.compile(
    r"\[(\d{4})\]\s*(HCA|FCAFC|FCA|NSWCA|NSWSC|VSCA|VSC|QCA|QSC)\s*(\d+)",
    re.IGNORECASE,
)

# Court code to full name mapping
HK_COURT_NAMES = {
    "HKCFA": "Court of Final Appeal",
    "HKCA": "Court of Appeal",
    "HKCFI": "Court of First Instance",
    "HKDC": "District Court",
    "HKFC": "Family Court",
    "HKLT": "Lands Tribunal",
    "HKLAB": "Labour Tribunal",
    "HKSCT": "Small Claims Tribunal",
    "HKEC": "Eastern Magistrates' Courts",
    "HKMC": "Magistrates' Courts",
}


def parse_hk_citations(text: str) -> list[ParsedCitation]:
    """
    Extract all Hong Kong neutral citations from text.
    
    Args:
        text: Text to search for citations
        
    Returns:
        List of parsed citations
    """
    citations = []
    seen = set()

    for match in HK_CITATION_PATTERN.finditer(text):
        full = match.group(0)
        if full not in seen:
            seen.add(full)
            citations.append(
                ParsedCitation(
                    full_citation=full,
                    year=int(match.group(1)),
                    court=match.group(2).upper(),
                    number=int(match.group(3)),
                    jurisdiction="HK",
                )
            )

    return citations


def parse_hk_law_reports(text: str) -> list[ParsedCitation]:
    """
    Extract Hong Kong Law Reports citations from text.
    
    Formats:
        - HKLR: Hong Kong Law Reports (e.g., [1996] 2 HKLR 401)
        - HKLRD: Hong Kong Law Reports & Digest (e.g., [2010] 1 HKLRD 100)
        - HKCFAR: Hong Kong Court of Final Appeal Reports (e.g., [2000] 3 HKCFAR 125)
        - HKC: Hong Kong Cases (e.g., [1995] 1 HKC 200)
    
    Args:
        text: Text to search for citations
        
    Returns:
        List of parsed citations
    """
    citations = []
    seen = set()

    for match in HK_LAW_REPORTS_PATTERN.finditer(text):
        full = match.group(0)
        if full not in seen:
            seen.add(full)
            citations.append(
                ParsedCitation(
                    full_citation=full,
                    year=int(match.group(1)),
                    court=match.group(3).upper(),
                    number=int(match.group(4)),
                    jurisdiction="HK",
                    volume=int(match.group(2)),
                )
            )

    return citations


def parse_uk_citations(text: str) -> list[ParsedCitation]:
    """
    Extract UK citations from text.
    
    Args:
        text: Text to search for citations
        
    Returns:
        List of parsed citations
    """
    citations = []
    seen = set()

    for match in UK_CITATION_PATTERN.finditer(text):
        full = match.group(0)
        if full not in seen:
            seen.add(full)
            volume = int(match.group(2)) if match.group(2) else None
            number = int(match.group(4)) if match.group(4) else 0
            citations.append(
                ParsedCitation(
                    full_citation=full,
                    year=int(match.group(1)),
                    court=match.group(3).upper().replace(" ", ""),
                    number=number,
                    jurisdiction="UK",
                    volume=volume,
                )
            )

    return citations


def parse_au_citations(text: str) -> list[ParsedCitation]:
    """
    Extract Australian citations from text.
    
    Args:
        text: Text to search for citations
        
    Returns:
        List of parsed citations
    """
    citations = []
    seen = set()

    for match in AU_CITATION_PATTERN.finditer(text):
        full = match.group(0)
        if full not in seen:
            seen.add(full)
            citations.append(
                ParsedCitation(
                    full_citation=full,
                    year=int(match.group(1)),
                    court=match.group(2).upper(),
                    number=int(match.group(3)),
                    jurisdiction="AU",
                )
            )

    return citations


def extract_all_citations(text: str) -> list[ParsedCitation]:
    """
    Extract all recognized citations from text.
    
    Args:
        text: Text to search for citations
        
    Returns:
        List of all parsed citations from all jurisdictions
    """
    citations = []
    citations.extend(parse_hk_citations(text))
    citations.extend(parse_hk_law_reports(text))
    citations.extend(parse_uk_citations(text))
    citations.extend(parse_au_citations(text))
    return citations


def normalize_citation(citation: str) -> str:
    """
    Normalize a citation to standard format.
    
    Args:
        citation: Raw citation string
        
    Returns:
        Normalized citation string
    """
    citation = citation.strip()

    # Try HK format first
    match = HK_CITATION_PATTERN.match(citation)
    if match:
        return f"[{match.group(1)}] {match.group(2).upper()} {match.group(3)}"

    # Try UK format
    match = UK_CITATION_PATTERN.match(citation)
    if match:
        parts = [f"[{match.group(1)}]"]
        if match.group(2):
            parts.append(match.group(2))
        parts.append(match.group(3).upper().replace(" ", " "))
        if match.group(4):
            parts.append(match.group(4))
        return " ".join(parts)

    # Return as-is if no pattern matches
    return citation


def extract_case_number(text: str) -> Optional[str]:
    """
    Extract HK case number (e.g., FACV 1/2024) from text.
    
    Args:
        text: Text to search
        
    Returns:
        Case number or None
    """
    match = HK_CASE_NUMBER_PATTERN.search(text)
    if match:
        return f"{match.group(1).upper()} {match.group(2)}/{match.group(3)}"
    return None


def get_court_hierarchy(court_code: str) -> int:
    """
    Get hierarchy level for a court (1 = highest).
    
    Args:
        court_code: Court citation code (e.g., 'HKCFA')
        
    Returns:
        Hierarchy level (1-5)
    """
    hierarchy = {
        "HKCFA": 1,
        "HKCA": 2,
        "HKCFI": 3,
        "HKDC": 4,
        "HKFC": 4,
        "HKLT": 4,
        "HKLAB": 5,
        "HKSCT": 5,
    }
    return hierarchy.get(court_code.upper(), 5)
