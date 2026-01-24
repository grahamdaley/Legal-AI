"""Integration tests for scrapers."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from scrapers.base import ScraperConfig, ScraperState
from scrapers.judiciary import JudiciaryScraper, JudiciaryCase
from scrapers.judiciary.parsers import parse_judgment_html
from scrapers.elegislation import ELegislationScraper, LegislationItem
from scrapers.elegislation.parsers import parse_legislation_html, parse_sitemap_xml


class TestScraperConfig:
    """Tests for scraper configuration."""

    def test_default_config(self):
        config = ScraperConfig(base_url="https://example.com")
        
        assert config.request_delay == 3.0
        assert config.max_concurrent == 2
        assert config.headless is True

    def test_custom_config(self):
        config = ScraperConfig(
            base_url="https://example.com",
            request_delay=5.0,
            max_concurrent=1,
            headless=False,
        )
        
        assert config.request_delay == 5.0
        assert config.max_concurrent == 1
        assert config.headless is False


class TestScraperState:
    """Tests for scraper state management."""

    def test_initial_state(self):
        state = ScraperState(scraper_name="TestScraper")
        
        assert state.scraper_name == "TestScraper"
        assert state.last_run_at is None
        assert len(state.processed_urls) == 0
        assert state.stats["total_processed"] == 0

    def test_state_serialization(self):
        state = ScraperState(scraper_name="TestScraper")
        state.processed_urls.add("https://example.com/1")
        state.stats["successful"] = 1
        
        data = state.model_dump()
        
        assert "https://example.com/1" in data["processed_urls"]
        assert data["stats"]["successful"] == 1


class TestJudiciaryCoramParsing:
    """Tests for extracting judge names from coram text."""

    def test_extract_judges_comma_separated_with_period_titles(self):
        """Test parsing comma-separated judges with period-containing titles like V.-P., J.A."""
        from scrapers.judiciary.parsers import _extract_judges_from_coram
        
        result = _extract_judges_from_coram("Hon. Leonard, V.-P., Cons, Fuad, J. A.")
        assert result == ["Leonard", "Cons", "Fuad"]

    def test_extract_judges_with_full_titles(self):
        """Test parsing judges with full titles like Mr Justice."""
        from scrapers.judiciary.parsers import _extract_judges_from_coram
        
        result = _extract_judges_from_coram(
            "Mr Justice Ribeiro PJ, Mr Justice Fok PJ and Mr Justice Tang PJ"
        )
        assert result == ["Ribeiro", "Fok", "Tang"]

    def test_extract_judges_abbreviated_titles(self):
        """Test parsing judges with abbreviated titles like CJHC, VP, JA."""
        from scrapers.judiciary.parsers import _extract_judges_from_coram
        
        result = _extract_judges_from_coram("Cheung CJHC, Lam VP and Barma JA")
        assert result == ["Cheung", "Lam", "Barma"]

    def test_extract_judges_chief_justice(self):
        """Test parsing The Honourable Chief Justice."""
        from scrapers.judiciary.parsers import _extract_judges_from_coram
        
        result = _extract_judges_from_coram("The Honourable Chief Justice Ma")
        assert result == ["Ma"]

    def test_extract_judges_simple_hon(self):
        """Test parsing simple Hon. prefix."""
        from scrapers.judiciary.parsers import _extract_judges_from_coram
        
        result = _extract_judges_from_coram("Hon. LIU")
        assert result == ["LIU"]

    def test_extract_judges_with_coram_prefix(self):
        """Test that Coram: prefix is stripped."""
        from scrapers.judiciary.parsers import _extract_judges_from_coram
        
        result = _extract_judges_from_coram("Coram: Mr Justice Chan PJ")
        assert result == ["Chan"]

    def test_extract_judges_npj_title(self):
        """Test parsing Non-Permanent Judge (NPJ) title."""
        from scrapers.judiciary.parsers import _extract_judges_from_coram
        
        result = _extract_judges_from_coram("Lord Hoffmann NPJ and Sir Anthony Mason NPJ")
        assert result == ["Lord Hoffmann", "Sir Anthony Mason"]

    def test_extract_judges_empty_input(self):
        """Test empty input returns empty list."""
        from scrapers.judiciary.parsers import _extract_judges_from_coram
        
        result = _extract_judges_from_coram("")
        assert result == []


class TestJudiciaryParser:
    """Tests for Judiciary HTML parsing."""

    def test_parse_citation(self):
        html = """
        <html>
        <head><title>HKSAR v. Chan Tai Man [2024] HKCFA 15</title></head>
        <body>
        <p>In [2024] HKCFA 15, the Court of Final Appeal held...</p>
        </body>
        </html>
        """
        
        result = parse_judgment_html(html, "https://example.com/judgment")
        
        assert result.neutral_citation == "[2024] HKCFA 15"
        assert result.court == "HKCFA"

    def test_parse_case_name(self):
        html = """
        <html>
        <head><title>HKSAR v. Chan Tai Man</title></head>
        <body></body>
        </html>
        """
        
        result = parse_judgment_html(html, "https://example.com/judgment")
        
        assert "HKSAR" in result.case_name or "Chan" in result.case_name

    def test_parse_full_text(self):
        html = """
        <html>
        <body>
        <p>This is the judgment text.</p>
        <p>It contains multiple paragraphs.</p>
        </body>
        </html>
        """
        
        result = parse_judgment_html(html, "https://example.com/judgment")
        
        assert "judgment text" in result.full_text
        assert result.word_count > 0


class TestELegislationParser:
    """Tests for eLegislation HTML parsing."""

    def test_parse_chapter_from_url(self):
        html = "<html><body></body></html>"
        
        result = parse_legislation_html(html, "https://www.elegislation.gov.hk/hk/cap32")
        
        assert result.chapter_number == "Cap. 32"

    def test_parse_sitemap(self):
        xml = """
        <?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url><loc>https://www.elegislation.gov.hk/hk/cap32</loc></url>
            <url><loc>https://www.elegislation.gov.hk/hk/cap571</loc></url>
            <url><loc>https://www.elegislation.gov.hk/about</loc></url>
        </urlset>
        """
        
        urls = parse_sitemap_xml(xml)
        
        # Should only include cap URLs
        assert len(urls) == 2
        assert all("/cap" in url for url in urls)


class TestJudiciaryScraper:
    """Tests for Judiciary scraper."""

    @pytest.mark.asyncio
    async def test_scraper_initialization(self):
        config = ScraperConfig(
            base_url="https://legalref.judiciary.hk",
            request_delay=1.0,
        )
        
        scraper = JudiciaryScraper(config)
        
        assert scraper.config.base_url == "https://legalref.judiciary.hk"

    def test_judiciary_case_from_parsed(self):
        from scrapers.judiciary.parsers import ParsedJudgment
        from datetime import date
        
        parsed = ParsedJudgment(
            neutral_citation="[2024] HKCFA 15",
            case_name="HKSAR v. Test",
            court="HKCFA",
            decision_date=date(2024, 6, 15),
            full_text="Test judgment text",
            word_count=3,
        )
        
        case = JudiciaryCase.from_parsed(parsed, "https://example.com", "<html></html>")
        
        assert case.neutral_citation == "[2024] HKCFA 15"
        assert case.case_name == "HKSAR v. Test"
        assert case.is_valid()


class TestELegislationScraper:
    """Tests for eLegislation scraper."""

    @pytest.mark.asyncio
    async def test_scraper_initialization(self):
        config = ScraperConfig(
            base_url="https://www.elegislation.gov.hk",
            request_delay=1.0,
        )
        
        scraper = ELegislationScraper(config)
        
        assert scraper.config.base_url == "https://www.elegislation.gov.hk"

    def test_legislation_item_from_parsed(self):
        from scrapers.elegislation.parsers import ParsedLegislation, ParsedSection
        
        parsed = ParsedLegislation(
            chapter_number="Cap. 32",
            title_en="Evidence Ordinance",
            type="ordinance",
            sections=[
                ParsedSection(section_number="1", title="Short title", content="Test")
            ],
        )
        
        item = LegislationItem.from_parsed(parsed, "https://example.com", "<html></html>")
        
        assert item.chapter_number == "Cap. 32"
        assert item.title_en == "Evidence Ordinance"
        assert len(item.sections) == 1
        assert item.is_valid()
