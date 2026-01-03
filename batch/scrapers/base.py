"""
Base scraper class with rate limiting, logging, and resume capability.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, date
from pathlib import Path
from typing import AsyncIterator, Optional, Any
import asyncio
import json

import aiofiles
import structlog
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from pydantic import BaseModel, ConfigDict
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

logger = structlog.get_logger(__name__)


class ScraperConfig(BaseModel):
    """Configuration for a scraper instance."""

    base_url: str
    request_delay: float = 3.0  # Minimum seconds between requests
    max_concurrent: int = 2  # Max concurrent browser contexts
    timeout: int = 60000  # Page load timeout in ms
    max_retries: int = 3
    headless: bool = True
    state_file: Optional[str] = None  # Path to state file for resume
    log_file: Optional[str] = None  # Path to log file
    user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )


class ScraperState(BaseModel):
    """Persistent state for resume capability."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    scraper_name: str
    last_run_at: Optional[datetime] = None
    last_successful_url: Optional[str] = None
    last_successful_date: Optional[date] = None
    processed_urls: set[str] = field(default_factory=set)
    failed_urls: dict[str, str] = field(default_factory=dict)  # url -> error message
    stats: dict[str, int] = field(default_factory=lambda: {
        "total_processed": 0,
        "successful": 0,
        "failed": 0,
        "skipped": 0,
    })

    def model_post_init(self, __context: Any) -> None:
        if self.processed_urls is None:
            self.processed_urls = set()
        if self.failed_urls is None:
            self.failed_urls = {}
        if self.stats is None:
            self.stats = {
                "total_processed": 0,
                "successful": 0,
                "failed": 0,
                "skipped": 0,
            }


@dataclass
class ScrapedItem:
    """Base class for scraped items."""

    source_url: str
    scraped_at: datetime = field(default_factory=datetime.utcnow)
    raw_html: Optional[str] = None
    error: Optional[str] = None

    def is_valid(self) -> bool:
        return self.raw_html is not None and self.error is None


