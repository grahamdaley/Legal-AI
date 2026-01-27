"""Tests for the embeddings module."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pipeline.embeddings import (
    _estimate_tokens,
    EmbeddingResult,
    EmbeddingBackend,
    BedrockCohereBackend,
)
from utils.text import truncate_to_token_limit


class TestEstimateTokens:
    """Tests for token estimation."""

    def test_empty_string(self):
        assert _estimate_tokens("") == 0

    def test_short_text(self):
        result = _estimate_tokens("Hello world")
        assert result > 0
        assert result < len("Hello world")

    def test_longer_text(self):
        text = "This is a longer piece of text that should have more tokens."
        result = _estimate_tokens(text)
        assert result == len(text) // 3

    def test_legal_text(self):
        text = "The appellant's contention regarding the interpretation of s.47(1) of the Ordinance..."
        result = _estimate_tokens(text)
        assert result > 0


class TestTruncateToTokenLimit:
    """Tests for text truncation."""

    def test_short_text_unchanged(self):
        text = "Short text"
        result = truncate_to_token_limit(text, max_tokens=1000)
        assert result == text

    def test_long_text_truncated(self):
        text = "A" * 5000
        result = truncate_to_token_limit(text, max_tokens=1000)
        assert len(result) <= 1000

    def test_truncates_at_word_boundary(self):
        text = "word " * 1000  # 5000 chars
        result = truncate_to_token_limit(text, max_tokens=100)
        
        # Should not end mid-word
        assert result.endswith("word") or result.endswith(" ")

    def test_empty_string(self):
        result = truncate_to_token_limit("", max_tokens=100)
        assert result == ""

    def test_exact_limit(self):
        text = "A" * 100
        result = truncate_to_token_limit(text, max_tokens=100)
        assert result == text


class TestEmbeddingResult:
    """Tests for EmbeddingResult dataclass."""

    def test_creation(self):
        result = EmbeddingResult(
            doc_type="case",
            doc_id="123",
            chunk_index=0,
            chunk_type="facts",
            text="Sample text",
            embedding=[0.1, 0.2, 0.3],
        )
        
        assert result.doc_type == "case"
        assert result.doc_id == "123"
        assert result.chunk_index == 0
        assert result.chunk_type == "facts"
        assert result.text == "Sample text"
        assert result.embedding == [0.1, 0.2, 0.3]

    def test_embedding_list(self):
        embedding = [0.1] * 1024
        result = EmbeddingResult(
            doc_type="legislation",
            doc_id="456",
            chunk_index=1,
            chunk_type="section_body",
            text="Section content",
            embedding=embedding,
        )
        
        assert len(result.embedding) == 1024


class TestBedrockCohereBackend:
    """Tests for BedrockCohereBackend."""

    def test_initialization(self):
        backend = BedrockCohereBackend(name="test-backend")
        
        assert backend.name == "test-backend"
        assert backend.model_id == "amazon.titan-embed-text-v2:0"

    def test_custom_model_id(self):
        backend = BedrockCohereBackend(
            name="test-backend",
            model_id="custom-model-id",
        )
        
        assert backend.model_id == "custom-model-id"

    def test_custom_region(self):
        backend = BedrockCohereBackend(
            name="test-backend",
            region_name="us-west-2",
        )
        
        assert backend.region_name == "us-west-2"

    @pytest.mark.asyncio
    async def test_embed_empty_list(self):
        backend = BedrockCohereBackend(name="test-backend")
        result = await backend.embed([])
        
        assert result == []

    @pytest.mark.asyncio
    async def test_embed_calls_bedrock(self):
        backend = BedrockCohereBackend(name="test-backend")
        
        mock_response = {
            "body": MagicMock(
                read=MagicMock(return_value=b'{"embedding": [0.1, 0.2, 0.3]}')
            )
        }
        
        with patch.object(backend, "_client") as mock_client:
            mock_client.return_value.invoke_model.return_value = mock_response
            
            result = await backend.embed(["test text"])
            
            assert len(result) == 1
            assert result[0] == [0.1, 0.2, 0.3]


class TestEmbeddingBackend:
    """Tests for EmbeddingBackend base class."""

    def test_is_abstract(self):
        backend = EmbeddingBackend(name="test")
        
        with pytest.raises(NotImplementedError):
            import asyncio
            asyncio.run(backend.embed(["test"]))


class TestIntegration:
    """Integration tests for embedding generation (mocked)."""

    @pytest.mark.asyncio
    async def test_truncation_applied_before_embedding(self):
        backend = BedrockCohereBackend(name="test-backend")
        
        long_text = "A" * 10000
        
        mock_response = {
            "body": MagicMock(
                read=MagicMock(return_value=b'{"embedding": [0.1, 0.2, 0.3]}')
            )
        }
        
        with patch.object(backend, "_client") as mock_client:
            mock_client.return_value.invoke_model.return_value = mock_response
            
            result = await backend.embed([long_text])
            
            # Should still return embeddings even for long text
            assert len(result) == 1
            
            # Verify the text was truncated before sending
            call_args = mock_client.return_value.invoke_model.call_args
            import json
            body = json.loads(call_args.kwargs.get("body", call_args[1].get("body", "{}")))
            assert len(body.get("inputText", "")) <= 4000
