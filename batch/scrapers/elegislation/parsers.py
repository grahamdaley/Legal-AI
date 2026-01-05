"""
HTML parsers for Hong Kong eLegislation content.
"""

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from bs4 import BeautifulSoup
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class ParsedSection:
    """Parsed legislation section."""

    section_number: str
    title: Optional[str] = None
    content: str = ""
    subsections: list["ParsedSection"] = field(default_factory=list)


@dataclass
class ParsedLegislation:
    """Parsed legislation data."""

    chapter_number: Optional[str] = None
    title_en: Optional[str] = None
    title_zh: Optional[str] = None
    type: str = "ordinance"
    enactment_date: Optional[date] = None
    commencement_date: Optional[date] = None
    status: str = "active"  # active, repealed, expired
    long_title: Optional[str] = None
    preamble: Optional[str] = None
    sections: list[ParsedSection] = field(default_factory=list)
    schedules: list[dict] = field(default_factory=list)
    version_date: Optional[date] = None


def parse_legislation_html(html: str, source_url: str) -> ParsedLegislation:
    """
    Parse a legislation page from eLegislation.
    
    Args:
        html: Raw HTML content
        source_url: URL the content was fetched from
        
    Returns:
        ParsedLegislation with extracted data
    """
    soup = BeautifulSoup(html, "lxml")
    result = ParsedLegislation()

    # Extract chapter number from URL or content
    result.chapter_number = _extract_chapter_number(source_url, soup)

    # Extract titles
    result.title_en = _extract_title(soup, "en")
    result.title_zh = _extract_title(soup, "zh")

    # Determine legislation type
    result.type = _determine_type(source_url, soup)

    # Extract dates
    result.enactment_date = _extract_date(soup, "enactment")
    result.commencement_date = _extract_date(soup, "commencement")
    result.version_date = _extract_date(soup, "version")

    # Check status
    result.status = _determine_status(soup)

    # Extract long title
    long_title_el = soup.find(class_=lambda c: c and "long-title" in c.lower() if c else False)
    if long_title_el:
        result.long_title = long_title_el.get_text(strip=True)

    # Extract preamble
    preamble_el = soup.find(class_=lambda c: c and "preamble" in c.lower() if c else False)
    if preamble_el:
        result.preamble = preamble_el.get_text(strip=True)

    # Extract sections
    result.sections = _extract_sections(soup)

    # Extract schedules
    result.schedules = _extract_schedules(soup)

    logger.debug(
        "Parsed legislation",
        chapter=result.chapter_number,
        title=result.title_en,
        sections_count=len(result.sections),
    )

    return result


def _extract_chapter_number(url: str, soup: BeautifulSoup) -> Optional[str]:
    """Extract chapter number from URL or page content."""
    # Try URL pattern: /hk/cap32 or /hk/cap32A
    cap_match = re.search(r"/cap(\d+[A-Z]?)", url, re.IGNORECASE)
    if cap_match:
        return f"Cap. {cap_match.group(1)}"

    # Try page content
    for pattern in [
        r"Cap(?:\.|\s+)(\d+[A-Z]?)",
        r"Chapter\s+(\d+[A-Z]?)",
        r"第(\d+[A-Z]?)章",
    ]:
        match = re.search(pattern, str(soup), re.IGNORECASE)
        if match:
            return f"Cap. {match.group(1)}"

    return None


def _extract_title(soup: BeautifulSoup, lang: str) -> Optional[str]:
    """Extract title in specified language."""
    
    # First, try the page <title> tag - most reliable for eLegislation
    # Format: "Cap. 32 Companies (Winding Up and Miscellaneous Provisions) Ordinance"
    title_tag = soup.find("title")
    if title_tag and lang == "en":
        title_text = title_tag.get_text(strip=True)
        # Remove "Cap. X" prefix to get just the title
        match = re.match(r"Cap\.\s*\d+[A-Z]?\s+(.+)", title_text)
        if match:
            title = match.group(1).strip()
            # Check it's not a generic page title
            if title and title not in ("View Legislation", "Back", "Home"):
                return title
        # If no cap prefix, check if it's a valid title
        elif title_text and not re.search(r"[\u4e00-\u9fff]", title_text):
            if title_text not in ("View Legislation", "Back", "Home", "eLegislation"):
                return title_text
    
    # Try Chinese title from page title
    if title_tag and lang == "zh":
        title_text = title_tag.get_text(strip=True)
        # Look for Chinese characters after the cap number
        match = re.search(r"Cap\.\s*\d+[A-Z]?\s+[^《]*《(.+?)》", title_text)
        if match:
            return match.group(1).strip()
        # Or just Chinese text
        if re.search(r"[\u4e00-\u9fff]", title_text):
            # Extract Chinese portion
            zh_match = re.search(r"([\u4e00-\u9fff].+)", title_text)
            if zh_match:
                return zh_match.group(1).strip()
    
    # Look for title elements with language indicators
    selectors = [
        f"[lang='{lang}'] .title",
        f"[lang='{lang}'] h1",
        f".title-{lang}",
        f".legislation-title[lang='{lang}']",
    ]

    for selector in selectors:
        el = soup.select_one(selector)
        if el:
            text = el.get_text(strip=True)
            if text and text not in ("View Legislation", "Back", "Home"):
                return text

    return None


