"""Re-ranking module for hybrid RAG retrieval.

Implements cross-encoder re-ranking and score fusion techniques
to improve precision after initial retrieval.

Best practices from:
- ColBERT, BERT re-rankers
- Reciprocal Rank Fusion (RRF)
- Score normalization
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Sequence

if TYPE_CHECKING:
    from ..domain.models import DocumentChunk


@dataclass
class ScoredChunk:
    """A chunk with its computed score and metadata."""

    chunk: "DocumentChunk"
    score: float
    score_components: dict[str, float] | None = None
    rank: int = 0


def normalize_scores(scores: list[float]) -> list[float]:
    """Min-max normalize scores to [0, 1] range.

    Args:
        scores: List of raw scores

    Returns:
        Normalized scores
    """
    if not scores:
        return []

    min_score = min(scores)
    max_score = max(scores)

    if max_score == min_score:
        return [0.5] * len(scores)

    return [(s - min_score) / (max_score - min_score) for s in scores]


def reciprocal_rank_fusion(
    ranked_lists: list[list[ScoredChunk]],
    k: int = 60,
) -> list[ScoredChunk]:
    """Combine multiple ranked lists using Reciprocal Rank Fusion.

    RRF is a simple but effective method for combining rankings from
    different retrieval systems. Formula: score = sum(1 / (k + rank))

    Args:
        ranked_lists: Multiple ranked lists of chunks
        k: RRF constant (default 60, from original paper)

    Returns:
        Fused and re-ranked list
    """
    # Map chunk ID to aggregated score
    chunk_scores: dict[str, float] = {}
    chunk_map: dict[str, ScoredChunk] = {}

    for ranked_list in ranked_lists:
        for rank, scored in enumerate(ranked_list):
            chunk_id = getattr(scored.chunk, "id", str(id(scored.chunk)))

            # RRF formula
            rrf_score = 1.0 / (k + rank + 1)

            if chunk_id in chunk_scores:
                chunk_scores[chunk_id] += rrf_score
            else:
                chunk_scores[chunk_id] = rrf_score
                chunk_map[chunk_id] = scored

    # Sort by fused score
    sorted_ids = sorted(chunk_scores.keys(), key=lambda x: chunk_scores[x], reverse=True)

    result = []
    for i, chunk_id in enumerate(sorted_ids):
        scored = chunk_map[chunk_id]
        result.append(
            ScoredChunk(
                chunk=scored.chunk,
                score=chunk_scores[chunk_id],
                score_components={"rrf": chunk_scores[chunk_id]},
                rank=i,
            )
        )

    return result


def linear_combination_fusion(
    semantic_results: list[ScoredChunk],
    keyword_results: list[ScoredChunk],
    semantic_weight: float = 0.7,
    keyword_weight: float = 0.3,
) -> list[ScoredChunk]:
    """Combine semantic and keyword scores with weighted linear combination.

    Args:
        semantic_results: Results from semantic (vector) search
        keyword_results: Results from keyword/BM25 search
        semantic_weight: Weight for semantic scores
        keyword_weight: Weight for keyword scores

    Returns:
        Fused results with combined scores
    """
    # Build score maps
    semantic_scores: dict[str, float] = {}
    keyword_scores: dict[str, float] = {}
    chunk_map: dict[str, ScoredChunk] = {}

    # Normalize semantic scores
    sem_raw = [s.score for s in semantic_results]
    sem_norm = normalize_scores(sem_raw)

    for scored, norm_score in zip(semantic_results, sem_norm):
        chunk_id = getattr(scored.chunk, "id", str(id(scored.chunk)))
        semantic_scores[chunk_id] = norm_score
        chunk_map[chunk_id] = scored

    # Normalize keyword scores
    kw_raw = [s.score for s in keyword_results]
    kw_norm = normalize_scores(kw_raw)

    for scored, norm_score in zip(keyword_results, kw_norm):
        chunk_id = getattr(scored.chunk, "id", str(id(scored.chunk)))
        keyword_scores[chunk_id] = norm_score
        if chunk_id not in chunk_map:
            chunk_map[chunk_id] = scored

    # Combine scores
    all_ids = set(semantic_scores.keys()) | set(keyword_scores.keys())
    combined: list[tuple[str, float, dict]] = []

    for chunk_id in all_ids:
        sem = semantic_scores.get(chunk_id, 0.0)
        kw = keyword_scores.get(chunk_id, 0.0)

        combined_score = (semantic_weight * sem) + (keyword_weight * kw)
        components = {"semantic": sem, "keyword": kw}
        combined.append((chunk_id, combined_score, components))

    # Sort by combined score
    combined.sort(key=lambda x: x[1], reverse=True)

    result = []
    for i, (chunk_id, score, components) in enumerate(combined):
        scored = chunk_map[chunk_id]
        result.append(
            ScoredChunk(
                chunk=scored.chunk,
                score=score,
                score_components=components,
                rank=i,
            )
        )

    return result


class HybridScorer:
    """Hybrid scoring system for RAG retrieval.

    Combines multiple signals:
    - Semantic similarity (from vector search)
    - Keyword/term overlap
    - Document mention boost
    - Topic relevance boost
    - Recency boost (optional)

    Args:
        semantic_weight: Base weight for semantic similarity
        keyword_weight: Weight for keyword matches
        mention_boost: Boost for explicitly mentioned documents
        topic_boost: Boost for topic-relevant chunks
        min_score_threshold: Minimum score to include in results
    """

    def __init__(
        self,
        semantic_weight: float = 0.5,
        keyword_weight: float = 0.15,
        mention_boost: float = 0.25,
        topic_boost: float = 0.15,
        min_score_threshold: float = 0.1,
    ) -> None:
        self.semantic_weight = semantic_weight
        self.keyword_weight = keyword_weight
        self.mention_boost = mention_boost
        self.topic_boost = topic_boost
        self.min_score_threshold = min_score_threshold

    def score_chunks(
        self,
        chunks: Sequence["DocumentChunk"],
        keywords: list[str],
        mentioned_doc: str | None = None,
        topic: str | None = None,
        normalize_text_fn: Callable[[str], str] | None = None,
    ) -> list[ScoredChunk]:
        """Score and rank chunks using hybrid signals.

        Args:
            chunks: Retrieved chunks to score
            keywords: Extracted query keywords
            mentioned_doc: Explicitly mentioned document name
            topic: Detected topic/subject
            normalize_text_fn: Function to normalize text for comparison

        Returns:
            Scored and sorted chunks
        """
        if normalize_text_fn is None:
            normalize_text_fn = lambda x: x.lower()

        scored_chunks: list[ScoredChunk] = []

        for chunk in chunks:
            score, components = self._compute_score(chunk, keywords, mentioned_doc, topic, normalize_text_fn)

            if score >= self.min_score_threshold:
                scored_chunks.append(
                    ScoredChunk(
                        chunk=chunk,
                        score=score,
                        score_components=components,
                    )
                )

        # Sort by score descending
        scored_chunks.sort(key=lambda x: x.score, reverse=True)

        # Assign ranks
        for i, sc in enumerate(scored_chunks):
            sc.rank = i

        return scored_chunks

    def _compute_score(
        self,
        chunk: "DocumentChunk",
        keywords: list[str],
        mentioned_doc: str | None,
        topic: str | None,
        normalize_fn: Callable[[str], str],
    ) -> tuple[float, dict[str, float]]:
        """Compute hybrid score for a single chunk."""
        components: dict[str, float] = {}

        # 1. Semantic score (from retrieval)
        semantic = float(chunk.score) if chunk.score is not None else 0.5
        components["semantic"] = semantic

        # 2. Keyword match score
        text = getattr(chunk, "text", "") or ""
        text_norm = normalize_fn(text)
        text_nospace = text_norm.replace(" ", "")

        keyword_matches = 0
        for kw in keywords:
            if kw in text_norm or kw in text_nospace:
                keyword_matches += 1

        keyword_score = min(1.0, keyword_matches / max(1, len(keywords))) if keywords else 0
        components["keyword"] = keyword_score

        # 3. Document mention boost
        mention_score = 0.0
        if mentioned_doc:
            filename = (getattr(chunk, "filename", "") or "").lower()
            doc_id = (getattr(chunk, "doc_id", "") or "").lower()

            if mentioned_doc in filename or mentioned_doc in doc_id:
                mention_score = 1.0
        components["mention"] = mention_score

        # 4. Topic boost
        topic_score = 0.0
        if topic:
            filename = (getattr(chunk, "filename", "") or "").lower()
            if topic in text_norm or topic in filename:
                topic_score = 1.0
        components["topic"] = topic_score

        # Combine scores
        total = (
            self.semantic_weight * semantic
            + self.keyword_weight * keyword_score
            + self.mention_boost * mention_score
            + self.topic_boost * topic_score
        )

        return total, components


def deduplicate_chunks(
    chunks: list[ScoredChunk],
    similarity_threshold: float = 0.9,
) -> list[ScoredChunk]:
    """Remove near-duplicate chunks based on text similarity.

    Uses a simple character n-gram approach for efficiency.

    Args:
        chunks: Scored chunks to deduplicate
        similarity_threshold: Jaccard similarity threshold for duplicates

    Returns:
        Deduplicated list (keeps highest scored)
    """
    if len(chunks) <= 1:
        return chunks

    def get_ngrams(text: str, n: int = 3) -> set[str]:
        """Get character n-grams from text."""
        text = text.lower()
        return {text[i : i + n] for i in range(len(text) - n + 1)}

    def jaccard_similarity(set1: set, set2: set) -> float:
        """Compute Jaccard similarity between two sets."""
        if not set1 or not set2:
            return 0.0
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        return intersection / union if union > 0 else 0.0

    # Pre-compute n-grams for all chunks
    chunk_ngrams = [get_ngrams(getattr(sc.chunk, "text", "") or "") for sc in chunks]

    result: list[ScoredChunk] = []
    used_indices: set[int] = set()

    for i, scored in enumerate(chunks):
        if i in used_indices:
            continue

        # This chunk is selected
        result.append(scored)
        used_indices.add(i)

        # Mark similar chunks as used (they won't be selected)
        for j in range(i + 1, len(chunks)):
            if j in used_indices:
                continue

            sim = jaccard_similarity(chunk_ngrams[i], chunk_ngrams[j])
            if sim >= similarity_threshold:
                used_indices.add(j)

    return result


def apply_diversity_limits(
    chunks: list[ScoredChunk],
    max_per_doc: int = 5,
    max_from_mentioned: int = 8,
    mentioned_doc: str | None = None,
    budget: int = 12,
) -> list[ScoredChunk]:
    """Apply per-document diversity limits.

    Prevents any single document from dominating results.

    Args:
        chunks: Pre-sorted chunks by score
        max_per_doc: Maximum chunks from any single document
        max_from_mentioned: Higher limit for explicitly mentioned doc
        mentioned_doc: Document name if explicitly mentioned
        budget: Total selection budget

    Returns:
        Filtered chunks respecting limits
    """
    selected: list[ScoredChunk] = []
    doc_counts: dict[str, int] = {}

    for scored in chunks:
        if len(selected) >= budget:
            break

        # Determine document key
        filename = getattr(scored.chunk, "filename", "") or ""
        source = getattr(scored.chunk, "source", "") or ""
        doc_key = (filename or source or "unknown").lower()

        # Determine limit for this document
        is_mentioned = mentioned_doc and mentioned_doc in doc_key
        limit = max_from_mentioned if is_mentioned else max_per_doc

        # Check if we can add this chunk
        current_count = doc_counts.get(doc_key, 0)
        if current_count < limit:
            selected.append(scored)
            doc_counts[doc_key] = current_count + 1

    return selected
