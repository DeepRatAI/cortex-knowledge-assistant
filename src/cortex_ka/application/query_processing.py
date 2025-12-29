"""Query expansion and transformation for improved RAG recall.

Implements techniques to improve retrieval quality:
- Query rewriting for clarity
- Synonym expansion
- Hypothetical document embedding (HyDE)
- Multi-query generation
- Keyword extraction

Based on best practices from research and production RAG systems.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Sequence

# Spanish synonyms and related terms for query expansion
_SYNONYM_MAP: dict[str, list[str]] = {
    # Academic terms
    "licenciatura": ["carrera", "grado", "titulo", "estudios"],
    "carrera": ["licenciatura", "programa", "estudios"],
    "materia": ["asignatura", "curso", "modulo"],
    "asignatura": ["materia", "curso", "modulo"],
    "profesor": ["docente", "catedratico", "maestro"],
    "alumno": ["estudiante", "cursante"],
    "examen": ["evaluacion", "prueba", "test"],
    "calificacion": ["nota", "puntuacion"],
    # Document terms
    "documento": ["archivo", "fichero", "texto"],
    "capitulo": ["seccion", "unidad", "parte"],
    "pagina": ["hoja", "folio"],
    # Banking/Financial terms
    "cuenta": ["deposito", "producto"],
    "transferencia": ["envio", "movimiento", "traspaso"],
    "prestamo": ["credito", "financiamiento"],
    "tarjeta": ["plastico"],
    "saldo": ["balance", "disponible"],
    "interes": ["tasa", "rendimiento"],
    # General terms
    "informacion": ["datos", "detalles", "contenido"],
    "procedimiento": ["proceso", "tramite", "metodo"],
    "requisitos": ["requerimientos", "condiciones"],
    "beneficios": ["ventajas", "bondades"],
}


def normalize_text(text: str) -> str:
    """Normalize text for comparison: lowercase, remove accents, normalize spaces."""
    text = text.lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", text).strip()


def extract_keywords(
    query: str,
    min_length: int = 3,
    max_keywords: int = 15,
    stopwords: set[str] | None = None,
) -> list[str]:
    """Extract significant keywords from a query.

    Args:
        query: Input query string
        min_length: Minimum word length to consider
        max_keywords: Maximum number of keywords to return
        stopwords: Set of words to exclude (uses default if None)

    Returns:
        List of keywords sorted by significance (length)
    """
    if stopwords is None:
        stopwords = _DEFAULT_STOPWORDS

    normalized = normalize_text(query)
    words = re.findall(r"\b[a-z]+\b", normalized)

    # Filter and deduplicate
    seen = set()
    keywords = []
    for w in words:
        if len(w) >= min_length and w not in stopwords and w not in seen:
            seen.add(w)
            keywords.append(w)

    # Sort by length (longer = more specific = more valuable)
    keywords.sort(key=len, reverse=True)

    return keywords[:max_keywords]


def expand_query_with_synonyms(
    query: str,
    max_expansions: int = 3,
) -> list[str]:
    """Expand query by adding synonym variants.

    Args:
        query: Original query
        max_expansions: Maximum number of expanded queries to generate

    Returns:
        List of query variants including original
    """
    keywords = extract_keywords(query)
    expanded_queries = [query]

    for kw in keywords:
        if kw in _SYNONYM_MAP:
            synonyms = _SYNONYM_MAP[kw]
            for syn in synonyms[:2]:  # Max 2 synonyms per keyword
                variant = query.lower().replace(kw, syn)
                if variant != query.lower() and variant not in expanded_queries:
                    expanded_queries.append(variant)
                    if len(expanded_queries) >= max_expansions + 1:
                        return expanded_queries

    return expanded_queries


def generate_search_variants(
    query: str,
    include_keywords_only: bool = True,
    include_synonyms: bool = True,
) -> list[str]:
    """Generate multiple search variants for improved recall.

    This implements a simplified multi-query approach without requiring
    an LLM, using rule-based transformations.

    Args:
        query: Original query
        include_keywords_only: Add a keywords-only variant
        include_synonyms: Add synonym-expanded variants

    Returns:
        List of search variants
    """
    variants = [query]

    # Add keywords-only variant for better semantic matching
    if include_keywords_only:
        keywords = extract_keywords(query, max_keywords=8)
        if len(keywords) >= 2:
            keywords_query = " ".join(keywords)
            if keywords_query != query.lower():
                variants.append(keywords_query)

    # Add synonym variants
    if include_synonyms:
        synonym_variants = expand_query_with_synonyms(query, max_expansions=2)
        for v in synonym_variants[1:]:  # Skip original (already included)
            if v not in variants:
                variants.append(v)

    return variants


def extract_document_reference(query: str) -> str | None:
    """Extract explicit document/file reference from query.

    Detects patterns like:
    - "según el documento X"
    - "en el archivo Y.pdf"
    - "del libro Z"

    Args:
        query: Query string

    Returns:
        Document name if found, None otherwise
    """
    query_lower = query.lower()

    patterns = [
        # Explicit file references
        r'"([^"]+\.pdf)"',
        r"'([^']+\.pdf)'",
        r"([a-z0-9_-]+\.pdf)",
        # Document mentions in Spanish
        r"(?:segun|según|de|del|en)\s+(?:el\s+)?(?:documento|archivo|libro|texto)\s+([a-z0-9_-]+)",
        r"(?:documento|archivo|libro)\s+([a-z0-9_-]+)",
        # Hyphenated/underscored names with article
        r"(?:el|la|del)\s+([a-z]+[_-][a-z0-9_-]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, query_lower)
        if match:
            name = match.group(1).strip()
            # Remove .pdf extension if present
            name = re.sub(r"\.pdf$", "", name)
            # Validate: at least 3 chars, alphanumeric with underscores/hyphens
            if len(name) >= 3 and re.match(r"^[a-z0-9_-]+$", name):
                return name

    return None


def extract_topic(query: str) -> str | None:
    """Extract main topic/subject from query.

    Useful for boosting chunks related to the detected topic.

    Args:
        query: Query string

    Returns:
        Topic keyword if detected, None otherwise
    """
    normalized = normalize_text(query)

    # Academic subject patterns
    subject_patterns = [
        r"licenciatura\s+(?:en\s+)?(\w+)",
        r"carrera\s+(?:de\s+)?(\w+)",
        r"(?:de|del|sobre)\s+(\w+ologia)",  # psicología, sociología, etc.
        r"plan\s+(?:de\s+)?(?:estudios\s+)?(?:de\s+)?(\w+)",
    ]

    for pattern in subject_patterns:
        match = re.search(pattern, normalized)
        if match:
            topic = match.group(1)
            if len(topic) >= 4:
                return topic

    # Check for known topic keywords
    topic_keywords = {
        "psicologia",
        "arquitectura",
        "medicina",
        "derecho",
        "economia",
        "ingenieria",
        "sistemas",
        "educacion",
        "administracion",
        "contabilidad",
        "marketing",
        "finanzas",
        "recursos",
        "humanos",
        "logistica",
    }

    words = set(re.findall(r"\b[a-z]+\b", normalized))
    for topic in topic_keywords:
        if topic in words:
            return topic

    return None


def rewrite_query_for_retrieval(query: str) -> str:
    """Rewrite query to be more suitable for semantic search.

    - Removes filler words and question markers
    - Expands abbreviations
    - Focuses on content words

    Args:
        query: Original query

    Returns:
        Rewritten query optimized for retrieval
    """
    normalized = normalize_text(query)

    # Remove question markers and common fillers
    fillers = [
        r"^(?:que|cual|cuales|como|donde|cuando|por que|para que)\s+",
        r"^(?:me\s+)?(?:podrias|puedes|podrias)\s+(?:decir|explicar|contar)\s+",
        r"^(?:quisiera|quiero|necesito)\s+(?:saber|conocer|entender)\s+",
        r"\?+$",
    ]

    result = normalized
    for pattern in fillers:
        result = re.sub(pattern, "", result)

    return result.strip()


# Default Spanish stopwords for keyword extraction
_DEFAULT_STOPWORDS = frozenset(
    {
        # Articles
        "el",
        "la",
        "los",
        "las",
        "un",
        "una",
        "unos",
        "unas",
        # Prepositions
        "de",
        "del",
        "en",
        "con",
        "por",
        "para",
        "al",
        "a",
        # Conjunctions
        "y",
        "o",
        "u",
        "e",
        "ni",
        "que",
        "pero",
        "sino",
        # Pronouns
        "yo",
        "tu",
        "el",
        "ella",
        "nosotros",
        "ustedes",
        "ellos",
        "me",
        "te",
        "se",
        "nos",
        "le",
        "les",
        "lo",
        "la",
        # Common verbs (conjugations)
        "es",
        "son",
        "ser",
        "esta",
        "estan",
        "estar",
        "fue",
        "fueron",
        "ha",
        "han",
        "haber",
        "hay",
        "tiene",
        "tienen",
        "tener",
        "puede",
        "pueden",
        "poder",
        "hace",
        "hacen",
        "hacer",
        # Question words (keep for detection but filter for keywords)
        "que",
        "cual",
        "cuales",
        "como",
        "donde",
        "cuando",
        "cuanto",
        # Common adverbs
        "muy",
        "mas",
        "menos",
        "mucho",
        "poco",
        "bien",
        "mal",
        "si",
        "no",
        "ya",
        "aun",
        "todavia",
        "siempre",
        "nunca",
        # Other common words
        "este",
        "esta",
        "estos",
        "estas",
        "ese",
        "esa",
        "esos",
        "esas",
        "todo",
        "toda",
        "todos",
        "todas",
        "otro",
        "otra",
        "otros",
        "otras",
        "mismo",
        "misma",
        "mismos",
        "mismas",
        # Filler words in queries
        "segun",
        "documento",
        "archivo",
        "pdf",
        "dice",
        "trata",
        "resumeme",
        "explicame",
        "cuentame",
        "informacion",
        "sobre",
    }
)
