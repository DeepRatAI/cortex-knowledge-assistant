"""Tests for RAGService - the core RAG pipeline orchestrator.

Tests cover:
- Normal answer generation with context
- No-context fallback behavior
- Cache hit/miss scenarios
- PII sensitivity tracking
- Full-list detection
- Error handling
"""

from __future__ import annotations

from typing import Iterator
from unittest.mock import MagicMock

import pytest

from cortex_ka.application.rag_service import (
    RAGConfig,
    RAGResult,
    RAGService,
    _extract_keywords,
    _is_full_list_request,
    _normalize_text,
)
from cortex_ka.domain.models import DocumentChunk, RetrievalResult
from cortex_ka.domain.ports import LLMPort, RetrieverPort

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class DummyRetriever(RetrieverPort):
    """Test double for RetrieverPort."""

    def __init__(self, chunks: list[DocumentChunk] | None = None) -> None:
        self._chunks = chunks or []

    def retrieve(
        self,
        query: str,
        k: int = 5,
        subject_id: str | None = None,
        context_type: str | None = None,
    ) -> RetrievalResult:
        return RetrievalResult(query=query, chunks=self._chunks)


class DummyLLM(LLMPort):
    """Test double for LLMPort."""

    def __init__(self, response: str = "Test response") -> None:
        self._response = response

    def generate(self, prompt: str) -> str:
        return self._response

    def generate_stream(self, prompt: str) -> Iterator[str]:
        for word in self._response.split():
            yield word + " "


class DummyCache:
    """Test double for CacheProtocol."""

    def __init__(self) -> None:
        self._cache: dict[str, str] = {}
        self.get_count = 0
        self.set_count = 0

    def get_answer(self, query: str) -> str | None:
        self.get_count += 1
        return self._cache.get(query)

    def set_answer(self, query: str, answer: str) -> None:
        self.set_count += 1
        self._cache[query] = answer


@pytest.fixture
def sample_chunks() -> list[DocumentChunk]:
    """Create sample document chunks for testing."""
    return [
        DocumentChunk(
            id="chunk-001",
            text="El plazo para presentar documentación es de 30 días.",
            source="reglamento.pdf",
            filename="reglamento.pdf",
            score=0.92,
            pii_sensitivity=None,
        ),
        DocumentChunk(
            id="chunk-002",
            text="Los requisitos de inscripción incluyen DNI y certificado de estudios.",
            source="tramites.pdf",
            filename="tramites.pdf",
            score=0.87,
            pii_sensitivity="medium",
        ),
        DocumentChunk(
            id="chunk-003",
            text="Información confidencial del cliente Juan Pérez.",
            source="clientes.pdf",
            filename="clientes.pdf",
            score=0.75,
            pii_sensitivity="high",
        ),
    ]


# ---------------------------------------------------------------------------
# RAGConfig Tests
# ---------------------------------------------------------------------------


class TestRAGConfig:
    """Tests for RAGConfig dataclass."""

    def test_default_values(self) -> None:
        """RAGConfig should have sensible defaults."""
        cfg = RAGConfig()
        assert cfg.top_k == 80
        assert cfg.selection_budget == 15
        assert cfg.min_similarity > 0
        assert cfg.semantic_weight > 0
        assert cfg.keyword_weight >= 0

    def test_custom_values(self) -> None:
        """RAGConfig should accept custom values."""
        cfg = RAGConfig(top_k=50, selection_budget=10, min_similarity=0.5)
        assert cfg.top_k == 50
        assert cfg.selection_budget == 10
        assert abs(cfg.min_similarity - 0.5) < 0.001  # Float comparison


# ---------------------------------------------------------------------------
# RAGResult Tests
# ---------------------------------------------------------------------------


class TestRAGResult:
    """Tests for RAGResult dataclass."""

    def test_basic_result(self) -> None:
        """RAGResult should store answer and query."""
        result = RAGResult(answer="La respuesta es 42.", query="¿Cuál es la respuesta?")
        assert result.answer == "La respuesta es 42."
        assert result.query == "¿Cuál es la respuesta?"

    def test_result_with_chunks(self, sample_chunks: list[DocumentChunk]) -> None:
        """RAGResult should track chunks used."""
        result = RAGResult(
            answer="Respuesta basada en documentos.",
            query="test query",
            chunks_used=sample_chunks[:2],
        )
        assert len(result.used_chunks) == 2
        assert result.citations is not None

    def test_max_pii_sensitivity(self, sample_chunks: list[DocumentChunk]) -> None:
        """RAGResult.max_pii_sensitivity is based on pii_sensitive flag."""
        # max_pii_sensitivity returns "high" when pii_sensitive=True
        result = RAGResult(
            answer="test",
            query="test",
            chunks_used=sample_chunks,
            pii_sensitive=True,  # This controls max_pii_sensitivity
        )
        assert result.max_pii_sensitivity == "high"

    def test_pii_sensitivity_none_when_no_pii(self) -> None:
        """RAGResult should return None when no chunks have PII sensitivity."""
        chunks = [
            DocumentChunk(id="1", text="safe text", source="doc.pdf", score=0.9),
        ]
        result = RAGResult(answer="safe", query="q", chunks_used=chunks)
        assert result.max_pii_sensitivity is None


# ---------------------------------------------------------------------------
# RAGService Tests
# ---------------------------------------------------------------------------


