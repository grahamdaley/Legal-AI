"""Tests for the chunking module."""

import pytest
from pipeline.chunking import (
    Chunk,
    chunk_case_text,
    chunk_legislation_section,
    _split_into_paragraphs,
    _guess_paragraph_number,
    _group_paragraphs_into_chunks,
)


class TestSplitIntoParagraphs:
    """Tests for paragraph splitting."""

    def test_split_on_blank_lines(self):
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        paras = _split_into_paragraphs(text)
        
        assert len(paras) == 3
        assert paras[0] == "First paragraph."
        assert paras[1] == "Second paragraph."
        assert paras[2] == "Third paragraph."

    def test_split_on_numbered_paragraphs(self):
        text = "[1] First paragraph.\n[2] Second paragraph.\n[3] Third paragraph."
        paras = _split_into_paragraphs(text)
        
        assert len(paras) == 3
        assert "[1]" in paras[0]
        assert "[2]" in paras[1]

    def test_handles_windows_line_endings(self):
        text = "First paragraph.\r\n\r\nSecond paragraph."
        paras = _split_into_paragraphs(text)
        
        assert len(paras) == 2

    def test_handles_mac_line_endings(self):
        text = "First paragraph.\r\rSecond paragraph."
        paras = _split_into_paragraphs(text)
        
        assert len(paras) == 2

    def test_empty_text(self):
        paras = _split_into_paragraphs("")
        assert len(paras) == 0

    def test_whitespace_only(self):
        paras = _split_into_paragraphs("   \n\n   \n   ")
        assert len(paras) == 0

    def test_joins_continuation_lines(self):
        text = "This is a long paragraph\nthat continues on the next line."
        paras = _split_into_paragraphs(text)
        
        assert len(paras) == 1
        assert "paragraph that continues" in paras[0]


class TestGuessParagraphNumber:
    """Tests for paragraph number extraction."""

    def test_bracket_format(self):
        assert _guess_paragraph_number("[1] Some text") == 1
        assert _guess_paragraph_number("[42] More text") == 42
        assert _guess_paragraph_number("[100] Even more") == 100

    def test_parenthesis_format(self):
        assert _guess_paragraph_number("(1) Some text") == 1
        assert _guess_paragraph_number("(25) More text") == 25

    def test_dot_format(self):
        assert _guess_paragraph_number("1. Some text") == 1
        assert _guess_paragraph_number("15. More text") == 15

    def test_no_number(self):
        assert _guess_paragraph_number("Some text without number") is None
        assert _guess_paragraph_number("") is None

    def test_number_not_at_start(self):
        assert _guess_paragraph_number("Text with [1] in middle") is None


class TestGroupParagraphsIntoChunks:
    """Tests for paragraph grouping."""

    def test_single_paragraph_under_limit(self):
        paras = ["Short paragraph."]
        chunks = _group_paragraphs_into_chunks(paras, max_chars=100)
        
        assert len(chunks) == 1
        assert chunks[0] == ["Short paragraph."]

    def test_multiple_paragraphs_fit_in_one_chunk(self):
        paras = ["Para 1.", "Para 2.", "Para 3."]
        chunks = _group_paragraphs_into_chunks(paras, max_chars=100)
        
        assert len(chunks) == 1
        assert len(chunks[0]) == 3

    def test_splits_when_exceeds_limit(self):
        paras = ["A" * 50, "B" * 50, "C" * 50]
        chunks = _group_paragraphs_into_chunks(paras, max_chars=80, overlap_paras=0)
        
        assert len(chunks) >= 2

    def test_overlap_between_chunks(self):
        paras = ["Para 1", "Para 2", "Para 3", "Para 4", "Para 5"]
        chunks = _group_paragraphs_into_chunks(paras, max_chars=20, overlap_paras=1)
        
        # With overlap, some paragraphs should appear in multiple chunks
        all_paras = [p for chunk in chunks for p in chunk]
        assert len(all_paras) >= len(paras)

    def test_handles_huge_single_paragraph(self):
        paras = ["A" * 5000]
        chunks = _group_paragraphs_into_chunks(paras, max_chars=100)
        
        # Should still produce at least one chunk
        assert len(chunks) >= 1
        assert chunks[0][0] == "A" * 5000