def _determine_type(url: str, soup: BeautifulSoup) -> str:
    """Determine the type of legislation."""
    url_lower = url.lower()

    # Check URL patterns
    if "/reg" in url_lower or "regulation" in url_lower:
        return "regulation"
    if "/rule" in url_lower:
        return "rule"
    if "/order" in url_lower:
        return "order"
    if "/notice" in url_lower:
        return "notice"

    # Check for subsidiary legislation indicators
    text = soup.get_text().lower()
    if "subsidiary legislation" in text:
        if "regulation" in text[:500]:
            return "regulation"
        if "rule" in text[:500]:
            return "rule"
        if "order" in text[:500]:
            return "order"
        return "regulation"  # Default subsidiary type

    return "ordinance"


def _extract_date(soup: BeautifulSoup, date_type: str) -> Optional[date]:
    """Extract a specific date from the legislation."""
    
    # First, try Dublin Core metadata elements (used by eLegislation)
    if date_type == "version":
        # Look for dc_date class element
        dc_date_el = soup.find(class_="dc_date")
        if dc_date_el:
            date_str = dc_date_el.get_text(strip=True)
            parsed = _parse_date_string(date_str)
            if parsed:
                return parsed
    
    # Try meta tags
    meta_names = {
        "enactment": ["dc.date.enacted", "enacted", "enactment-date"],
        "commencement": ["dc.date.commenced", "commenced", "commencement-date"],
        "version": ["dc.date", "dc_date", "version-date"],
    }
    
    for meta_name in meta_names.get(date_type, []):
        meta_el = soup.find("meta", attrs={"name": meta_name})
        if meta_el and meta_el.get("content"):
            parsed = _parse_date_string(meta_el["content"])
            if parsed:
                return parsed
    
    # Try elements with specific classes
    class_patterns = {
        "enactment": ["enactment-date", "enacted-date", "date-enacted"],
        "commencement": ["commencement-date", "commenced-date", "date-commenced"],
        "version": ["version-date", "dc_date", "as-at-date"],
    }
    
    for class_name in class_patterns.get(date_type, []):
        el = soup.find(class_=class_name)
        if el:
            date_str = el.get_text(strip=True)
            parsed = _parse_date_string(date_str)
            if parsed:
                return parsed
    
    # Fallback: regex patterns in text
    text_patterns = {
        "enactment": [
            r"enacted[:\s]+(\d{1,2}[/.-]\d{1,2}[/.-]\d{4})",
            r"enacted[:\s]+(\d{4}[/.-]\d{1,2}[/.-]\d{1,2})",
            r"enacted[:\s]+(\d{4})",
        ],
        "commencement": [
            r"commenced?[:\s]+(\d{1,2}[/.-]\d{1,2}[/.-]\d{4})",
            r"commenced?[:\s]+(\d{4}[/.-]\d{1,2}[/.-]\d{1,2})",
            r"commencement[:\s]+(\d{1,2}[/.-]\d{1,2}[/.-]\d{4})",
        ],
        "version": [
            r"version[:\s]+(\d{1,2}[/.-]\d{1,2}[/.-]\d{4})",
            r"version[:\s]+(\d{4}[/.-]\d{1,2}[/.-]\d{1,2})",
            r"as at[:\s]+(\d{1,2}[/.-]\d{1,2}[/.-]\d{4})",
        ],
    }

    text = soup.get_text()
    for pattern in text_patterns.get(date_type, []):
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            date_str = match.group(1)
            return _parse_date_string(date_str)

    return None


