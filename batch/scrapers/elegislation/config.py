"""
Configuration for Hong Kong eLegislation scraper.
"""

from pydantic import BaseModel


class ELegislationConfig(BaseModel):
    """Configuration specific to eLegislation scraper."""

    base_url: str = "https://www.elegislation.gov.hk"
    sitemap_url: str = "https://www.elegislation.gov.hk/sitemapindex.xml"
    request_delay: float = 3.0
    max_concurrent: int = 2
    timeout: int = 60000
    max_retries: int = 3
    headless: bool = True

    # Scraping parameters
    include_subsidiary: bool = True  # Include subsidiary legislation
    include_historical: bool = False  # Include historical versions
    languages: list[str] = ["en", "zh"]  # Languages to scrape


# Legislation types
LEGISLATION_TYPES = {
    "ordinance": "Primary Legislation (Ordinance)",
    "regulation": "Subsidiary Legislation (Regulation)",
    "rule": "Subsidiary Legislation (Rules)",
    "order": "Subsidiary Legislation (Order)",
    "notice": "Subsidiary Legislation (Notice)",
    "bylaw": "Subsidiary Legislation (By-law)",
}

# Common chapter ranges for Hong Kong legislation
# Cap. 1-600+ are ordinances, subsidiary legislation follows
CHAPTER_RANGES = {
    "primary": (1, 700),
    "subsidiary": (1, 700),  # Each chapter can have subsidiary legislation
}