class BaseScraper(ABC):
    """
    Abstract base class for web scrapers.
    
    Features:
    - Rate limiting with configurable delays
    - Concurrent request management via semaphore
    - Persistent state for resume capability
    - Structured logging
    - Automatic retries with exponential backoff
    """

    def __init__(self, config: ScraperConfig):
        self.config = config
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._playwright = None
        self._semaphore = asyncio.Semaphore(config.max_concurrent)
        self._last_request_time: float = 0.0
        self._state: Optional[ScraperState] = None
        self._log = logger.bind(scraper=self.__class__.__name__)

    @property
    def name(self) -> str:
        return self.__class__.__name__

    async def __aenter__(self):
        self._log.info("Starting scraper", config=self.config.model_dump())
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.config.headless
        )
        # Create a persistent context to maintain cookies across requests
        self._context = await self._browser.new_context(
            user_agent=self.config.user_agent,
            viewport={"width": 1920, "height": 1080},
            java_script_enabled=True,
        )
        await self._load_state()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._save_state()
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._log.info(
            "Scraper stopped",
            stats=self._state.stats if self._state else None,
        )

    async def _load_state(self) -> None:
        """Load state from file if exists."""
        if not self.config.state_file:
            self._state = ScraperState(scraper_name=self.name)
            return

        state_path = Path(self.config.state_file)
        if state_path.exists():
            try:
                async with aiofiles.open(state_path, "r") as f:
                    data = json.loads(await f.read())
                    # Convert processed_urls list back to set
                    if "processed_urls" in data:
                        data["processed_urls"] = set(data["processed_urls"])
                    self._state = ScraperState(**data)
                    self._log.info(
                        "Loaded state",
                        last_run=self._state.last_run_at,
                        processed_count=len(self._state.processed_urls),
                    )
            except Exception as e:
                self._log.warning("Failed to load state, starting fresh", error=str(e))
                self._state = ScraperState(scraper_name=self.name)
        else:
            self._state = ScraperState(scraper_name=self.name)

    async def _save_state(self) -> None:
        """Save state to file."""
        if not self.config.state_file or not self._state:
            return

        self._state.last_run_at = datetime.utcnow()
        state_path = Path(self.config.state_file)
        state_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            data = self._state.model_dump()
            # Convert set to list for JSON serialization
            data["processed_urls"] = list(data["processed_urls"])
            async with aiofiles.open(state_path, "w") as f:
                await f.write(json.dumps(data, default=str, indent=2))
            self._log.info("Saved state", path=str(state_path))
        except Exception as e:
            self._log.error("Failed to save state", error=str(e))

    async def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request_time
        wait_time = self.config.request_delay - elapsed

        if wait_time > 0:
            self._log.debug("Rate limiting", wait_seconds=wait_time)
            await asyncio.sleep(wait_time)

        self._last_request_time = asyncio.get_event_loop().time()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        retry=retry_if_exception_type((TimeoutError, ConnectionError)),
    )
    async def fetch_page(self, url: str, wait_for_selector: Optional[str] = None) -> Optional[str]:
        """
        Fetch a page with rate limiting and retries.
        
        Uses the persistent browser context to maintain cookies across requests.
        
        Args:
            url: URL to fetch
            wait_for_selector: Optional CSS selector to wait for before returning
            
        Returns:
            HTML content or None if failed
        """
        async with self._semaphore:
            await self._rate_limit()

            page = await self._context.new_page()

            try:
                self._log.info("Fetching page", url=url)
                response = await page.goto(
                    url,
                    wait_until="networkidle",
                    timeout=self.config.timeout,
                )

                if response and response.status >= 400:
                    self._log.warning(
                        "HTTP error",
                        url=url,
                        status=response.status,
                    )
                    return None

                if wait_for_selector:
                    await page.wait_for_selector(
                        wait_for_selector,
                        timeout=self.config.timeout,
                    )

                content = await page.content()
                self._log.debug("Page fetched", url=url, content_length=len(content))
                return content

            except Exception as e:
                self._log.error("Failed to fetch page", url=url, error=str(e))
                raise

            finally:
                await page.close()

    def is_url_processed(self, url: str) -> bool:
        """Check if URL has already been processed."""
        return self._state and url in self._state.processed_urls

    def mark_url_processed(self, url: str, success: bool, error: Optional[str] = None) -> None:
        """Mark a URL as processed."""
        if not self._state:
            return

        self._state.processed_urls.add(url)
        self._state.stats["total_processed"] += 1

        if success:
            self._state.stats["successful"] += 1
            self._state.last_successful_url = url
        else:
            self._state.stats["failed"] += 1
            if error:
                self._state.failed_urls[url] = error

    def mark_url_skipped(self, url: str) -> None:
        """Mark a URL as skipped (e.g., already processed)."""
        if self._state:
            self._state.stats["skipped"] += 1

    def should_resume_from_date(self, item_date: date) -> bool:
        """Check if we should process items from this date based on resume state."""
        if not self._state or not self._state.last_successful_date:
            return True
        return item_date >= self._state.last_successful_date

    def update_last_successful_date(self, item_date: date) -> None:
        """Update the last successful date for resume capability."""
        if self._state:
            self._state.last_successful_date = item_date

    async def run(
        self,
        resume_from_date: Optional[date] = None,
        limit: Optional[int] = None,
    ) -> AsyncIterator[ScrapedItem]:
        """
        Run the scraper.
        
        Args:
            resume_from_date: Optional date to resume from (overrides state)
            limit: Optional limit on number of items to scrape
            
        Yields:
            ScrapedItem instances
        """
        count = 0
        
        async for url in self.get_index_urls():
            if limit and count >= limit:
                self._log.info("Reached limit", limit=limit)
                break

            if self.is_url_processed(url):
                self._log.debug("Skipping processed URL", url=url)
                self.mark_url_skipped(url)
                continue

            try:
                item = await self.scrape_item(url)
                if item:
                    if item.is_valid():
                        self.mark_url_processed(url, success=True)
                        count += 1
                        yield item
                    else:
                        self.mark_url_processed(url, success=False, error=item.error)
                else:
                    self.mark_url_processed(url, success=False, error="No item returned")

            except Exception as e:
                self._log.error("Error scraping item", url=url, error=str(e))
                self.mark_url_processed(url, success=False, error=str(e))

            # Periodically save state
            if count % 10 == 0:
                await self._save_state()

    @abstractmethod
    async def get_index_urls(self) -> AsyncIterator[str]:
        """
        Generate URLs to scrape.
        
        Yields:
            URLs to scrape
        """
        pass

    @abstractmethod
    async def scrape_item(self, url: str) -> Optional[ScrapedItem]:
        """
        Scrape a single item.
        
        Args:
            url: URL to scrape
            
        Returns:
            ScrapedItem or None if failed
        """
        pass
