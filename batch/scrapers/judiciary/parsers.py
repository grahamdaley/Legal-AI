"""
HTML and PDF parsers for Hong Kong Judiciary judgments.
"""

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

from bs4 import BeautifulSoup
import structlog

from ..utils.citation_parser import parse_hk_citations, extract_case_number

logger = structlog.get_logger(__name__)


@dataclass
class ParsedJudgment:
    """Parsed judgment data."""

    neutral_citation: Optional[str] = None
    case_number: Optional[str] = None
    case_name: Optional[str] = None
    court: Optional[str] = None
    decision_date: Optional[date] = None
    judges: list[str] = field(default_factory=list)
    parties: dict = field(default_factory=dict)
    headnote: Optional[str] = None
    catchwords: list[str] = field(default_factory=list)
    full_text: Optional[str] = None
    word_count: int = 0
    language: str = "en"
    cited_cases: list[str] = field(default_factory=list)


def parse_judgment_html(html: str, source_url: str) -> ParsedJudgment:
    """
    Parse a judgment HTML page from the Judiciary website.
    
    The LRS judgment pages use custom HTML tags:
    - <caseno> for case number
    - <parties> for party information
    - <coram> for judges
    - <date> for hearing/judgment dates
    
    Args:
        html: Raw HTML content
        source_url: URL the content was fetched from
        
    Returns:
        ParsedJudgment with extracted data
    """
    soup = BeautifulSoup(html, "lxml")
    result = ParsedJudgment()

    # Extract case number and name from title (format: "FACC1/1997 HKSAR v. TANG SIU MAN")
    # There may be multiple title tags - find the non-empty one
    for title_el in soup.find_all("title"):
        title_text = title_el.get_text(strip=True)
        if title_text:
            # Split on first space to get case number and name
            parts = title_text.split(" ", 1)
            if len(parts) >= 1:
                result.case_number = parts[0]
            if len(parts) >= 2:
                result.case_name = parts[1]
            break

    # Extract case number from text if not in title (e.g., "FACC No. 1 of 1997")
    if not result.case_number:
        case_no_pattern = r"([A-Z]{2,6})\s*(?:No\.?\s*)?(\d+)\s*(?:of\s*)?(\d{4})"
        case_match = re.search(case_no_pattern, html)
        if case_match:
            result.case_number = f"{case_match.group(1)}{case_match.group(2)}/{case_match.group(3)}"

    # Extract neutral citation from content
    citation_pattern = r"\[(\d{4})\]\s*(HK(?:CFA|CA|CFI|DC|FC|LT|LAB|SCT))\s*(\d+)"
    citation_match = re.search(citation_pattern, html)
    if citation_match:
        result.neutral_citation = citation_match.group(0)
        result.court = citation_match.group(2)
    
    # Infer court from case number if not found
    if not result.court and result.case_number:
        court_code = re.match(r"([A-Z]+)", result.case_number)
        if court_code:
            result.court = _map_case_prefix_to_court(court_code.group(1))

    # Extract judges from <coram> tag
    coram_el = soup.find("coram")
    if coram_el:
        coram_text = coram_el.get_text(strip=True)
        result.judges = _extract_judges_from_coram(coram_text)
    else:
        result.judges = _extract_judges(html, soup)

    # Extract decision date from <date> tag
    date_el = soup.find("date")
    if date_el:
        date_text = date_el.get_text(strip=True)
        result.decision_date = _extract_date_from_text(date_text)
    else:
        result.decision_date = _extract_date(html, soup)

    # Extract parties from <parties> tag
    parties_el = soup.find("parties")
    if parties_el:
        result.parties = _extract_parties_from_tag(parties_el)
    else:
        result.parties = _extract_parties(html, soup, result.case_name)

    # Extract full text
    body = soup.find("body")
    if body:
        # Remove script and style elements
        for element in body.find_all(["script", "style", "nav", "header", "footer"]):
            element.decompose()
        result.full_text = body.get_text(separator="\n", strip=True)
        result.word_count = len(result.full_text.split())

    # Detect language
    if soup.find("html"):
        lang = soup.find("html").get("lang", "en")
        result.language = "zh" if "zh" in lang.lower() else "en"

    # Check for Chinese characters in text
    if result.full_text and re.search(r"[\u4e00-\u9fff]", result.full_text[:1000]):
        # Significant Chinese content
        chinese_ratio = len(re.findall(r"[\u4e00-\u9fff]", result.full_text[:1000])) / 1000
        if chinese_ratio > 0.3:
            result.language = "zh"

    # Extract cited cases
    if result.full_text:
        citations = parse_hk_citations(result.full_text)
        result.cited_cases = [c.full_citation for c in citations]
        # Remove self-citation
        if result.neutral_citation and result.neutral_citation in result.cited_cases:
            result.cited_cases.remove(result.neutral_citation)

    logger.debug(
        "Parsed judgment",
        citation=result.neutral_citation,
        case_name=result.case_name,
        date=result.decision_date,
        word_count=result.word_count,
    )

    return result


