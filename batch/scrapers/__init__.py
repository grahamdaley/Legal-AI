"""
Legal AI Web Scrapers

Scrapers for Hong Kong legal data sources:
- Judiciary (legalref.judiciary.hk) - Court judgments
- eLegislation (elegislation.gov.hk) - Legislation
"""

from .base import BaseScraper, ScraperConfig, ScrapedItem, ScraperState

__all__ = ["BaseScraper", "ScraperConfig", "ScrapedItem", "ScraperState"]
