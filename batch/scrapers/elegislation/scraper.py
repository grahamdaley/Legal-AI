"""
Hong Kong eLegislation scraper for elegislation.gov.hk

Scrapes legislation from the official Hong Kong e-Legislation database.

The site provides a sitemap at https://www.elegislation.gov.hk/sitemapindex.xml
which can be used to discover all legislation URLs.

Note: The site uses heavy JavaScript rendering, so Playwright is required.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import AsyncIterator, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup
import structlog

from ..base import BaseScraper, ScrapedItem, ScraperConfig
from .config import ELegislationConfig
from .parsers import (
    parse_legislation_html,
    parse_sitemap_xml,
    ParsedLegislation,
    ParsedSection,
)

logger = structlog.get_logger(__name__)


@dataclass
class LegislationSection:
    """A section within a piece of legislation."""

    section_number: str
    title: Optional[str] = None
    content: str = ""
    source_url: Optional[str] = None


@dataclass
class LegislationItem(ScrapedItem):
    """Scraped legislation from eLegislation."""

    chapter_number: Optional[str] = None
    title_en: Optional[str] = None
    title_zh: Optional[str] = None
    type: str = "ordinance"
    enactment_date: Optional[date] = None
    commencement_date: Optional[date] = None
    status: str = "active"
    long_title: Optional[str] = None
    preamble: Optional[str] = None
    sections: list[LegislationSection] = field(default_factory=list)
    schedules: list[dict] = field(default_factory=list)
    version_date: Optional[date] = None
    pdf_url: Optional[str] = None

    @classmethod
    def from_parsed(
        cls,
        parsed: ParsedLegislation,
        source_url: str,
        raw_html: str,
    ) -> "LegislationItem":
        """Create from parsed legislation data."""
        sections = [
            LegislationSection(
                section_number=s.section_number,
                title=s.title,
                content=s.content,
            )
            for s in parsed.sections
        ]

        return cls(
            source_url=source_url,
            raw_html=raw_html,
            chapter_number=parsed.chapter_number,
            title_en=parsed.title_en,
            title_zh=parsed.title_zh,
            type=parsed.type,
            enactment_date=parsed.enactment_date,
            commencement_date=parsed.commencement_date,
            status=parsed.status,
            long_title=parsed.long_title,
            preamble=parsed.preamble,
            sections=sections,
            schedules=parsed.schedules,
            version_date=parsed.version_date,
        )


class ELegislationScraper(BaseScraper):
    """
    Scraper for Hong Kong eLegislation database.
    
    Uses the sitemap to discover all legislation URLs, then scrapes
    each piece of legislation including all sections.
    
    Usage:
        config = ScraperConfig(
            base_url="https://www.elegislation.gov.hk",
            request_delay=3.0,
            state_file="./state/elegislation_state.json",
        )
        async with ELegislationScraper(config) as scraper:
            async for item in scraper.run():
                print(item.chapter_number, item.title_en)
    """

    BASE_URL = "https://www.elegislation.gov.hk"
    SITEMAP_URL = "https://www.elegislation.gov.hk/sitemapindex.xml"

    def __init__(
        self,
        config: Optional[ScraperConfig] = None,
        elegislation_config: Optional[ELegislationConfig] = None,
    ):
        if config is None:
            config = ScraperConfig(
                base_url=self.BASE_URL,
                request_delay=3.0,
                max_concurrent=2,
            )
        super().__init__(config)

        self.elegislation_config = elegislation_config or ELegislationConfig()
        self._log = logger.bind(scraper="ELegislationScraper")
        self._sitemap_urls: list[str] = []

    async def _fetch_sitemap(self, url: str) -> Optional[str]:
        """
        Fetch sitemap XML content using HTTP requests.
        
        Sitemaps are static XML files that don't need browser rendering.
        Using requests is faster and handles .gz files properly.
        """
        import aiohttp
        import gzip
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status != 200:
                        self._log.warning("Failed to fetch sitemap", url=url, status=response.status)
                        return None
                    
                    content = await response.read()
                    
                    # Try to decompress if gzipped (check magic bytes)
                    if content[:2] == b'\x1f\x8b':
                        content = gzip.decompress(content)
                    
                    text = content.decode('utf-8')
                    
                    # Skip empty or invalid responses
                    if not text.strip() or not text.strip().startswith('<?xml'):
                        self._log.warning("Invalid sitemap content", url=url)
                        return None
                    
                    return text
        except Exception as e:
            self._log.error("Error fetching sitemap", url=url, error=str(e))
            return None

    async def get_index_urls(self) -> AsyncIterator[str]:
        """
        Generate URLs for all legislation pages.
        
        Generates URLs based on known chapter number patterns since
        the sitemap may not be reliably accessible.
        
        Yields:
            URLs to individual legislation pages
        """
        self._log.info("Generating legislation URLs by chapter number")
        
        # Hong Kong has chapters numbered 1-1200+ 
        # Generate URLs for main chapters
        base_url = "https://www.elegislation.gov.hk/hk/cap"
        
        for cap_num in range(1, 1201):
            url = f"{base_url}{cap_num}"
            
            # Filter based on config
            if not self._should_include_url(url):
                continue
            
            yield url
            
            # Also yield subsidiary legislation (cap1A, cap1B, etc.) if configured
            if self.elegislation_config.include_subsidiary:
                for suffix in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L']:
                    sub_url = f"{base_url}{cap_num}{suffix}"
                    yield sub_url

    def _should_include_url(self, url: str) -> bool:
        """Check if URL should be included based on config."""
        url_lower = url.lower()

        # Check for subsidiary legislation
        if not self.elegislation_config.include_subsidiary:
            # Subsidiary legislation URLs often have patterns like /cap32A
            if any(c.isalpha() for c in url.split("/cap")[-1][:3] if c != "/"):
                return False

        # Check for historical versions
        if not self.elegislation_config.include_historical:
            if "history" in url_lower or "version" in url_lower:
                return False

        return True

    async def scrape_item(self, url: str) -> Optional[LegislationItem]:
        """
        Scrape a single legislation page.
        
        Args:
            url: URL to the legislation page
            
        Returns:
            LegislationItem with extracted data, or None if failed
        """
        self._log.info("Scraping legislation", url=url)

        # eLegislation uses heavy JS, wait for content to load
        html = await self.fetch_page(
            url,
            wait_for_selector=".content",
        )

        if not html:
            return LegislationItem(
                source_url=url,
                error="Failed to fetch page",
            )

        try:
            parsed = parse_legislation_html(html, url)

            item = LegislationItem.from_parsed(parsed, url, html)

            # Try to find PDF link
            item.pdf_url = self._extract_pdf_url(html, url)

            # Validate we got meaningful data
            if not item.chapter_number and not item.title_en:
                self._log.warning("No chapter or title found", url=url)
                item.error = "Could not extract legislation identifier"

            return item

        except Exception as e:
            self._log.error("Failed to parse legislation", url=url, error=str(e))
            return LegislationItem(
                source_url=url,
                raw_html=html,
                error=str(e),
            )

    def _extract_pdf_url(self, html: str, page_url: str) -> Optional[str]:
        """Extract PDF download URL from legislation page."""
        soup = BeautifulSoup(html, "lxml")

        # Look for PDF links
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if ".pdf" in href.lower():
                return urljoin(page_url, href)

            # Check link text/title
            text = (a.get_text(strip=True) + " " + a.get("title", "")).lower()
            if "pdf" in text or "download" in text:
                return urljoin(page_url, href)

        return None

    async def scrape_chapter(self, chapter: str) -> Optional[LegislationItem]:
        """
        Scrape a specific chapter by number.
        
        Args:
            chapter: Chapter number (e.g., "32" or "32A")
            
        Returns:
            LegislationItem or None if not found
        """
        # Normalize chapter number
        chapter = chapter.upper().replace("CAP.", "").replace("CAP", "").strip()

        url = f"{self.BASE_URL}/hk/cap{chapter}"
        return await self.scrape_item(url)

    async def scrape_section(
        self,
        chapter: str,
        section: str,
    ) -> Optional[LegislationSection]:
        """
        Scrape a specific section of a chapter.
        
        Args:
            chapter: Chapter number
            section: Section number
            
        Returns:
            LegislationSection or None if not found
        """
        # Normalize
        chapter = chapter.upper().replace("CAP.", "").replace("CAP", "").strip()
        section = section.strip()

        url = f"{self.BASE_URL}/hk/cap{chapter}!en@{section}"

        html = await self.fetch_page(url)
        if not html:
            return None

        try:
            parsed = parse_legislation_html(html, url)

            # Find the specific section
            for s in parsed.sections:
                if s.section_number == section:
                    return LegislationSection(
                        section_number=s.section_number,
                        title=s.title,
                        content=s.content,
                        source_url=url,
                    )

            # If not found in parsed sections, return first section
            if parsed.sections:
                s = parsed.sections[0]
                return LegislationSection(
                    section_number=s.section_number,
                    title=s.title,
                    content=s.content,
                    source_url=url,
                )

        except Exception as e:
            self._log.error(
                "Failed to scrape section",
                chapter=chapter,
                section=section,
                error=str(e),
            )

        return None

    async def get_all_chapters(self) -> list[str]:
        """
        Get a list of all chapter numbers.
        
        Returns:
            List of chapter numbers (e.g., ["1", "2", "32", "32A", ...])
        """
        chapters = set()

        async for url in self.get_index_urls():
            # Extract chapter from URL
            import re
            match = re.search(r"/cap(\d+[A-Z]?)", url, re.IGNORECASE)
            if match:
                chapters.add(match.group(1).upper())

        return sorted(chapters, key=lambda x: (int("".join(c for c in x if c.isdigit()) or 0), x))

    async def run_for_chapters(
        self,
        chapters: list[str],
        limit: Optional[int] = None,
    ) -> AsyncIterator[LegislationItem]:
        """
        Run scraper for specific chapters.
        
        Args:
            chapters: List of chapter numbers to scrape
            limit: Optional limit on items
            
        Yields:
            LegislationItem instances
        """
        count = 0

        for chapter in chapters:
            if limit and count >= limit:
                break

            url = f"{self.BASE_URL}/hk/cap{chapter}"

            if self.is_url_processed(url):
                self.mark_url_skipped(url)
                continue

            item = await self.scrape_item(url)
            if item:
                self.mark_url_processed(url, success=item.is_valid(), error=item.error)
                if item.is_valid():
                    count += 1
                    yield item