class TestRAGServiceAnswer:
    """Tests for RAGService.answer() method."""

    def test_answer_with_context(self, sample_chunks: list[DocumentChunk]) -> None:
        """answer() should generate response using retrieved chunks."""
        retriever = DummyRetriever(chunks=sample_chunks)
        llm = DummyLLM(response="El plazo es de 30 días según el reglamento.")

        svc = RAGService(retriever=retriever, llm=llm)
        result = svc.answer("¿Cuál es el plazo?")

        assert "plazo" in result.answer.lower() or "30" in result.answer
        assert result.query == "¿Cuál es el plazo?"
        assert result.metrics is not None
        assert result.metrics.get("candidates", 0) > 0

    def test_answer_no_context(self) -> None:
        """answer() should return fallback when no chunks found."""
        retriever = DummyRetriever(chunks=[])
        llm = DummyLLM()

        svc = RAGService(retriever=retriever, llm=llm)
        result = svc.answer("pregunta sin respuesta")

        # Should return a polite "no info" message, not an error
        assert "no" in result.answer.lower() or "información" in result.answer.lower()
        assert result.metrics.get("candidates", 0) == 0

    def test_cache_hit(self, sample_chunks: list[DocumentChunk]) -> None:
        """answer() should return cached response on cache hit."""
        cache = DummyCache()
        # Cache key format: "{subject_id or 'anon'}::{context_type or 'all'}::{query}"
        cache.set_answer("anon::all::test query", "Cached answer")

        retriever = DummyRetriever(chunks=sample_chunks)
        llm = DummyLLM(response="Fresh answer")

        svc = RAGService(retriever=retriever, llm=llm, cache=cache)
        result = svc.answer("test query")

        assert result.answer == "Cached answer"
        assert cache.get_count == 1

    def test_cache_miss_stores_result(self, sample_chunks: list[DocumentChunk]) -> None:
        """answer() should store result in cache on miss."""
        cache = DummyCache()
        retriever = DummyRetriever(chunks=sample_chunks)
        llm = DummyLLM(response="Generated answer")

        svc = RAGService(retriever=retriever, llm=llm, cache=cache)
        result = svc.answer("new query")

        assert cache.set_count == 1
        assert result.answer == "Generated answer"

    def test_pii_tracking(self, sample_chunks: list[DocumentChunk]) -> None:
        """answer() should track PII sensitivity in result."""
        retriever = DummyRetriever(chunks=sample_chunks)
        llm = DummyLLM()

        svc = RAGService(retriever=retriever, llm=llm)
        result = svc.answer("test query")

        # Result should have pii_sensitive flag based on chunks
        assert result.pii_sensitive is not None or result.max_pii_sensitivity is not None

    def test_subject_id_scoping(self, sample_chunks: list[DocumentChunk]) -> None:
        """answer() should pass subject_id to retriever for scoping."""
        retriever = MagicMock(spec=RetrieverPort)
        retriever.retrieve.return_value = RetrievalResult(query="q", chunks=sample_chunks)

        llm = DummyLLM()

        svc = RAGService(retriever=retriever, llm=llm)
        svc.answer("test", subject_id="client-123")

        retriever.retrieve.assert_called_once()
        call_args = retriever.retrieve.call_args
        assert call_args.kwargs.get("subject_id") == "client-123"


class TestRAGServiceStream:
    """Tests for RAGService.answer_stream() method."""

    def test_stream_yields_tokens(self, sample_chunks: list[DocumentChunk]) -> None:
        """answer_stream() should yield tokens incrementally."""
        retriever = DummyRetriever(chunks=sample_chunks)
        llm = DummyLLM(response="Token one two three")

        svc = RAGService(retriever=retriever, llm=llm)
        tokens = list(svc.answer_stream("test query"))

        assert len(tokens) > 0
        full_response = "".join(tokens)
        assert "Token" in full_response or "token" in full_response.lower()

    def test_stream_no_context_yields_fallback(self) -> None:
        """answer_stream() should yield fallback message when no chunks."""
        retriever = DummyRetriever(chunks=[])
        llm = DummyLLM()

        svc = RAGService(retriever=retriever, llm=llm)
        tokens = list(svc.answer_stream("test"))

        full_response = "".join(tokens)
        assert len(full_response) > 0


# ---------------------------------------------------------------------------
# Helper Function Tests
# ---------------------------------------------------------------------------


class TestHelperFunctions:
    """Tests for RAG helper functions."""

    def test_normalize_text(self) -> None:
        """_normalize_text should lowercase and remove accents."""
        assert _normalize_text("HOLA") == "hola"
        assert _normalize_text("Café") == "cafe"
        assert _normalize_text("Año") == "ano"

    def test_extract_keywords(self) -> None:
        """_extract_keywords should extract meaningful terms."""
        keywords = _extract_keywords("¿Cuál es el reglamento de inscripción?")
        assert "reglamento" in keywords or "inscripcion" in keywords

    def test_is_full_list_request_true(self) -> None:
        """_is_full_list_request should detect list requests."""
        assert _is_full_list_request("Dame toda la lista de materias") is True
        assert _is_full_list_request("Enumera todos los requisitos") is True
        assert _is_full_list_request("Lista completa de documentos") is True

    def test_is_full_list_request_false(self) -> None:
        """_is_full_list_request should return False for normal queries."""
        assert _is_full_list_request("¿Cuál es el plazo?") is False
        assert _is_full_list_request("Información sobre inscripción") is False
        assert _is_full_list_request("") is False
