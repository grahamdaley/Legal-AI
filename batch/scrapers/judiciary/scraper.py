"""
Hong Kong Judiciary scraper for legalref.judiciary.hk

Scrapes court judgments from the Legal Reference System.

IMPORTANT: The Judiciary website's robots.txt disallows automated access.
This scraper should only be used with proper authorization or for testing.
Implement strict rate limiting (3+ second delays) if authorized.
"""

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import AsyncIterator, Optional
from urllib.parse import urljoin, urlencode, urlparse, parse_qs

from bs4 import BeautifulSoup
import structlog

from ..base import BaseScraper, ScrapedItem, ScraperConfig
from .config import COURTS, COURT_HIERARCHY, JudiciaryConfig
from .parsers import parse_judgment_html, ParsedJudgment, extract_pdf_text
from ..utils.citation_parser import parse_hk_citations, extract_case_number

logger = structlog.get_logger(__name__)


@dataclass
class JudiciaryCase(ScrapedItem):
    """Scraped case from the Judiciary website."""

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
    pdf_url: Optional[str] = None

    @classmethod
    def from_parsed(cls, parsed: ParsedJudgment, source_url: str, raw_html: str) -> "JudiciaryCase":
        """Create from parsed judgment data."""
        return cls(
            source_url=source_url,
            raw_html=raw_html,
            neutral_citation=parsed.neutral_citation,
            case_number=parsed.case_number,
            case_name=parsed.case_name,
            court=parsed.court,
            decision_date=parsed.decision_date,
            judges=parsed.judges,
            parties=parsed.parties,
            headnote=parsed.headnote,
            catchwords=parsed.catchwords,
            full_text=parsed.full_text,
            word_count=parsed.word_count,
            language=parsed.language,
            cited_cases=parsed.cited_cases,
        )


