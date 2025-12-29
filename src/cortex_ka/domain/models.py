"""Domain models for Cortex KA.

Contains simple value objects and entities reused across layers.
"""

from __future__ import annotations

from pydantic import BaseModel


class DocumentChunk(BaseModel):
    """A semantically meaningful chunk of a document."""

    id: str
    text: str
    source: str
    # Optional document identifier for traceability
    doc_id: str | None = None
    # Optional original filename for better context
    filename: str | None = None
    # Score from vector search (similarity)
    score: float | None = None
    # Optional sensitivity label derived from ingestion-time PII classification.
    # When present, this allows downstream components to reason about the
    # relative sensitivity of the chunk without re-inspecting raw text.
    pii_sensitivity: str | None = None


class RetrievalResult(BaseModel):
    """Result returned by the retriever before prompt assembly."""

    query: str
    chunks: list[DocumentChunk]


class Answer(BaseModel):
    """Generated answer with trace metadata."""

    answer: str
    query: str
    used_chunks: list[str]
    citations: list[dict] = []
    # Maximum PII sensitivity across all chunks used to answer this query.
    # This is a coarse summary intended for observability/auditing; it does
    # not replace fine-grained, per-field enforcement.
    max_pii_sensitivity: str | None = None
