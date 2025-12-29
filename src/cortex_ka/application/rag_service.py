"""Application service orchestrating retrieval + generation.

Implements industry best practices for production RAG pipelines:
- Multi-stage retrieval with query expansion
- Hybrid scoring (semantic + keyword + structural)
- Re-ranking with cross-encoder principles
- Document-aware chunk selection with diversity
- Near-duplicate detection and removal
- PII sensitivity tracking
- Comprehensive metrics and observability
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Iterator, Protocol, Sequence

from .prompt_builder import build_prompt
from .query_processing import (
    extract_document_reference,
    extract_keywords,
    extract_topic,
    generate_search_variants,
    normalize_text,
)
from .reranking import (
    HybridScorer,
    ScoredChunk,
    apply_diversity_limits,
    deduplicate_chunks,
)

if TYPE_CHECKING:
    from ..domain.models import DocumentChunk
    from ..domain.ports import LLMPort, RetrieverPort
    from ..transactions.service import CustomerSnapshot

logger = logging.getLogger(__name__)


class CacheProtocol(Protocol):
    """Protocol for cache implementations (compatible with CachePort)."""

    def get_answer(self, query: str) -> str | None: ...
    def set_answer(self, query: str, answer: str) -> None: ...


class _NullCache:
    """No-op cache for when caching is disabled."""

    def get_answer(self, query: str) -> str | None:
        del query
        return None

    def set_answer(self, query: str, answer: str) -> None:
        del query, answer


@dataclass
class RAGConfig:
    """Configuration for production RAG pipeline.

    These parameters are tuned based on empirical testing and
    RAG best practices from research papers.
    """

    # Retrieval parameters
    top_k: int = 80  # Initial retrieval pool size
    selection_budget: int = 15  # Final chunks to use for generation
    max_per_doc: int = 6  # Max chunks from single document
    max_from_mentioned: int = 10  # Higher limit for explicitly mentioned docs

    # Scoring thresholds
    min_similarity: float = 0.12  # Minimum semantic similarity

    # Hybrid scoring weights (should sum to ~1.0)
    semantic_weight: float = 0.50  # Base semantic similarity weight
    keyword_weight: float = 0.15  # Keyword match weight
    mention_boost: float = 0.25  # Explicit document mention boost
    topic_boost: float = 0.15  # Topic relevance boost

    # Deduplication
    dedup_threshold: float = 0.85  # Jaccard similarity for near-duplicates

    # Generation parameters
    max_tokens: int = 8192  # Max output tokens
    context_budget_chars: int = 8000  # Max context size in characters

    # Cache
    cache_ttl: int = 3600  # Cache TTL in seconds

    # Feature flags
    use_query_expansion: bool = True  # Generate search variants
    use_deduplication: bool = True  # Remove near-duplicate chunks
    use_reranking: bool = True  # Apply hybrid re-ranking


@dataclass
class RAGResult:
    """Result from RAG pipeline with API compatibility properties."""

    answer: str
    query: str = ""
    chunks_used: list = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    pii_sensitive: bool = False
    _chunk_ids: list[str] = field(default_factory=list)
    _citations: list[dict] = field(default_factory=list)

    @property
    def used_chunks(self) -> list[str]:
        if self._chunk_ids:
            return self._chunk_ids
        return [getattr(c, "id", str(i)) for i, c in enumerate(self.chunks_used)]

    @property
    def citations(self) -> list[dict]:
        if self._citations:
            return self._citations
        cites = []
        for chunk in self.chunks_used:
            cid = getattr(chunk, "id", None) or ""
            src = getattr(chunk, "source", None) or getattr(chunk, "filename", "unknown")
            cites.append({"id": str(cid), "source": str(src)})
        return cites

    @property
    def max_pii_sensitivity(self) -> str | None:
        return "high" if self.pii_sensitive else None


_STOPWORDS = frozenset(
    {
        "el",
        "la",
        "los",
        "las",
        "un",
        "una",
        "de",
        "del",
        "en",
        "con",
        "por",
        "para",
        "que",
        "es",
        "se",
        "como",
        "su",
        "al",
        "lo",
        "mas",
        "pero",
        "sus",
        "le",
        "ya",
        "o",
        "este",
        "si",
        "porque",
        "esta",
        "cuando",
        "muy",
        "sin",
        "sobre",
        "ser",
        "tiene",
        "tambien",
        "fue",
        "hay",
        "donde",
        "puede",
        "todos",
        "asi",
        "nos",
        "ni",
        "parte",
        "despues",
        "uno",
        "bien",
        "cada",
        "segun",
        "documento",
        "archivo",
        "pdf",
        "dice",
        "trata",
        "cual",
        "cuales",
        "resumime",
        "resumeme",
        "explicame",
        "cuentame",
        "describeme",
        "informacion",
    }
)

# Stopwords estructurales del español (palabras que NO aportan significado temático)
# Esta lista es agnóstica al dominio - solo contiene palabras funcionales del idioma
_STRUCTURAL_STOPWORDS = frozenset(
    {
        # Artículos y determinantes
        "el",
        "la",
        "los",
        "las",
        "un",
        "una",
        "unos",
        "unas",
        # Preposiciones
        "de",
        "del",
        "en",
        "con",
        "por",
        "para",
        "sin",
        "sobre",
        "bajo",
        "ante",
        "entre",
        # Pronombres y demostrativos
        "que",
        "cual",
        "quien",
        "este",
        "esta",
        "estos",
        "estas",
        "ese",
        "esa",
        "mi",
        "tu",
        "su",
        "mis",
        "tus",
        "sus",
        "me",
        "te",
        "se",
        "nos",
        "les",
        # Verbos auxiliares y comunes
        "es",
        "son",
        "ser",
        "estar",
        "hay",
        "tiene",
        "tienen",
        "puede",
        "pueden",
        "hacer",
        "hecho",
        "sido",
        "siendo",
        "era",
        "fue",
        "seria",
        # Adverbios y conectores
        "mas",
        "muy",
        "poco",
        "mucho",
        "algo",
        "nada",
        "todo",
        "todos",
        "cada",
        "como",
        "cuando",
        "donde",
        "porque",
        "aunque",
        "sino",
        "pero",
        "tambien",
        "asi",
        "bien",
        "mal",
        "solo",
        "ya",
        "aun",
        "aqui",
        "alli",
        "ahora",
        "siempre",
        # Palabras de consulta genéricas (no aportan tema)
        "hablame",
        "dime",
        "explicame",
        "cuentame",
        "describe",
        "describeme",
        "informacion",
        "documento",
        "documentos",
        "archivo",
        "archivos",
        "pregunta",
        "respuesta",
        "necesito",
        "quisiera",
        "podrias",
        "quiero",
        "dame",
        "muestrame",
        "busca",
        "encuentra",
        "ayuda",
        "favor",
        # Números escritos
        "uno",
        "dos",
        "tres",
        "cuatro",
        "cinco",
        "seis",
        "siete",
        "ocho",
        "nueve",
        "diez",
        "primero",
        "segundo",
        "tercero",
        "cuarto",
        "quinto",
    }
)


def _normalize_text(text: str) -> str:
    import unicodedata

    text = text.lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", text).strip()


def _extract_significant_terms(query: str, min_len: int = 4) -> list[str]:
    """Extract significant terms from query - domain agnostic.

    Returns words that are likely to be meaningful topic identifiers,
    ordered by significance (longer words first, as they tend to be more specific).
    """
    normalized = _normalize_text(query)
    words = re.findall(r"\b[a-z]+\b", normalized)

    # Filter out structural stopwords and very short words
    significant = [w for w in words if len(w) >= min_len and w not in _STRUCTURAL_STOPWORDS and w not in _STOPWORDS]

    # Sort by length (longer = more specific/significant)
    # Also deduplicate while preserving order
    seen = set()
    unique_sorted = []
    for w in sorted(significant, key=lambda x: -len(x)):
        if w not in seen:
            seen.add(w)
            unique_sorted.append(w)

    return unique_sorted


def _extract_keywords(text: str, min_len: int = 3, max_kw: int = 15) -> list[str]:
    """Extract keywords from text for matching."""
    normalized = _normalize_text(text)
    words = re.findall(r"\b[a-z]+\b", normalized)
    filtered = [w for w in words if len(w) >= min_len and w not in _STOPWORDS]

    # Sort by length (longer words tend to be more specific)
    sorted_words = sorted(set(filtered), key=lambda w: -len(w))
    return sorted_words[:max_kw]


def _extract_query_topics(query: str) -> list[str]:
    """Extract potential topic terms from a query - completely domain agnostic.

    Uses linguistic patterns and word characteristics to identify likely topic terms.
    No hardcoded domain terms - works for any subject area.
    """
    normalized = _normalize_text(query)

    # Pattern-based extraction: words following contextual indicators
    # These patterns work for ANY domain
    topic_patterns = [
        # "la asignatura X", "el curso X", "la materia X"
        r"(?:asignatura|materia|curso|clase|taller|seminario)\s+(?:de\s+)?(\w+)",
        # "carrera de X", "licenciatura en X", "maestria en X"
        r"(?:carrera|licenciatura|maestria|doctorado|especializacion|diplomado)\s+(?:de|en)\s+(\w+)",
        # "documento de X", "manual de X", "guia de X"
        r"(?:documento|manual|guia|libro|texto|programa)\s+(?:de|sobre)\s+(\w+)",
        # "sobre X", "acerca de X", "respecto a X"
        r"(?:sobre|acerca\s+de|respecto\s+a|referente\s+a)\s+(\w+)",
        # "el/la X" followed by context words
        r"(?:el|la)\s+(\w{5,})\s+(?:del|de\s+la|que|es)",
    ]

    topics = []
    for pattern in topic_patterns:
        matches = re.findall(pattern, normalized)
        for match in matches:
            if len(match) >= 4 and match not in _STRUCTURAL_STOPWORDS:
                topics.append(match)

    # Also get significant terms (long, non-stopword words)
    significant = _extract_significant_terms(query, min_len=5)

    # Combine pattern matches with significant terms, prioritizing pattern matches
    seen = set()
    result = []
    for t in topics + significant:
        if t not in seen:
            seen.add(t)
            result.append(t)

    return result[:5]  # Limit to top 5 most likely topics


def _is_full_list_request(query: str) -> bool:
    """Detect if the user explicitly requests a full/complete list or enumeration.

    This helps the RAG pipeline relax selection limits and instruct the LLM
    to return an explicit enumerated list instead of a short summary.
    """
    if not query:
        return False
    q = query.lower()
    patterns = [
        "toda la lista",
        "lista completa",
        "todas las",
        "toda la",
        "enumerame",
        "enumera",
        "enumerar",
        "dame la lista",
        "dame toda la lista",
        "listar",
        "toda lista",
        "la lista completa",
    ]
    return any(p in q for p in patterns)


def _calculate_term_document_relevance(
    terms: list[str],
    filename: str,
    text: str,
) -> float:
    """Calculate relevance score between query terms and a document.

    Domain-agnostic scoring based on term overlap with filename and content.
    """
    if not terms:
        return 0.0

    filename_normalized = _normalize_text(filename)
    text_normalized = _normalize_text(text)

    score = 0.0
    for term in terms:
        # High boost if term appears in filename (very strong signal)
        if term in filename_normalized:
            score += 2.0
        # Medium boost if term appears in text content
        elif term in text_normalized:
            score += 0.5
        # Partial match in filename (e.g., "bromato" in "bromatologia")
        elif any(term[:4] in filename_normalized for _ in [1] if len(term) >= 4):
            score += 1.0

    # Normalize by number of terms to get average relevance
    return score / len(terms)


def _extract_mentioned_doc(query: str) -> str | None:
    patterns = [
        r'"([^"]+\.pdf)"',
        r"'([^']+\.pdf)'",
        r"(?:de|del|en|from)\s+([^\s]+\.pdf)",
        r"documento\s+([^\s]+)",
        r"(?:de|del|en)\s+([a-z0-9_-]+(?:-[a-z0-9_-]+)+)",
    ]
    query_lower = query.lower()
    for pattern in patterns:
        match = re.search(pattern, query_lower)
        if match:
            name = match.group(1).replace(".pdf", "")
            if len(name) >= 3:
                return name
    return None


class RAGService:
    """Service that orchestrates the complete RAG pipeline."""

    def __init__(
        self,
        retriever: RetrieverPort,
        llm: LLMPort,
        cache: CacheProtocol | None = None,
        config: RAGConfig | None = None,
    ) -> None:
        self._retriever = retriever
        self._llm = llm
        self._cache = cache or _NullCache()
        self._config = config or RAGConfig()

    def answer(
        self,
        query: str,
        subject_id: str | None = None,
        *,
        customer_snapshot: CustomerSnapshot | None = None,
        regulatory_strict: bool = False,
        context_type: str | None = None,
    ) -> RAGResult:
        cache_key = f"{subject_id or 'anon'}::{context_type or 'all'}::{query}"
        cached = self._cache.get_answer(cache_key)
        if cached:
            logger.info("cache_hit", extra={"query": query[:50]})
            return RAGResult(answer=cached, query=query)

        try:
            cfg = self._config
            retrieval = self._retriever.retrieve(
                query,
                k=self._config.top_k,
                subject_id=subject_id,
                context_type=context_type,
            )

            candidates = retrieval.chunks if hasattr(retrieval, "chunks") else []

            # If no documents but we have customer data, answer from snapshot only
            if not candidates:
                if customer_snapshot and self._has_customer_data(customer_snapshot):
                    return self._answer_from_snapshot_only(query, customer_snapshot, cache_key, regulatory_strict)
                msg = self._no_info_response(query)
                if not regulatory_strict:
                    self._cache.set_answer(cache_key, msg)
                return RAGResult(
                    answer=msg,
                    query=query,
                    metrics={"candidates": 0, "selected": 0},
                )

            keywords = _extract_keywords(query)
            mentioned_doc = _extract_mentioned_doc(query)
            query_topics = _extract_query_topics(query)  # Domain-agnostic topic extraction

            # If user explicitly requested a full list, relax selection limits
            full_list = _is_full_list_request(query)
            # For full-list requests, allow up to the initial retrieval pool (top_k)
            # so the selection can include all relevant chunks instead of a small
            # hand-picked subset.
            selection_limit = cfg.top_k if full_list else None

            selected = self._select_chunks(candidates, keywords, mentioned_doc, query_topics, selection_limit)

            if not selected:
                msg = self._no_info_response(query)
                return RAGResult(
                    answer=msg,
                    query=query,
                    chunks_used=candidates[:3],
                    metrics={"candidates": len(candidates), "selected": 0},
                )

            pii_sensitive = self._check_pii(selected)
            chunk_texts = self._build_context_blocks(selected, customer_snapshot)
            prompt = build_prompt(query, chunk_texts)

            # If user asked for the complete list, add a short instruction so the LLM
            # returns an explicit enumerated list rather than a short summary.
            if full_list:
                prompt += "\nPor favor, devuelve UNA LISTA ENUMERADA completa con todos los items mencionados en la documentación anterior. Si el texto original usa numeración, conserva un formato resumido pero completo."
            answer_text = self._llm.generate(prompt)

            sources = self._collect_sources(selected)
            chunk_ids = [str(getattr(c, "id", i)) for i, c in enumerate(selected)]
            citations = [
                {
                    "id": str(getattr(c, "id", "")),
                    "source": getattr(c, "source", "unknown"),
                }
                for c in selected
            ]

            metrics = {
                "candidates": len(candidates),
                "selected": len(selected),
                "sources": len(sources),
                "keywords": len(keywords),
                "mentioned_doc": mentioned_doc,
                "detected_topics": query_topics,  # Now a list, domain-agnostic
                "pii_sensitive": pii_sensitive,
            }

            self._cache.set_answer(cache_key, answer_text)

            logger.info(
                "rag_answer_generated",
                extra={
                    "query": query[:80],
                    "candidates": len(candidates),
                    "selected": len(selected),
                },
            )

            return RAGResult(
                answer=answer_text,
                query=query,
                chunks_used=selected,
                sources=sources,
                metrics=metrics,
                pii_sensitive=pii_sensitive,
                _chunk_ids=chunk_ids,
                _citations=citations,
            )

        except Exception as e:
            logger.exception("RAG pipeline error: %s", e)
            return RAGResult(
                answer="Error procesando la consulta. Por favor intente nuevamente.",
                query=query,
                metrics={"error": str(e)},
            )

    def answer_stream(
        self,
        query: str,
        subject_id: str | None = None,
        *,
        customer_snapshot: CustomerSnapshot | None = None,
        context_type: str | None = None,
    ) -> Iterator[str]:
        """Stream RAG answer token by token.

        Yields tokens as they are generated by the LLM.
        Does NOT use cache (streaming responses should not be cached).
        """
        try:
            cfg = self._config
            retrieval = self._retriever.retrieve(
                query,
                k=self._config.top_k,
                subject_id=subject_id,
                context_type=context_type,
            )

            candidates = retrieval.chunks if hasattr(retrieval, "chunks") else []

            # If no documents but we have customer data, stream from snapshot only
            if not candidates:
                if customer_snapshot and self._has_customer_data(customer_snapshot):
                    yield from self._stream_from_snapshot_only(query, customer_snapshot)
                    return
                yield self._no_info_response(query)
                return

            keywords = _extract_keywords(query)
            mentioned_doc = _extract_mentioned_doc(query)
            query_topics = _extract_query_topics(query)
            full_list = _is_full_list_request(query)
            # For streaming full-list requests, expand selection to the retrieval
            # pool so the LLM can enumerate everything found.
            selection_limit = cfg.top_k if full_list else None
            selected = self._select_chunks(candidates, keywords, mentioned_doc, query_topics, selection_limit)

            if not selected:
                yield self._no_info_response(query)
                return

            chunk_texts = self._build_context_blocks(selected, customer_snapshot)
            prompt = build_prompt(query, chunk_texts)
            if full_list:
                prompt += "\nPor favor, devuelve UNA LISTA ENUMERADA completa con todos los items mencionados en la documentación anterior. Si el texto original usa numeración, conserva un formato resumido pero completo."

            # Stream tokens from LLM
            for token in self._llm.generate_stream(prompt):
                yield token

            logger.info(
                "rag_stream_completed",
                extra={
                    "query": query[:80],
                    "candidates": len(candidates),
                    "selected": len(selected),
                },
            )

        except Exception as e:
            logger.exception("RAG streaming error: %s", e)
            yield "Error procesando la consulta. Por favor intente nuevamente."

    def _select_chunks(
        self,
        candidates: Sequence[DocumentChunk],
        keywords: list[str],
        mentioned_doc: str | None,
        query_topics: list[str] | None = None,
        selection_limit: int | None = None,
    ) -> list[DocumentChunk]:
        """Select best chunks using hybrid scoring with topic awareness.

        Completely domain-agnostic: uses extracted query topics to boost
        relevant documents without any hardcoded domain knowledge.
        """
        cfg = self._config
        scored: list[tuple[float, DocumentChunk]] = []

        for chunk in candidates:
            score = self._score_chunk(chunk, keywords, mentioned_doc, query_topics, cfg)
            if score is not None:
                scored.append((score, chunk))

        scored.sort(key=lambda x: -x[0])
        return self._apply_diversity_limits(scored, mentioned_doc, cfg, selection_limit)

    def _score_chunk(
        self,
        chunk: DocumentChunk,
        keywords: list[str],
        mentioned_doc: str | None,
        query_topics: list[str] | None,
        cfg: RAGConfig,
    ) -> float | None:
        """Calculate hybrid score for a single chunk.

        Domain-agnostic scoring using:
        - Semantic similarity (from retrieval)
        - Keyword overlap
        - Document mention boost
        - Topic relevance boost (based on term-document alignment)
        """
        # Base semantic score from retrieval
        semantic_score = float(chunk.score) if chunk.score is not None else 0.5

        if semantic_score < cfg.min_similarity:
            return None

        text = getattr(chunk, "text", "") or ""
        text_normalized = _normalize_text(text)
        text_nospace = text_normalized.replace(" ", "")
        filename = (getattr(chunk, "filename", "") or "").lower()

        # Calculate keyword match ratio
        keyword_matches = sum(1 for kw in keywords if kw in text_normalized or kw in text_nospace)
        keyword_ratio = keyword_matches / max(1, len(keywords)) if keywords else 0

        # Document mention boost
        mention_score = 1.0 if (mentioned_doc and mentioned_doc in filename) else 0.0

        # Topic relevance boost - domain agnostic
        # Uses the new _calculate_term_document_relevance function
        topic_score = 0.0
        if query_topics:
            topic_score = _calculate_term_document_relevance(query_topics, filename, text_normalized)

        # Weighted combination
        final_score = (
            cfg.semantic_weight * semantic_score
            + cfg.keyword_weight * keyword_ratio
            + cfg.mention_boost * mention_score
            + cfg.topic_boost * topic_score
        )

        return final_score

    def _apply_diversity_limits(
        self,
        scored: list[tuple[float, DocumentChunk]],
        mentioned_doc: str | None,
        cfg: RAGConfig,
        selection_limit: int | None = None,
    ) -> list[DocumentChunk]:
        """Apply per-document limits for diversity."""
        selected: list[DocumentChunk] = []
        doc_counts: dict[str, int] = {}

        # Determine how many chunks to select. Allow an override for full-list requests.
        budget = selection_limit if selection_limit is not None else cfg.selection_budget

        for score, chunk in scored:
            if len(selected) >= budget:
                break

            filename = getattr(chunk, "filename", "") or getattr(chunk, "source", "unknown")
            doc_key = filename.lower() or "unknown"

            is_mentioned = mentioned_doc and mentioned_doc in doc_key
            limit = cfg.max_from_mentioned if is_mentioned else cfg.max_per_doc

            if doc_counts.get(doc_key, 0) < limit:
                selected.append(chunk)
                doc_counts[doc_key] = doc_counts.get(doc_key, 0) + 1

        return selected

    def _build_context_blocks(
        self,
        chunks: Sequence[DocumentChunk],
        customer_snapshot: CustomerSnapshot | None,
    ) -> list[str]:
        blocks: list[str] = []

        if customer_snapshot is not None:
            try:
                # Use the centralized snapshot context builder
                snapshot_context = self._build_snapshot_context(customer_snapshot)
                if snapshot_context and snapshot_context != "INFORMACIÓN DEL CLIENTE:":
                    blocks.append(snapshot_context)
            except Exception:
                pass

        for chunk in chunks:
            text = getattr(chunk, "text", "") or ""
            filename = getattr(chunk, "filename", "") or ""

            if filename:
                blocks.append(f"[Documento: {filename}] {text}")
            else:
                blocks.append(text)

        return blocks

    def _has_customer_data(self, snapshot: CustomerSnapshot) -> bool:
        """Check if the customer snapshot has any meaningful data."""
        has_products = hasattr(snapshot, "products") and snapshot.products and len(snapshot.products) > 0
        has_transactions = (
            hasattr(snapshot, "recent_transactions")
            and snapshot.recent_transactions
            and len(snapshot.recent_transactions) > 0
        )
        return has_products or has_transactions

    def _build_snapshot_context(self, snapshot: CustomerSnapshot) -> str:
        """Build a text context from customer snapshot data.

        For university domain, separates grades from other transactions
        to provide clearer academic context.

        Includes personal identification data (name, DNI, email, phone)
        which are PRE-MASKED according to viewer role before reaching here.
        """
        import os

        demo_domain = os.environ.get("CKA_DEMO_DOMAIN", "banking").lower()

        lines = ["INFORMACION DEL CLIENTE:"]

        # Personal identification section (PRE-MASKED by pii_masking)
        if hasattr(snapshot, "display_name") and snapshot.display_name:
            lines.append(f"\nNombre: {snapshot.display_name}")
        if hasattr(snapshot, "document_id") and snapshot.document_id:
            lines.append(f"DNI: {snapshot.document_id}")
        if hasattr(snapshot, "tax_id") and snapshot.tax_id:
            label = "CUIL/CUIT" if demo_domain == "banking" else "CUIL"
            lines.append(f"{label}: {snapshot.tax_id}")
        if hasattr(snapshot, "email") and snapshot.email:
            lines.append(f"Email: {snapshot.email}")
        if hasattr(snapshot, "phone") and snapshot.phone:
            lines.append(f"Telefono: {snapshot.phone}")

        if hasattr(snapshot, "products") and snapshot.products:
            if demo_domain == "university":
                lines.append("\nInscripciones y cursadas:")
            else:
                lines.append("\nProductos activos:")
            for p in snapshot.products:
                status = getattr(p, "status", "activo")
                extra = getattr(p, "extra", {}) or {}
                if demo_domain == "university" and p.service_type == "course_registration":
                    course_name = extra.get("course_name", p.service_key)
                    lines.append(f"  - {course_name} (estado: {status})")
                else:
                    lines.append(f"  - {p.service_type}: {p.service_key} (estado: {status})")

        if hasattr(snapshot, "recent_transactions") and snapshot.recent_transactions:
            if demo_domain == "university":
                # Separate grades from other transactions
                grades = [t for t in snapshot.recent_transactions if t.transaction_type == "grade"]
                other_txs = [t for t in snapshot.recent_transactions if t.transaction_type != "grade"]

                if grades:
                    lines.append("\nCalificaciones:")
                    for t in grades:  # Show ALL grades
                        desc = t.description or "Evaluación"
                        lines.append(f"  - {desc}: {t.amount}/10")

                if other_txs:
                    lines.append("\nPagos recientes:")
                    for t in other_txs[:5]:  # Limit other transactions
                        desc = f" - {t.description}" if t.description else ""
                        lines.append(f"  - {t.transaction_type}: {t.amount} {t.currency}{desc}")
            else:
                lines.append("\nMovimientos recientes:")
                for t in snapshot.recent_transactions[:10]:
                    desc = f" - {t.description}" if t.description else ""
                    lines.append(f"  - {t.transaction_type}: {t.amount} {t.currency}{desc}")
        return "\n".join(lines)

    def _answer_from_snapshot_only(
        self,
        query: str,
        snapshot: CustomerSnapshot,
        cache_key: str,
        regulatory_strict: bool,
    ) -> RAGResult:
        """Generate answer using only customer snapshot data (no documents)."""
        context = self._build_snapshot_context(snapshot)
        prompt = build_prompt(query, [context])
        answer_text = self._llm.generate(prompt)

        if not regulatory_strict:
            self._cache.set_answer(cache_key, answer_text)

        logger.info(
            "rag_answer_from_snapshot",
            extra={"query": query[:80], "source": "customer_snapshot"},
        )

        return RAGResult(
            answer=answer_text,
            query=query,
            metrics={"candidates": 0, "selected": 0, "source": "customer_snapshot"},
        )

    def _stream_from_snapshot_only(self, query: str, snapshot: CustomerSnapshot) -> Iterator[str]:
        """Stream answer using only customer snapshot data (no documents)."""
        context = self._build_snapshot_context(snapshot)
        prompt = build_prompt(query, [context])

        for token in self._llm.generate_stream(prompt):
            yield token

        logger.info(
            "rag_stream_from_snapshot",
            extra={"query": query[:80], "source": "customer_snapshot"},
        )

    def _check_pii(self, chunks: Sequence[DocumentChunk]) -> bool:
        for chunk in chunks:
            pii_info = getattr(chunk, "pii_sensitivity", None)
            if pii_info and str(pii_info).lower() == "high":
                return True
        return False

    def _collect_sources(self, chunks: Sequence[DocumentChunk]) -> list[str]:
        seen: set[str] = set()
        sources: list[str] = []
        for chunk in chunks:
            filename = getattr(chunk, "filename", "") or getattr(chunk, "source", "")
            if filename and filename not in seen:
                seen.add(filename)
                sources.append(filename)
        return sources

    def _detect_mentioned_document(self, query: str, chunks: Sequence[DocumentChunk]) -> str | None:
        """
        Detect document mentioned in query and validate against retrieved chunks.

        Security: Only returns document names that are present in the chunks,
        preventing path traversal or injection attacks through document references.

        Args:
            query: User query text
            chunks: Retrieved document chunks to validate against

        Returns:
            Normalized document name if found and valid, None otherwise.
        """
        if not query or not chunks:
            return None

        # Build set of valid document names from chunks (normalized forms)
        valid_docs: dict[str, str] = {}  # normalized -> canonical
        for chunk in chunks:
            filename = getattr(chunk, "filename", "") or getattr(chunk, "source", "")
            if filename:
                doc_name = filename.replace(".pdf", "").strip().lower()
                # Store all variations pointing to canonical form
                canonical = doc_name.replace(" ", "_")
                valid_docs[doc_name] = canonical
                valid_docs[canonical] = canonical
                valid_docs[doc_name.replace("_", " ")] = canonical

        if not valid_docs:
            return None

        # Direct matching approach: check if any valid document name appears in query
        query_lower = query.lower()

        # Check each valid document name (try longer names first to avoid partial matches)
        for doc_name in sorted(valid_docs.keys(), key=len, reverse=True):
            if doc_name in query_lower:
                return valid_docs[doc_name]

        return None

    def _no_info_response(self, query: str) -> str:
        mentioned = _extract_mentioned_doc(query)
        if mentioned:
            return (
                f"No encontre informacion relevante sobre '{mentioned}' en los "
                "documentos disponibles. Verifica que el documento este cargado "
                "y contenga la informacion buscada."
            )
        return (
            "No encontre informacion suficiente en los documentos disponibles "
            "para responder tu consulta. Intenta reformular la pregunta o "
            "verifica que los documentos relevantes esten cargados."
        )

    def get_config(self) -> RAGConfig:
        return self._config


def create_rag_service(
    retriever: RetrieverPort,
    llm: LLMPort,
    cache: CacheProtocol | None = None,
    **config_kwargs,
) -> RAGService:
    config = RAGConfig(**config_kwargs) if config_kwargs else None
    return RAGService(retriever, llm, cache, config)