def _clean_case_name(text: str) -> str:
    """Clean up case name text."""
    # Remove citation if present
    text = re.sub(r"\[?\d{4}\]?\s*HK[A-Z]+\s*\d+", "", text)
    # Remove common prefixes
    text = re.sub(r"^(IN THE MATTER OF|RE:|BETWEEN)\s*", "", text, flags=re.IGNORECASE)
    # Clean whitespace
    text = " ".join(text.split())
    return text.strip()


def _extract_date(html: str, soup: BeautifulSoup) -> Optional[date]:
    """Extract decision date from judgment."""
    # Common date patterns
    date_patterns = [
        r"Date of (?:Judgment|Decision|Ruling|Hearing)[:\s]*(\d{1,2})\s+(\w+)\s+(\d{4})",
        r"(\d{1,2})\s+(\w+)\s+(\d{4})",
        r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})",
    ]

    for pattern in date_patterns[:1]:  # Try specific pattern first
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            try:
                day = int(match.group(1))
                month_str = match.group(2)
                year = int(match.group(3))
                month = _parse_month(month_str)
                if month:
                    return date(year, month, day)
            except (ValueError, AttributeError):
                continue

    # Try meta tags
    for meta in soup.find_all("meta"):
        name = meta.get("name", "").lower()
        if "date" in name:
            content = meta.get("content", "")
            parsed = _parse_date_string(content)
            if parsed:
                return parsed

    return None


def _parse_month(month_str: str) -> Optional[int]:
    """Parse month name to number."""
    months = {
        "january": 1, "jan": 1,
        "february": 2, "feb": 2,
        "march": 3, "mar": 3,
        "april": 4, "apr": 4,
        "may": 5,
        "june": 6, "jun": 6,
        "july": 7, "jul": 7,
        "august": 8, "aug": 8,
        "september": 9, "sep": 9, "sept": 9,
        "october": 10, "oct": 10,
        "november": 11, "nov": 11,
        "december": 12, "dec": 12,
    }
    return months.get(month_str.lower())


def _parse_date_string(date_str: str) -> Optional[date]:
    """Parse various date string formats."""
    formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y/%m/%d",
        "%d %B %Y",
        "%d %b %Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _extract_judges(html: str, soup: BeautifulSoup) -> list[str]:
    """Extract judge names from judgment."""
    judges = []

    # Look for common patterns
    patterns = [
        r"(?:Before|Coram)[:\s]*(.+?)(?:\n|$)",
        r"(?:The Honourable|Hon\.?)\s+(?:Mr\.?|Mrs\.?|Ms\.?)?\s*Justice\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
        r"(?:Chief Justice|CJ|JA|J)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
    ]

    for pattern in patterns:
        matches = re.findall(pattern, html, re.IGNORECASE)
        for match in matches:
            if isinstance(match, tuple):
                match = match[0]
            # Clean and validate
            name = match.strip()
            if name and len(name) > 2 and name not in judges:
                judges.append(name)

    return judges[:10]  # Limit to reasonable number


