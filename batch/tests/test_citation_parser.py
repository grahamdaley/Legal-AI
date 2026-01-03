"""Tests for citation parser utilities."""

import pytest
from scrapers.utils.citation_parser import (
    parse_hk_citations,
    parse_uk_citations,
    normalize_citation,
    extract_case_number,
    get_court_hierarchy,
)


class TestHKCitationParser:
    """Tests for Hong Kong citation parsing."""

    def test_parse_basic_citation(self):
        text = "The case [2024] HKCFA 15 established important principles."
        citations = parse_hk_citations(text)
        
        assert len(citations) == 1
        assert citations[0].full_citation == "[2024] HKCFA 15"
        assert citations[0].year == 2024
        assert citations[0].court == "HKCFA"
        assert citations[0].number == 15
        assert citations[0].jurisdiction == "HK"

    def test_parse_multiple_citations(self):
        text = """
        In [2024] HKCFA 15, the court referred to [2020] HKCA 500 
        and [2019] HKCFI 1234.
        """
        citations = parse_hk_citations(text)
        
        assert len(citations) == 3
        courts = {c.court for c in citations}
        assert courts == {"HKCFA", "HKCA", "HKCFI"}

    def test_parse_lowercase_citation(self):
        text = "See [2024] hkcfa 15 for reference."
        citations = parse_hk_citations(text)
        
        assert len(citations) == 1
        assert citations[0].court == "HKCFA"

    def test_parse_no_citations(self):
        text = "This text contains no legal citations."
        citations = parse_hk_citations(text)
        
        assert len(citations) == 0

    def test_deduplicate_citations(self):
        text = "[2024] HKCFA 15 was cited. See [2024] HKCFA 15 again."
        citations = parse_hk_citations(text)
        
        assert len(citations) == 1


class TestUKCitationParser:
    """Tests for UK citation parsing."""

    def test_parse_uksc_citation(self):
        text = "The Supreme Court in [2024] UKSC 10 held that..."
        citations = parse_uk_citations(text)
        
        assert len(citations) == 1
        assert citations[0].court == "UKSC"
        assert citations[0].jurisdiction == "UK"

    def test_parse_ewca_citation(self):
        text = "See [2023] EWCA Civ 500 for the Court of Appeal decision."
        citations = parse_uk_citations(text)
        
        assert len(citations) == 1
        assert "EWCA" in citations[0].court

    def test_parse_law_report_citation(self):
        text = "The leading case is [2020] 1 AC 123."
        citations = parse_uk_citations(text)
        
        assert len(citations) == 1
        assert citations[0].volume == 1


class TestNormalizeCitation:
    """Tests for citation normalization."""

    def test_normalize_hk_citation(self):
        assert normalize_citation("[2024] hkcfa 15") == "[2024] HKCFA 15"
        assert normalize_citation("  [2024] HKCA 100  ") == "[2024] HKCA 100"

    def test_normalize_unknown_format(self):
        # Should return as-is if not recognized
        result = normalize_citation("Some random text")
        assert result == "Some random text"


class TestCaseNumber:
    """Tests for case number extraction."""

    def test_extract_facv(self):
        text = "FACV 1/2024"
        result = extract_case_number(text)
        assert result == "FACV 1/2024"

    def test_extract_hcal(self):
        text = "The case HCAL 1234/2023 was heard..."
        result = extract_case_number(text)
        assert result == "HCAL 1234/2023"

    def test_no_case_number(self):
        text = "No case number here"
        result = extract_case_number(text)
        assert result is None


class TestCourtHierarchy:
    """Tests for court hierarchy."""

    def test_cfa_highest(self):
        assert get_court_hierarchy("HKCFA") == 1

    def test_ca_second(self):
        assert get_court_hierarchy("HKCA") == 2

    def test_cfi_third(self):
        assert get_court_hierarchy("HKCFI") == 3

    def test_unknown_court(self):
        # Should return lowest level for unknown
        assert get_court_hierarchy("UNKNOWN") == 5