class JudiciaryScraper(BaseScraper):
    """
    Scraper for Hong Kong Judiciary Legal Reference System.
    
    The LRS provides access to court judgments from various HK courts.
    This scraper navigates the search interface to discover and download
    judgment documents.
    
    Usage:
        config = ScraperConfig(
            base_url="https://legalref.judiciary.hk",
            request_delay=3.0,
            state_file="./state/judiciary_state.json",
        )
        async with JudiciaryScraper(config) as scraper:
            async for case in scraper.run(resume_from_date=date(2024, 1, 1)):
                print(case.neutral_citation)
    """

    BASE_URL = "https://legalref.judiciary.hk"

    def __init__(
        self,
        config: Optional[ScraperConfig] = None,
        judiciary_config: Optional[JudiciaryConfig] = None,
    ):
        if config is None:
            config = ScraperConfig(
                base_url=self.BASE_URL,
                request_delay=3.0,
                max_concurrent=2,
            )
        super().__init__(config)

        self.judiciary_config = judiciary_config or JudiciaryConfig()
        self._log = logger.bind(scraper="JudiciaryScraper")
        self._session_initialized = False

    async def _ensure_session(self) -> None:
        """
        Initialize session by visiting the main page first.
        
        The LRS requires cookies/session to be established before
        search queries will work properly.
        """
        if self._session_initialized:
            return
        
        self._log.info("Initializing session with main page")
        init_url = f"{self.config.base_url}/lrs/common/ju/judgment.jsp"
        await self.fetch_page(init_url)
        self._session_initialized = True
        self._log.info("Session initialized")

    async def get_index_urls(
        self,
        courts: Optional[list[str]] = None,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
    ) -> AsyncIterator[str]:
        """
        Generate URLs for all judgments matching criteria.
        
        This method iterates through each day in the date range to discover
        judgment URLs via the LRS search interface.
        
        Args:
            courts: List of court codes to scrape (not used - searches all courts)
            year_from: Start year (default: from config)
            year_to: End year (default: from config)
            
        Yields:
            URLs to individual judgment detail pages
        """
        # Ensure session is initialized before making search requests
        await self._ensure_session()
        
        year_from = year_from or self.judiciary_config.start_year
        year_to = year_to or self.judiciary_config.end_year

        self._log.info(
            "Starting index generation by date",
            year_from=year_from,
            year_to=year_to,
        )

        # Iterate through each day in the date range
        start_date = date(year_from, 1, 1)
        end_date = date(year_to, 12, 31)
        
        # Don't go beyond today
        today = date.today()
        if end_date > today:
            end_date = today

        current_date = start_date
        while current_date <= end_date:
            try:
                async for url in self._get_judgments_for_date(current_date):
                    yield url
            except Exception as e:
                self._log.error(
                    "Failed to index date",
                    date=str(current_date),
                    error=str(e),
                )
            
            current_date += timedelta(days=1)

    async def _get_judgments_for_date(self, search_date: date) -> AsyncIterator[str]:
        """
        Get all judgment URLs for a specific date.
        
        Handles pagination through search results for the given date.
        
        Args:
            search_date: The date to search for judgments
            
        Yields:
            URLs to judgment detail pages
        """
        page = 1
        total_pages = 1
        
        while page <= total_pages:
            search_url = self._build_search_url_for_date(
                day=search_date.day,
                month=search_date.month,
                year=search_date.year,
                page=page,
            )

            html = await self.fetch_page(search_url)
            if not html:
                break

            soup = BeautifulSoup(html, "lxml")
            
            # Check for "no results" 
            if "No record found" in html or "0</span>&nbsp; found" in html:
                self._log.debug("No judgments for date", date=str(search_date))
                break
            
            # Extract total pages on first page
            if page == 1:
                total_pages = self._extract_total_pages(soup)
                if total_pages > 0:
                    self._log.info(
                        "Found judgments for date",
                        date=str(search_date),
                        total_pages=total_pages,
                    )

            # Extract judgment detail URLs
            judgment_urls = self._extract_judgment_detail_urls(soup)

            if not judgment_urls:
                break

            for url in judgment_urls:
                yield url

            page += 1
    
    def _extract_total_pages(self, soup: BeautifulSoup) -> int:
        """Extract total number of pages from search results."""
        # Look for "Total Pages: X" text
        total_pages_span = soup.find("span", id="searchresult-totalpages")
        if total_pages_span:
            try:
                return int(total_pages_span.get_text(strip=True))
            except ValueError:
                pass
        
        # Fallback: count pagination links
        pagination = soup.find("ul", class_="pagination")
        if pagination:
            page_links = pagination.find_all("li", class_="page-item")
            return len(page_links)
        
        return 1
    
    def _extract_judgment_detail_urls(self, soup: BeautifulSoup) -> list[str]:
        """
        Extract judgment detail page URLs from search results.
        
        The search results contain JavaScript variables with DIS IDs like:
        var temp32205='DIS=32205&QS=%2B&TP=JU'
        
        We construct the detail URL from these.
        """
        urls = []
        
        # Find all DIS IDs from JavaScript variables
        # Pattern: var tempXXXX='DIS=XXXX&QS=%2B&TP=JU'
        html_text = str(soup)
        dis_pattern = r"var\s+temp\d+='DIS=(\d+)&"
        matches = re.findall(dis_pattern, html_text)
        
        for dis_id in matches:
            # Construct the detail body URL (not the frame, which just contains iframes)
            detail_url = (
                f"{self.config.base_url}/lrs/common/search/"
                f"search_result_detail_body.jsp?DIS={dis_id}&QS=%2B&TP=JU"
            )
            if detail_url not in urls:
                urls.append(detail_url)
        
        return urls

    def _build_search_url_for_date(self, day: int, month: int, year: int, page: int = 1) -> str:
        """
        Build search URL for judgments on a specific date.
        
        The LRS search interface allows searching by date of judgment.
        We iterate through each day to discover all judgments.
        
        Args:
            day: Day of month (1-31)
            month: Month (1-12)
            year: Year (e.g., 2024)
            page: Page number for pagination
            
        Returns:
            Full search URL
        """
        params = {
            "isadvsearch": "1",
            "txtselectopt": "1",
            "txtSearch": "",
            "txtselectopt1": "2",
            "txtSearch1": "",
            "txtselectopt2": "3",
            "txtSearch2": "",
            "stem": "1",
            "txtselectopt3": "5",
            "txtSearch3": f"{day}/{month}/{year}",
            "day1": str(day),
            "month": str(month),
            "year": str(year),
            "txtselectopt4": "6",
            "txtSearch4": "",
            "txtselectopt5": "7",
            "txtSearch5": "",
            "txtselectopt6": "8",
            "txtSearch6": "",
            "txtselectopt7": "9",
            "txtSearch7": "",
            "selallct": "1",
            "selSchct": ["FA", "CA", "HC", "CT", "DC", "FC", "LD", "OT"],
            "selcourtname": "",
            "selcourtype": "",
            "txtselectopt8": "10",
            "txtSearch8": "",
            "txtselectopt9": "4",
            "txtSearch9": "",
            "txtselectopt10": "12",
            "txtSearch10": "",
            "selall2": "1",
            "selDatabase2": ["JU", "RV", "RS", "PD"],
            "order": "1",
            "SHC": "",
            "page": str(page),
        }
        
        # Build query string manually to handle multiple values for same key
        query_parts = []
        for key, value in params.items():
            if isinstance(value, list):
                for v in value:
                    query_parts.append(f"{key}={v}")
            else:
                query_parts.append(f"{key}={value}")
        
        query_string = "&".join(query_parts)
        return f"{self.config.base_url}/lrs/common/search/search_result_form.jsp?{query_string}"

    def _extract_judgment_links(self, soup: BeautifulSoup) -> list[str]:
        """Extract judgment URLs from search results page."""
        links = []

        # Look for links to judgment pages
        # Common patterns in legal databases
        for a in soup.find_all("a", href=True):
            href = a["href"]

            # Match judgment URL patterns
            if any(pattern in href.lower() for pattern in [
                "judgment", "decision", "ruling",
                "ju_frame", "case_no", "casenumber",
            ]):
                links.append(href)

            # Match by file extension
            if href.endswith(".htm") or href.endswith(".html"):
                if "search" not in href.lower() and "index" not in href.lower():
                    links.append(href)

        # Deduplicate while preserving order
        seen = set()
        unique_links = []
        for link in links:
            if link not in seen:
                seen.add(link)
                unique_links.append(link)

        return unique_links

    def _has_next_page(self, soup: BeautifulSoup) -> bool:
        """Check if there's a next page of results."""
        # Look for pagination elements
        next_patterns = ["next", "»", "›", "下一頁"]

        for pattern in next_patterns:
            next_link = soup.find("a", string=lambda s: s and pattern in s.lower() if s else False)
            if next_link:
                return True

        # Check for page numbers
        pagination = soup.find(class_=lambda c: c and "pag" in c.lower() if c else False)
        if pagination:
            current = pagination.find(class_=lambda c: c and ("active" in c.lower() or "current" in c.lower()) if c else False)
            if current:
                next_sibling = current.find_next_sibling("a")
                if next_sibling:
                    return True

        return False

    async def scrape_item(self, url: str) -> Optional[JudiciaryCase]:
        """
        Scrape a single judgment page.
        
        Args:
            url: URL to the judgment page
            
        Returns:
            JudiciaryCase with extracted data, or None if failed
        """
        self._log.info("Scraping judgment", url=url)

        html = await self.fetch_page(url)
        if not html:
            return JudiciaryCase(
                source_url=url,
                error="Failed to fetch page",
            )

        try:
            parsed = parse_judgment_html(html, url)

            case = JudiciaryCase.from_parsed(parsed, url, html)

            # Try to find PDF link
            case.pdf_url = self._extract_pdf_url(html, url)

            # If we still don't have an identifier but there is a PDF, try to enrich from PDF text
            if not case.case_number and not case.neutral_citation and case.pdf_url:
                await self._enrich_from_pdf(case)

            # Validate we got meaningful data (case_number is most reliable)
            if not case.case_number and not case.neutral_citation:
                self._log.warning("No case number or citation found", url=url)
                case.error = "Could not extract case identifier"

            return case

        except Exception as e:
            self._log.error("Failed to parse judgment", url=url, error=str(e))
            return JudiciaryCase(
                source_url=url,
                raw_html=html,
                error=str(e),
            )

    def _extract_pdf_url(self, html: str, page_url: str) -> Optional[str]:
        """Extract PDF download URL from judgment page."""
        soup = BeautifulSoup(html, "lxml")

        # Look for PDF links
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if ".pdf" in href.lower():
                return urljoin(page_url, href)

            # Check link text
            text = a.get_text(strip=True).lower()
            if "pdf" in text or "download" in text:
                return urljoin(page_url, href)

        return None

    async def _fetch_pdf(self, url: str) -> Optional[bytes]:
        """Fetch a PDF using the shared browser context."""
        async with self._semaphore:
            await self._rate_limit()

            page = await self._context.new_page()
            try:
                self._log.info("Fetching PDF", url=url)
                response = await page.goto(
                    url,
                    wait_until="networkidle",
                    timeout=self.config.timeout,
                )

                if not response or response.status >= 400:
                    self._log.warning(
                        "HTTP error when fetching PDF",
                        url=url,
                        status=response.status if response else None,
                    )
                    return None

                return await response.body()

            except Exception as e:
                self._log.error("Failed to fetch PDF", url=url, error=str(e))
                return None

            finally:
                await page.close()

    async def _enrich_from_pdf(self, case: JudiciaryCase) -> None:
        """Download the PDF and try to recover identifiers from its text."""
        if not case.pdf_url:
            return

        try:
            pdf_bytes = await self._fetch_pdf(case.pdf_url)
            if not pdf_bytes:
                return

            text = extract_pdf_text(pdf_bytes)
            if not text:
                return

            # Try to fill in missing case number
            if not case.case_number:
                cn = extract_case_number(text)
                if cn:
                    case.case_number = cn

            # Try to fill in missing neutral citation
            if not case.neutral_citation:
                citations = parse_hk_citations(text)
                if citations:
                    primary = citations[0]
                    case.neutral_citation = primary.full_citation
                    if not case.court:
                        case.court = primary.court

        except Exception as e:
            self._log.error("Failed to enrich from PDF", url=case.pdf_url, error=str(e))

    async def scrape_by_citation(self, citation: str) -> Optional[JudiciaryCase]:
        """
        Scrape a specific case by its neutral citation.
        
        Args:
            citation: Neutral citation (e.g., "[2024] HKCFA 15")
            
        Returns:
            JudiciaryCase or None if not found
        """
        # Build search URL for specific citation
        params = {"citation": citation}
        search_url = f"{self.config.base_url}/lrs/common/search/search_result.jsp?{urlencode(params)}"

        html = await self.fetch_page(search_url)
        if not html:
            return None

        soup = BeautifulSoup(html, "lxml")
        links = self._extract_judgment_links(soup)

        if links:
            judgment_url = urljoin(self.config.base_url, links[0])
            return await self.scrape_item(judgment_url)

        return None

    async def run_for_court(
        self,
        court: str,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> AsyncIterator[JudiciaryCase]:
        """
        Run scraper for a specific court.
        
        Convenience method for scraping a single court.
        """
        count = 0
        async for url in self.get_index_urls(
            courts=[court],
            year_from=year_from,
            year_to=year_to,
        ):
            if limit and count >= limit:
                break

            if self.is_url_processed(url):
                self.mark_url_skipped(url)
                continue

            case = await self.scrape_item(url)
            if case:
                self.mark_url_processed(url, success=case.is_valid(), error=case.error)
                if case.is_valid():
                    count += 1
                    yield case