def _extract_parties(html: str, soup: BeautifulSoup, case_name: Optional[str]) -> dict:
    """Extract party names from judgment."""
    parties = {"applicant": [], "respondent": []}

    if not case_name:
        return parties

    # Try to split on "v." or "v "
    if " v. " in case_name:
        parts = case_name.split(" v. ", 1)
    elif " v " in case_name:
        parts = case_name.split(" v ", 1)
    elif " and " in case_name.lower():
        parts = re.split(r"\s+and\s+", case_name, 1, flags=re.IGNORECASE)
    else:
        return parties

    if len(parts) == 2:
        parties["applicant"] = [parts[0].strip()]
        parties["respondent"] = [parts[1].strip()]

    return parties


def _map_case_prefix_to_court(prefix: str) -> Optional[str]:
    """Map case number prefix to court name."""
    court_map = {
        "FACC": "CFA",  # Court of Final Appeal (Criminal)
        "FACV": "CFA",  # Court of Final Appeal (Civil)
        "FAMV": "CFA",  # Court of Final Appeal (Misc)
        "CACC": "CA",   # Court of Appeal (Criminal)
        "CACV": "CA",   # Court of Appeal (Civil)
        "CAAR": "CA",   # Court of Appeal (Application for Review)
        "HCCC": "CFI",  # Court of First Instance (Criminal)
        "HCAL": "CFI",  # Court of First Instance (Admin Law)
        "HCMP": "CFI",  # Court of First Instance (Misc)
        "HCA": "CFI",   # High Court Action
        "HCCT": "CFI",  # Construction and Arbitration
        "DCCC": "DC",   # District Court (Criminal)
        "DCCJ": "DC",   # District Court (Civil)
        "FCMC": "FC",   # Family Court
        "LDBM": "LT",   # Lands Tribunal
        "LDCS": "LT",   # Lands Tribunal
    }
    return court_map.get(prefix.upper())


def _extract_judges_from_coram(coram_text: str) -> list[str]:
    """Extract judge names from coram text.
    
    Hong Kong judgment coram sections use various formats:
    - "Hon. Leonard V.-P., Cons Fuad J.A." (titles with periods)
    - "Mr Justice Ribeiro PJ, Mr Justice Fok PJ" (full titles)
    - "Cheung CJHC, Lam VP and Barma JA" (abbreviated titles)
    
    This function extracts clean judge names by:
    1. First normalizing title patterns with periods (V.-P. -> VP, J.A. -> JA)
    2. Splitting on commas and "and"
    3. Removing judicial titles to get the surname/name
    """
    judges = []
    
    # Remove common prefixes
    coram_text = re.sub(r"^(?:Appeal Committee|Coram)[:\s]*", "", coram_text, flags=re.IGNORECASE)
    
    # Normalize title patterns with periods before splitting
    # V.-P. or V-P. or V.P. -> VP
    coram_text = re.sub(r"\bV\.?-?P\.?\b", "VP", coram_text, flags=re.IGNORECASE)
    # J.A. or J. A. or JA. -> JA
    coram_text = re.sub(r"\bJ\.?\s*A\.?\b", "JA", coram_text, flags=re.IGNORECASE)
    # C.J. or CJ. -> CJ
    coram_text = re.sub(r"\bC\.?\s*J\.?\b", "CJ", coram_text, flags=re.IGNORECASE)
    # P.J. or PJ. -> PJ
    coram_text = re.sub(r"\bP\.?\s*J\.?\b", "PJ", coram_text, flags=re.IGNORECASE)
    # N.P.J. or NPJ. -> NPJ
    coram_text = re.sub(r"\bN\.?\s*P\.?\s*J\.?\b", "NPJ", coram_text, flags=re.IGNORECASE)
    # CJHC (Chief Justice High Court)
    coram_text = re.sub(r"\bC\.?\s*J\.?\s*H\.?\s*C\.?\b", "CJHC", coram_text, flags=re.IGNORECASE)
    
    # Split on commas and "and" - but be careful with "and" to use word boundaries
    parts = re.split(r",\s*|\s+and\s+", coram_text)
    
    # Judicial titles to remove (order matters - longer patterns first)
    title_patterns = [
        r"\bThe\s+Honourable\b",
        r"\bChief\s+Justice\b",
        r"\bMr\.?\s+Justice\b",
        r"\bMrs\.?\s+Justice\b", 
        r"\bMs\.?\s+Justice\b",
        r"\bJustice\b",
        r"\bHon\.?\b",
        r"\bCJHC\b",  # Chief Justice High Court
        r"\bNPJ\b",   # Non-Permanent Judge
        r"\bPJ\b",    # Permanent Judge
        r"\bJA\b",    # Justice of Appeal
        r"\bVP\b",    # Vice-President
        r"\bCJ\b",    # Chief Justice
        r"\bJ\b",     # Justice (must be last of single-letter patterns)
    ]
    
    for part in parts:
        name = part
        # Remove all title patterns
        for pattern in title_patterns:
            name = re.sub(pattern, "", name, flags=re.IGNORECASE)
        
        # Clean up whitespace and punctuation
        name = re.sub(r"\s+", " ", name)  # Normalize whitespace
        name = re.sub(r"^[\s,\.]+|[\s,\.]+$", "", name)  # Strip leading/trailing punctuation
        name = name.strip()
        
        # Only include if it looks like a valid name (not just punctuation)
        # Allow 2-char names like "Ma" but require at least 2 consecutive letters
        if name and len(name) >= 2 and re.search(r"[A-Za-z]{2,}", name):
            judges.append(name)
    
    return judges


