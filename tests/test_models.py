"""Tests for domain models."""

from cortex_ka.domain.models import Answer, DocumentChunk, RetrievalResult


class TestDocumentChunk:
    """Test suite for DocumentChunk model."""

    def test_create_minimal(self):
        """Create chunk with required fields only."""
        chunk = DocumentChunk(id="1", text="Hello", source="test")
        assert chunk.id == "1"
        assert chunk.text == "Hello"
        assert chunk.source == "test"

    def test_create_with_optional_fields(self):
        """Create chunk with optional fields."""
        chunk = DocumentChunk(
            id="1",
            text="Hello",
            source="test",
            doc_id="doc-1",
            filename="test.pdf",
            score=0.95,
            pii_sensitivity="low",
        )
        assert chunk.doc_id == "doc-1"
        assert chunk.score == 0.95


class TestRetrievalResult:
    """Test suite for RetrievalResult model."""

    def test_create_empty(self):
        """Create result with no chunks."""
        result = RetrievalResult(query="test", chunks=[])
        assert result.query == "test"
        assert len(result.chunks) == 0

    def test_create_with_chunks(self):
        """Create result with chunks."""
        chunk = DocumentChunk(id="1", text="content", source="test")
        result = RetrievalResult(query="test", chunks=[chunk])
        assert len(result.chunks) == 1


class TestAnswer:
    """Test suite for Answer model."""

    def test_create_minimal(self):
        """Create answer with required fields."""
        answer = Answer(answer="response", query="question", used_chunks=["1"])
        assert answer.answer == "response"
        assert answer.query == "question"

    def test_citations_default_empty(self):
        """Citations should default to empty list."""
        answer = Answer(answer="x", query="y", used_chunks=[])
        assert answer.citations == []
