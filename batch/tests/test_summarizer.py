"""Tests for the summarizer module."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pipeline.summarizer import (
    HEADNOTE_TEMPLATE,
    _build_prompt,
)


class TestHeadnoteTemplate:
    """Tests for the headnote template."""

    def test_template_contains_required_sections(self):
        assert "Citation:" in HEADNOTE_TEMPLATE
        assert "Court:" in HEADNOTE_TEMPLATE
        assert "Procedural posture:" in HEADNOTE_TEMPLATE
        assert "Issues:" in HEADNOTE_TEMPLATE
        assert "Holdings:" in HEADNOTE_TEMPLATE
        assert "Legal principles:" in HEADNOTE_TEMPLATE
        assert "Disposition:" in HEADNOTE_TEMPLATE
        assert "Key citations:" in HEADNOTE_TEMPLATE

    def test_template_has_placeholders(self):
        assert "{few_shots}" in HEADNOTE_TEMPLATE
        assert "{judgment_text}" in HEADNOTE_TEMPLATE

    def test_template_has_guidelines(self):
        assert "Guidelines:" in HEADNOTE_TEMPLATE
        assert "points of law" in HEADNOTE_TEMPLATE
        assert "neutral, formal style" in HEADNOTE_TEMPLATE


class TestBuildPrompt:
    """Tests for prompt building."""

    def test_includes_judgment_text(self):
        judgment = "This is the judgment text."
        prompt = _build_prompt(judgment, [])
        
        assert judgment in prompt

    def test_includes_few_shots(self):
        few_shots = ["Example headnote 1", "Example headnote 2"]
        prompt = _build_prompt("Judgment", few_shots)
        
        assert "Example headnote 1" in prompt
        assert "Example headnote 2" in prompt

    def test_numbers_examples(self):
        few_shots = ["First example", "Second example"]
        prompt = _build_prompt("Judgment", few_shots)
        
        assert "[EXAMPLE 1]" in prompt
        assert "[EXAMPLE 2]" in prompt

    def test_empty_few_shots(self):
        prompt = _build_prompt("Judgment text", [])
        
        assert "Judgment text" in prompt
        # Should still be valid prompt
        assert "Citation:" in prompt

    def test_preserves_judgment_markers(self):
        prompt = _build_prompt("Test judgment", [])
        
        assert "[Judgment text begins]" in prompt
        assert "[Judgment text ends]" in prompt


class TestGenerateHeadnote:
    """Tests for headnote generation (mocked)."""

    @pytest.mark.asyncio
    async def test_returns_none_for_missing_case(self):
        with patch("pipeline.summarizer._get_db_connection") as mock_conn:
            mock_connection = AsyncMock()
            mock_connection.fetchrow.return_value = None
            mock_connection.close = AsyncMock()
            mock_conn.return_value = mock_connection
            
            from pipeline.summarizer import generate_headnote
            result = await generate_headnote("nonexistent-id")
            
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_empty_full_text(self):
        with patch("pipeline.summarizer._get_db_connection") as mock_conn:
            mock_connection = AsyncMock()
            mock_connection.fetchrow.return_value = {
                "id": "123",
                "neutral_citation": "[2024] HKCFA 1",
                "case_name": "Test Case",
                "full_text": "",
                "court_code": "CFA",
            }
            mock_connection.close = AsyncMock()
            mock_conn.return_value = mock_connection
            
            from pipeline.summarizer import generate_headnote
            result = await generate_headnote("123")
            
            assert result is None

    @pytest.mark.asyncio
    async def test_truncates_long_text(self):
        with patch("pipeline.summarizer._get_db_connection") as mock_conn, \
             patch("pipeline.summarizer._azure_openai_client") as mock_azure, \
             patch("pipeline.summarizer.get_settings") as mock_settings:
            
            mock_connection = AsyncMock()
            mock_connection.fetchrow.return_value = {
                "id": "123",
                "neutral_citation": "[2024] HKCFA 1",
                "case_name": "Test Case",
                "full_text": "A" * 200000,  # Very long text
                "court_code": "CFA",
            }
            mock_connection.fetch.return_value = []
            mock_connection.close = AsyncMock()
            mock_conn.return_value = mock_connection
            
            mock_settings_obj = MagicMock()
            mock_settings_obj.headnote_model = "azure-gpt-4o"
            mock_settings_obj.azure_openai_gpt4o_deployment = "gpt-4o"
            mock_settings.return_value = mock_settings_obj
            
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock(message=MagicMock(content="Generated headnote"))]
            mock_client.chat.completions.create.return_value = mock_response
            mock_azure.return_value = mock_client
            
            from pipeline.summarizer import generate_headnote
            result = await generate_headnote("123", max_chars=1000)
            
            # Verify the prompt was built with truncated text
            call_args = mock_client.chat.completions.create.call_args
            messages = call_args.kwargs.get("messages", call_args[1].get("messages", []))
            prompt_content = messages[0]["content"]
            
            # The full 200000 char text should not be in the prompt
            assert "A" * 200000 not in prompt_content


class TestFewShotRetrieval:
    """Tests for few-shot example retrieval."""

    @pytest.mark.asyncio
    async def test_fetches_from_headnote_corpus(self):
        with patch("pipeline.summarizer._get_db_connection") as mock_conn:
            mock_connection = AsyncMock()
            mock_connection.fetch.return_value = [
                {"headnote_text": "Example 1"},
                {"headnote_text": "Example 2"},
            ]
            mock_conn.return_value = mock_connection
            
            from pipeline.summarizer import _fetch_dynamic_few_shots
            result = await _fetch_dynamic_few_shots(mock_connection, subject_limit=2)
            
            assert len(result) == 2
            assert "Example 1" in result
            assert "Example 2" in result

    @pytest.mark.asyncio
    async def test_respects_subject_limit(self):
        with patch("pipeline.summarizer._get_db_connection") as mock_conn:
            mock_connection = AsyncMock()
            mock_connection.fetch.return_value = [
                {"headnote_text": "Example 1"},
            ]
            mock_conn.return_value = mock_connection
            
            from pipeline.summarizer import _fetch_dynamic_few_shots
            await _fetch_dynamic_few_shots(mock_connection, subject_limit=1)
            
            call_args = mock_connection.fetch.call_args
            assert call_args[0][1] == 1  # LIMIT parameter