def _parse_date_string(date_str: str) -> Optional[date]:
    """Parse various date string formats."""
    from datetime import datetime

    # Handle year-only
    if re.match(r"^\d{4}$", date_str):
        return date(int(date_str), 1, 1)

    formats = [
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d.%m.%Y",
        "%Y-%m-%d",
        "%Y/%m/%d",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue

    return None


def _determine_status(soup: BeautifulSoup) -> str:
    """Determine if legislation is active, repealed, or expired."""
    text = soup.get_text().lower()

    if "repealed" in text[:1000] or "廢除" in text[:1000]:
        return "repealed"
    if "expired" in text[:1000] or "届滿" in text[:1000]:
        return "expired"
    if "omitted" in text[:1000]:
        return "omitted"

    return "active"


def _extract_sections(soup: BeautifulSoup) -> list[ParsedSection]:
    """Extract all sections from the legislation."""
    sections = []

    # Look for section containers
    section_containers = soup.find_all(
        class_=lambda c: c and any(
            x in c.lower() for x in ["section", "provision", "clause"]
        ) if c else False
    )

    for container in section_containers:
        section = _parse_section_element(container)
        if section:
            sections.append(section)

    # Fallback: look for numbered sections in text
    if not sections:
        sections = _extract_sections_from_text(soup)

    return sections


def _parse_section_element(element) -> Optional[ParsedSection]:
    """Parse a section from an HTML element."""
    # Try to find section number
    number_el = element.find(class_=lambda c: c and "number" in c.lower() if c else False)
    if not number_el:
        # Try to extract from text
        text = element.get_text()[:50]
        match = re.match(r"^(\d+[A-Z]?\.?)\s*", text)
        if match:
            section_num = match.group(1).rstrip(".")
        else:
            return None
    else:
        section_num = number_el.get_text(strip=True).rstrip(".")

    # Get title
    title_el = element.find(class_=lambda c: c and "heading" in c.lower() if c else False)
    title = title_el.get_text(strip=True) if title_el else None

    # Get content
    content_el = element.find(class_=lambda c: c and "content" in c.lower() if c else False)
    content = content_el.get_text(separator="\n", strip=True) if content_el else element.get_text(separator="\n", strip=True)

    return ParsedSection(
        section_number=section_num,
        title=title,
        content=content,
    )


def _extract_sections_from_text(soup: BeautifulSoup) -> list[ParsedSection]:
    """Extract sections by parsing the text content."""
    sections = []
    text = soup.get_text()

    # Pattern for section headers
    pattern = r"^(\d+[A-Z]?)\.\s+(.+?)(?=\n\d+[A-Z]?\.\s|\Z)"
    matches = re.findall(pattern, text, re.MULTILINE | re.DOTALL)

    for num, content in matches[:100]:  # Limit to prevent runaway
        # Try to split title from content
        lines = content.strip().split("\n", 1)
        title = lines[0].strip() if lines else None
        body = lines[1].strip() if len(lines) > 1 else content.strip()

        sections.append(ParsedSection(
            section_number=num,
            title=title,
            content=body,
        ))

    return sections


def _extract_schedules(soup: BeautifulSoup) -> list[dict]:
    """Extract schedules from the legislation."""
    schedules = []

    schedule_containers = soup.find_all(
        class_=lambda c: c and "schedule" in c.lower() if c else False
    )

    for i, container in enumerate(schedule_containers, 1):
        title_el = container.find(["h1", "h2", "h3", "h4"])
        title = title_el.get_text(strip=True) if title_el else f"Schedule {i}"

        content = container.get_text(separator="\n", strip=True)

        schedules.append({
            "number": i,
            "title": title,
            "content": content,
        })

    return schedules


def parse_sitemap_xml(xml_content: str) -> list[str]:
    """
    Parse sitemap XML to extract legislation URLs.
    
    Args:
        xml_content: Raw XML content
        
    Returns:
        List of legislation URLs
    """
    soup = BeautifulSoup(xml_content, "xml")
    urls = []

    # Handle sitemap index (contains links to other sitemaps)
    sitemap_locs = soup.find_all("sitemap")
    if sitemap_locs:
        for sitemap in sitemap_locs:
            loc = sitemap.find("loc")
            if loc:
                urls.append(loc.get_text(strip=True))
        return urls

    # Handle regular sitemap (contains page URLs)
    url_elements = soup.find_all("url")
    seen_chapters = set()
    
    for url_el in url_elements:
        loc = url_el.find("loc")
        if loc:
            url = loc.get_text(strip=True)
            # Filter for legislation pages
            if "/hk/cap" in url.lower():
                # Extract base chapter URL from PDF URLs
                # e.g., https://www.elegislation.gov.hk/hk/cap32!en.pdf -> /hk/cap32
                match = re.search(r"(/hk/cap\d+[A-Z]?)", url, re.IGNORECASE)
                if match:
                    chapter_path = match.group(1)
                    if chapter_path.lower() not in seen_chapters:
                        seen_chapters.add(chapter_path.lower())
                        # Construct HTML page URL
                        base_url = "https://www.elegislation.gov.hk"
                        urls.append(f"{base_url}{chapter_path}")

    return urls
