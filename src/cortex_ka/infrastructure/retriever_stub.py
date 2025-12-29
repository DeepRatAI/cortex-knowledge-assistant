"""Stub retriever (to be replaced by Qdrant implementation)."""

from __future__ import annotations

from ..domain.models import DocumentChunk, RetrievalResult
from ..domain.ports import RetrieverPort


class StubRetriever(RetrieverPort):
    """Returns static chunks for early development.

    This enables testing the generation pipeline prior to integrating the vector DB.
    """

    def retrieve(
        self,
        query: str,
        k: int = 5,
        subject_id: str | None = None,
        context_type: str | None = None,
    ) -> RetrievalResult:  # type: ignore[override]
        chunks = [
            DocumentChunk(
                id="demo-1",
                text="Corporate policies define procedures for internal compliance.",
                source="synthetic",
            ),
            DocumentChunk(
                id="demo-2",
                text="Procedures outline step-by-step operational guidelines.",
                source="synthetic",
            ),
        ][:k]
        return RetrievalResult(query=query, chunks=chunks)