def _extract_date_from_text(date_text: str) -> Optional[date]:
    """Extract date from date tag text."""
    # Look for "Date of Handing Down" or "Date of Judgment"
    patterns = [
        r"Date of (?:Handing Down|Judgment|Decision)[:\s]*(\d{1,2})\s+(\w+)\s+(\d{4})",
        r"(\d{1,2})\s+(\w+)\s+(\d{4})",
        r"(\d{1,2})/(\d{1,2})/(\d{4})",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, date_text, re.IGNORECASE)
        if match:
            try:
                if "/" in pattern:
                    day = int(match.group(1))
                    month = int(match.group(2))
                    year = int(match.group(3))
                else:
                    day = int(match.group(1))
                    month_str = match.group(2)
                    year = int(match.group(3))
                    month = _parse_month(month_str)
                    if not month:
                        continue
                return date(year, month, day)
            except (ValueError, AttributeError):
                continue
    
    return None


def _extract_parties_from_tag(parties_el) -> dict:
    """Extract parties from <parties> tag."""
    parties = {"applicant": [], "respondent": []}
    
    text = parties_el.get_text(separator=" ", strip=True)
    
    # Look for "Between ... AND ..." pattern
    between_match = re.search(r"Between\s+(.+?)\s+(?:Appellant|Applicant|Plaintiff)", text, re.IGNORECASE)
    if between_match:
        parties["applicant"].append(between_match.group(1).strip())
    
    # Look for respondent
    resp_match = re.search(r"(?:AND|and)\s+(.+?)\s+(?:Respondent|Defendant)", text, re.IGNORECASE)
    if resp_match:
        parties["respondent"].append(resp_match.group(1).strip())
    
    # Fallback: look in table cells
    if not parties["applicant"]:
        cells = parties_el.find_all("td")
        for i, cell in enumerate(cells):
            cell_text = cell.get_text(strip=True)
            if "Appellant" in cell_text or "Applicant" in cell_text or "Plaintiff" in cell_text:
                # Previous cell likely has the name
                if i > 0:
                    name = cells[i-1].get_text(strip=True)
                    if name and name not in ["Between", "AND", "&nbsp;"]:
                        parties["applicant"].append(name)
            elif "Respondent" in cell_text or "Defendant" in cell_text:
                if i > 0:
                    name = cells[i-1].get_text(strip=True)
                    if name and name not in ["Between", "AND", "&nbsp;"]:
                        parties["respondent"].append(name)
    
    return parties


def extract_pdf_text(pdf_bytes: bytes) -> Optional[str]:
    """
    Extract text from a PDF judgment.
    
    Args:
        pdf_bytes: Raw PDF content
        
    Returns:
        Extracted text or None
    """
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        text_parts = []

        for page in doc:
            text_parts.append(page.get_text())

        doc.close()
        return "\n".join(text_parts)

    except ImportError:
        logger.warning("PyMuPDF not installed, cannot extract PDF text")
        return None
    except Exception as e:
        logger.error("Failed to extract PDF text", error=str(e))
        return None