class TestChunkCaseText:
    """Tests for case text chunking."""

    def test_creates_chunks_with_correct_doc_type(self):
        case_id = "test-case-123"
        text = "[1] First paragraph.\n\n[2] Second paragraph."
        
        chunks = chunk_case_text(case_id, text)
        
        for chunk in chunks:
            assert chunk.doc_type == "case"
            assert chunk.doc_id == case_id

    def test_assigns_chunk_indices(self):
        case_id = "test-case-123"
        text = "[1] Para 1.\n\n" * 50  # Create enough text for multiple chunks
        
        chunks = chunk_case_text(case_id, text)
        
        indices = [c.chunk_index for c in chunks]
        assert indices == list(range(len(chunks)))

    def test_first_chunk_labeled_facts(self):
        case_id = "test-case-123"
        text = "[1] Background facts.\n\n[2] More facts.\n\n[3] Legal analysis.\n\n[4] Order."
        
        chunks = chunk_case_text(case_id, text)
        
        if len(chunks) > 0:
            assert chunks[0].chunk_type == "facts"

    def test_last_chunk_labeled_order(self):
        case_id = "test-case-123"
        # Create enough text for multiple chunks
        text = "[1] Para.\n\n" * 100 + "[100] Final order."
        
        chunks = chunk_case_text(case_id, text)
        
        if len(chunks) > 1:
            assert chunks[-1].chunk_type == "order"

    def test_middle_chunks_labeled_reasoning(self):
        case_id = "test-case-123"
        text = "[1] Para.\n\n" * 100
        
        chunks = chunk_case_text(case_id, text)
        
        if len(chunks) > 2:
            for chunk in chunks[1:-1]:
                assert chunk.chunk_type == "reasoning"

    def test_extracts_paragraph_numbers(self):
        case_id = "test-case-123"
        text = "[1] First.\n\n[2] Second.\n\n[3] Third."
        
        chunks = chunk_case_text(case_id, text)
        
        all_para_nums = []
        for chunk in chunks:
            if chunk.paragraph_numbers:
                all_para_nums.extend(chunk.paragraph_numbers)
        
        assert 1 in all_para_nums
        assert 2 in all_para_nums
        assert 3 in all_para_nums

    def test_empty_text_returns_empty_list(self):
        chunks = chunk_case_text("test", "")
        assert chunks == []

    def test_whitespace_only_returns_empty_list(self):
        chunks = chunk_case_text("test", "   \n\n   ")
        assert chunks == []


class TestChunkLegislationSection:
    """Tests for legislation section chunking."""

    def test_short_section_single_chunk(self):
        section_id = "section-123"
        content = "This is a short section."
        
        chunks = chunk_legislation_section(section_id, content)
        
        assert len(chunks) == 1
        assert chunks[0].doc_type == "legislation"
        assert chunks[0].doc_id == section_id
        assert chunks[0].chunk_type == "section_body"

    def test_includes_section_path(self):
        section_id = "section-123"
        content = "Section content."
        
        chunks = chunk_legislation_section(
            section_id, content, section_path="Part 1 > s.5"
        )
        
        assert chunks[0].section_path == "Part 1 > s.5"

    def test_long_section_splits(self):
        section_id = "section-123"
        content = ("Paragraph content.\n\n" * 200)  # Create long content
        
        chunks = chunk_legislation_section(section_id, content)
        
        assert len(chunks) > 1
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i

    def test_empty_content_returns_empty_list(self):
        chunks = chunk_legislation_section("test", "")
        assert chunks == []

    def test_whitespace_only_returns_empty_list(self):
        chunks = chunk_legislation_section("test", "   \n\n   ")
        assert chunks == []

    def test_preserves_section_path_across_chunks(self):
        section_id = "section-123"
        content = ("Long paragraph content.\n\n" * 200)
        
        chunks = chunk_legislation_section(
            section_id, content, section_path="Schedule 1"
        )
        
        for chunk in chunks:
            assert chunk.section_path == "Schedule 1"


class TestChunkDataclass:
    """Tests for the Chunk dataclass."""

    def test_chunk_creation(self):
        chunk = Chunk(
            doc_type="case",
            doc_id="123",
            chunk_index=0,
            text="Sample text",
            chunk_type="facts",
        )
        
        assert chunk.doc_type == "case"
        assert chunk.doc_id == "123"
        assert chunk.chunk_index == 0
        assert chunk.text == "Sample text"
        assert chunk.chunk_type == "facts"
        assert chunk.paragraph_numbers is None
        assert chunk.section_path is None

    def test_chunk_with_optional_fields(self):
        chunk = Chunk(
            doc_type="legislation",
            doc_id="456",
            chunk_index=1,
            text="Section text",
            chunk_type="section_body",
            paragraph_numbers=[1, 2, 3],
            section_path="Part 1 > s.5",
        )
        
        assert chunk.paragraph_numbers == [1, 2, 3]
        assert chunk.section_path == "Part 1 > s.5"
