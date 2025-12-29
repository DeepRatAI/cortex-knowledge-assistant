"""Qdrant retriever adapter using local embeddings and query_points API.

Provides semantic similarity search against a named collection. Falls back gracefully
to an empty result if the service is unreachable or collection absent. Uses a single
named vector "text"; multi-vector or metadata filtering can be incorporated later.
"""

from __future__ import annotations

from typing import Any, Dict, List

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from ..config import settings
from ..domain.models import DocumentChunk, RetrievalResult
from ..domain.ports import RetrieverPort
from ..logging import logger
from .embedding_local import LocalEmbedder


class QdrantRetriever(RetrieverPort):
    """Retrieve document chunks from Qdrant by semantic similarity.

    Args:
        collection: Name of Qdrant collection containing document vectors.
        top_k: Default max results to return when k not specified.
    """

    def __init__(self, collection: str | None = None, top_k: int | None = None) -> None:
        self._collection = collection or settings.qdrant_collection_docs
        self._top_k = top_k or settings.qdrant_top_k
        self._client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None, timeout=30)
        self._embedder = LocalEmbedder()

    def _search_compat(
        self,
        collection_name: str,
        query_vector: list | None = None,
        query: list | None = None,
        using: str | None = None,
        limit: int | None = None,
        query_filter: Any | None = None,
        with_payload: bool = True,
    ) -> Any:
        """Compatibility wrapper for various qdrant-client APIs and the test DummyQdrant.

        The project historically used both ``search`` and ``query_points`` APIs and
        tests provide a ``DummyQdrant`` shim with slightly different signatures.
        This helper tries the most likely call patterns in order and falls back
        gracefully when a keyword argument like ``using`` is not accepted.

        qdrant-client >= 1.9 uses named vectors via the query_vector parameter
        as a tuple (vector_name, vector) instead of a separate `using` kwarg.
        """
        # For named vector collections with qdrant-client >= 1.9, we need to pass
        # query_vector as (name, vector) tuple instead of using the `using` kwarg.
        if using is not None and query_vector is not None:
            # Convert to named vector tuple format
            named_query_vector = (using, query_vector)
        else:
            named_query_vector = query_vector

        # Prefer the client's `search` method if present.
        if hasattr(self._client, "search"):
            # Strategy 1: Try with named vector tuple (qdrant-client >= 1.9)
            try:
                return self._client.search(
                    collection_name=collection_name,
                    query_vector=named_query_vector,
                    limit=limit or 5,
                    query_filter=query_filter,
                    with_payload=with_payload,
                )
            except (TypeError, Exception) as exc:
                msg = str(exc).lower()
                # If the error is about unknown arguments or tuple handling,
                # try alternative approaches
                if "unknown" not in msg and "using" not in msg and "tuple" not in msg:
                    raise

            # Strategy 2: Try with separate `using` kwarg (older clients)
            try:
                return self._client.search(
                    collection_name=collection_name,
                    query_vector=query_vector,
                    using=using,
                    limit=limit or 5,
                    query_filter=query_filter,
                    with_payload=with_payload,
                )
            except (TypeError, Exception) as exc:
                msg = str(exc).lower()
                if "using" not in msg and "unknown" not in msg:
                    raise

            # Strategy 3: Try without `using` at all (simplest form)
            return self._client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=limit or 5,
                query_filter=query_filter,
                with_payload=with_payload,
            )

        # Fallback: try `query_points` style API (newer qdrant-client versions).
        if hasattr(self._client, "query_points"):
            # For query_points, we pass the raw vector directly (not as a tuple).
            # The `using` parameter specifies the named vector field.
            q = query if query is not None else query_vector

            # If q is a named vector tuple (name, vector), extract just the vector
            if isinstance(q, tuple) and len(q) == 2 and isinstance(q[0], str):
                q = q[1]

            try:
                result = self._client.query_points(
                    collection_name=collection_name,
                    query=q,
                    limit=limit or 5,
                    query_filter=query_filter,
                    with_payload=with_payload,
                    using=using,
                )
                # query_points returns QueryResponse with .points attribute
                return result.points if hasattr(result, "points") else result
            except TypeError:
                # Try without using
                result = self._client.query_points(
                    collection_name=collection_name,
                    query=q,
                    limit=limit or 5,
                    query_filter=query_filter,
                    with_payload=with_payload,
                )
                return result.points if hasattr(result, "points") else result

        # If neither method exists, raise a clear error.
        raise AttributeError("qdrant client does not provide 'search' or 'query_points' methods")

    def _extract_mentioned_filename(self, query: str) -> str | None:
        """Extract a potential document filename mentioned in the CURRENT query.

        This helps users target specific documents by name. Examples:
        - "segun el documento programa_ortodoncia" -> "programa_ortodoncia"
        - "segun programa_ortodoncia.pdf" -> "programa_ortodoncia"
        - "en el libro_ortodoncia" -> "libro_ortodoncia"

        IMPORTANT: When the query includes conversation history (prefixed with
        "Previous context"), we ONLY extract from the "Current question:" part
        to avoid matching document names from earlier turns in the conversation.

        Security note: This only returns a potential filename pattern.
        The actual filtering happens at query time against documents
        the user already has access to (public or their own private docs).
        """
        import re

        # If the query contains conversation history, extract ONLY the current question
        # The format is: "Previous context...\n\nCurrent question: <actual question>"
        current_question_marker = "Current question:"
        if current_question_marker in query:
            # Extract everything after "Current question:"
            idx = query.index(current_question_marker)
            query = query[idx + len(current_question_marker) :].strip()

        query_lower = query.lower()

        # Common patterns for document mentions in Spanish queries
        # Order matters - more specific patterns first
        patterns = [
            # Pattern: filename in quotes (handles hyphens and special chars)
            r'"([\w\-_]+)\.pdf"',
            r"'([\w\-_]+)\.pdf'",
            # Pattern with explicit "documento/archivo/doc" keyword (supports hyphens)
            r"(?:segun|según|en)\s+(?:el\s+)?(?:documento|archivo|doc)\s+([\w\-_]+?)(?:\.pdf)?(?:\s|$|\?|,)",
            r"(?:documento|archivo|doc)\s+([\w\-_]+?)(?:\.pdf)?(?:\s|$|\?|,)",
            # Pattern: "segun <filename>.pdf" or "segun <filename>" (direct reference without "documento")
            r"(?:segun|según)\s+([\w\-_]+?)(?:\.pdf)?(?:\s|$|\?|,)",
            # Pattern: hyphen or underscore-separated names with "el/la" prefix
            r"(?:el|la)\s+([\w]+[\-_][\w\-_]+?)(?:\.pdf)?(?:\s|$|\?|,)",
            # Pattern: explicit .pdf extension anywhere in query (supports hyphens)
            r"([\w\-_]+)\.pdf",
        ]

        for pattern in patterns:
            match = re.search(pattern, query_lower)
            if match:
                potential_name = match.group(1).strip()
                # Remove .pdf suffix if captured
                if potential_name.endswith(".pdf"):
                    potential_name = potential_name[:-4]
                # Basic sanity check: at least 3 chars, alphanumeric with underscores/hyphens
                if len(potential_name) >= 3 and re.match(r"^[\w\-_]+$", potential_name):
                    return potential_name

        return None

    def _extract_significant_keywords(self, query: str, min_length: int = 6) -> list[str]:
        """Extract significant keywords from query for text search fallback.

        When semantic search fails (e.g., due to poorly parsed PDF text),
        we can use keyword matching as a fallback. This extracts words
        that are likely to be domain-specific and worth searching for.

        Args:
            query: The search query
            min_length: Minimum word length to consider (default 6 to skip common words)

        Returns:
            List of significant keywords (lowercase)
        """
        import re

        # Common Spanish stopwords and query artifacts to ignore
        stopwords = {
            "segun",
            "según",
            "documento",
            "archivo",
            "sobre",
            "dice",
            "tiene",
            "cuales",
            "cuáles",
            "donde",
            "cuando",
            "cuanto",
            "cuánto",
            "como",
            "porque",
            "porqué",
            "quien",
            "quién",
            "cuantos",
            "cuántos",
            "todos",
            "todas",
            "algunos",
            "algunas",
            "otros",
            "otras",
            "previous",
            "context",
            "current",
            "question",
            "answer",
        }

        # Extract words, keeping only alphanumeric
        words = re.findall(r"\b[a-záéíóúñü]+\b", query.lower())

        # Filter by length and stopwords
        keywords = [w for w in words if len(w) >= min_length and w not in stopwords]

        # Remove duplicates preserving order
        seen = set()
        unique = []
        for w in keywords:
            if w not in seen:
                seen.add(w)
                unique.append(w)

        return unique[:5]  # Max 5 keywords to avoid over-filtering

    def _extract_unit_number(self, query: str) -> str | None:
        """Extract a unit/chapter number from the query if present.

        Examples:
        - "unidad 7" -> "7"
        - "UNIDAD Nº18" -> "18"
        - "capitulo 3" -> "3"
        """
        import re

        query_lower = query.lower()

        patterns = [
            r"unidad\s*(?:n[º°o]?)?\s*(\d+)",
            r"capitulo\s*(?:n[º°o]?)?\s*(\d+)",
            r"tema\s*(?:n[º°o]?)?\s*(\d+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, query_lower)
            if match:
                return match.group(1)

        return None

    def _detect_institutional_intent(self, query: str) -> tuple[bool, list[str]]:
        """Detect if the query is about institutional/administrative topics.

        When users ask about calendar, careers, enrollment, fees, schedules, etc.,
        we should prioritize institutional documentation over academic textbooks.

        Returns:
            Tuple of (is_institutional, matching_categories)
            - is_institutional: True if the query seems to be about institutional topics
            - matching_categories: List of document category prefixes to prioritize
        """
        query_lower = query.lower()

        # If the query contains conversation history, extract ONLY the current question
        current_question_marker = "Current question:"
        if current_question_marker in query:
            idx = query.index(current_question_marker)
            query_lower = query[idx + len(current_question_marker) :].strip().lower()

        # Keywords that indicate institutional/administrative queries
        # Grouped by document category for targeted retrieval
        INSTITUTIONAL_KEYWORDS = {
            "calendario": [
                "calendario",
                "receso",
                "feriado",
                "asueto",
                "vacaciones",
                "semestre",
                "cuatrimestre",
                "parciales",
                "finales",
                "turnos",
                "inscripcion",
                "inscripciones",
                "mesa",
                "mesas",
                "examen",
                "examenes",
                "colacion",
                "defensa",
                "cursado",
                "cursada",
                "fecha",
                "fechas",
                "cuando empieza",
                "cuando termina",
                "cuando comienza",
                "cuando finaliza",
                "periodo",
                "periodos",
            ],
            "carreras": [
                "carrera",
                "carreras",
                "plan de estudio",
                "planes de estudio",
                "titulo",
                "titulacion",
                "licenciatura",
                "contador",
                "contadora",
                "administracion",
                "economia",
                "duracion",
                "materias de",
                "correlativas",
                "correlatividad",
                "programa",
                "programas",
            ],
            "institucional": [
                "institucion",
                "institucional",
                "secretaria",
                "secretarias",
                "autoridades",
                "rector",
                "decano",
                "consejo",
                "directivo",
                "contacto",
                "telefono",
                "email",
                "direccion",
                "horarios",
                "atencion",
                "sede",
                "campus",
                "edificio",
                "ubicacion",
                "historia",
                "mision",
                "vision",
                "valores",
            ],
            "financiero": [
                "beca",
                "becas",
                "arancel",
                "aranceles",
                "cuota",
                "cuotas",
                "pago",
                "pagos",
                "descuento",
                "descuentos",
                "costo",
                "costos",
                "precio",
                "precios",
                "matricula",
                "moratoria",
                "financiacion",
            ],
            "servicios": [
                "biblioteca",
                "laboratorio",
                "cafeteria",
                "comedor",
                "wifi",
                "estacionamiento",
                "seguro",
                "credencial",
                "carnet",
                "siu",
                "guarani",
                "campus virtual",
                "plataforma",
                "aula virtual",
            ],
            "extension": [
                "extension",
                "curso",
                "cursos",
                "taller",
                "talleres",
                "diplomatura",
                "diplomaturas",
                "capacitacion",
                "seminario",
            ],
            "posgrados": [
                "posgrado",
                "posgrados",
                "maestria",
                "doctorado",
                "especializacion",
                "master",
                "mba",
                "tesis",
                "tesina",
            ],
        }

        matching_categories = []
        match_count = 0

        for category, keywords in INSTITUTIONAL_KEYWORDS.items():
            for keyword in keywords:
                if keyword in query_lower:
                    if category not in matching_categories:
                        matching_categories.append(category)
                    match_count += 1

        # Consider it institutional if we have at least one keyword match
        # and the query doesn't seem to be asking about the concept itself
        # (e.g., "que es un calendario" vs "cuando es el receso")
        conceptual_indicators = [
            "que es",
            "qué es",
            "define",
            "definicion",
            "concepto de",
            "teoria de",
        ]
        is_conceptual = any(ind in query_lower for ind in conceptual_indicators)

        is_institutional = match_count > 0 and not is_conceptual

        return is_institutional, matching_categories

    def retrieve(
        self,
        query: str,
        k: int | None = None,
        subject_id: str | None = None,
        context_type: str | None = None,
    ) -> RetrievalResult:  # type: ignore[override]
        """Retrieve top-k chunks for ``query`` combining public and private docs.

        Args:
            query: The search query
            k: Maximum number of results
            subject_id: Optional subject/client ID for private documents
            context_type: Optional filter for document types:
                - "public_docs": Institutional documentation only (calendario, carreras, etc.)
                - "educational": Educational material only (textbooks, PDFs from biblioteca)
                - None: All public documents (default)

        Security / multi-tenant model (v1):

        * Documentos públicos (por ejemplo PDFs bancarios) se indexan sin
          ``metadata.info_personal.id_cliente`` y con ``source="documentacion_publica_pdf"``.
          Son visibles para todos los usuarios.
        * Documentos sensibles / por-cliente se indexan con
          ``metadata.info_personal.id_cliente`` y sólo deben ser visibles para
          el ``subject_id`` correspondiente (o empleados/admin autorizados).

        Estrategia de recuperación:

        1. Siempre buscamos en el corpus público (sin filtro por ``subject_id``).
        2. Si ``subject_id`` está presente, realizamos además una búsqueda
           filtrada por ``metadata.info_personal.id_cliente`` y fusionamos los
           resultados.
        """

        k = k or self._top_k
        try:
            vector: List[float] = self._embedder.embed([query])[0]
            # Collections are configured with named vectors (e.g. "text").
            # The Qdrant server requires the vector name to be specified for
            # named-vector collections; with this client we do that via the
            # "using" parameter while passing the raw vector as the query.
            vector_name = getattr(settings, "qdrant_vector_name", "text")

            # Estrategia general:
            # - Si la colección es el corpus bancario real (por defecto
            #   settings.qdrant_collection_docs), aplicamos el modelo
            #   público+privado: siempre se consulta la documentación
            #   pública y, si hay subject_id, además la sensible de ese
            #   cliente.
            # - Para otras colecciones genéricas usadas en tests o
            #   tooling (por ejemplo "demo" en DummyQdrant), mantenemos
            #   el comportamiento original: sólo se filtra por
            #   metadata.info_personal.id_cliente cuando se pasa
            #   subject_id, sin añadir resultados adicionales.

            is_primary_corpus = self._collection == settings.qdrant_collection_docs

            # Colección principal: público + privado.
            if is_primary_corpus:
                # 1) Búsqueda sobre corpus público (sin filtro de cliente).
                # Aceptamos múltiples tipos de fuentes públicas:
                # - "documentacion_publica_pdf": PDFs corporativos
                # - "documentacion_publica_txt": TXT files
                # - "documentacion_publica_md": Markdown files
                # - "corpus_bancario": corpus de FAQs bancarias
                # - "fce_iuc_demo": FCE-IUC university demo corpus
                # - cualquier doc que NO tenga metadata.info_personal.id_cliente
                import os

                demo_domain = os.environ.get("CKA_DEMO_DOMAIN", "banking").lower()

                # =============================================================
                # CONTEXT TYPE FILTERING
                # =============================================================
                # context_type determines which documents to search:
                # - "public_docs": Only institutional documentation (NO textbooks)
                # - "educational": Only educational material (textbooks/PDFs)
                # - None: All public documents (default behavior)
                #
                # For university domain, we distinguish by filename pattern:
                # - Institutional: files in calendario/, carreras/, institucional/, etc.
                # - Educational: PDF files (textbooks like apuntes_*.pdf, etc.)
                # =============================================================

                # Define institutional folder prefixes (documentation about the institution)
                # Folders containing institutional documentation
                # These correspond to metadata.folder values in Qdrant documents
                INSTITUTIONAL_FOLDERS = [
                    "calendario",
                    "carreras",
                    "datos_demo",
                    "extension",
                    "financiero",
                    "institucional",
                    "materias",
                    "noticias",
                    "posgrados",
                    "servicios",
                ]

                # Build appropriate filter based on context_type
                public_filter = None
                use_context_filtering = context_type in ("public_docs", "educational")

                if demo_domain == "university" and use_context_filtering:
                    # Apply context-specific filtering for university domain
                    if context_type == "public_docs":
                        # Only institutional documentation - filter by metadata.folder
                        # Match documents whose metadata.folder is one of the institutional folders
                        # Use a nested filter with should conditions inside must
                        folder_conditions = [
                            qmodels.FieldCondition(
                                key="metadata.folder",
                                match=qmodels.MatchValue(value=folder),
                            )
                            for folder in INSTITUTIONAL_FOLDERS
                        ]
                        # Create a sub-filter that requires at least one folder to match
                        folder_subfilter = qmodels.Filter(should=folder_conditions)
                        public_filter = qmodels.Filter(
                            must=[
                                qmodels.FieldCondition(
                                    key="source",
                                    match=qmodels.MatchValue(value="fce_iuc_demo"),
                                ),
                                folder_subfilter,  # This makes the should conditions mandatory
                            ],
                        )
                        logger.info(
                            "context_filter_applied",
                            context_type="public_docs",
                            description="Filtering to institutional documentation only (by folder)",
                            folder_count=len(INSTITUTIONAL_FOLDERS),
                        )

                    elif context_type == "educational":
                        # Only educational material - textbooks from 'libros' folder
                        # Match files from the 'libros' folder or with doc_type='textbook'
                        educational_conditions = [
                            qmodels.FieldCondition(
                                key="metadata.folder",
                                match=qmodels.MatchValue(value="libros"),
                            ),
                            qmodels.FieldCondition(
                                key="metadata.doc_type",
                                match=qmodels.MatchValue(value="textbook"),
                            ),
                        ]
                        # Create a sub-filter that requires at least one educational condition
                        educational_subfilter = qmodels.Filter(should=educational_conditions)
                        public_filter = qmodels.Filter(
                            must=[
                                qmodels.FieldCondition(
                                    key="source",
                                    match=qmodels.MatchValue(value="fce_iuc_demo"),
                                ),
                                educational_subfilter,  # This makes the should conditions mandatory
                            ],
                        )
                        logger.info(
                            "context_filter_applied",
                            context_type="educational",
                            description="Filtering to educational material (textbooks) only",
                        )
                else:
                    # Default behavior: all public sources
                    public_sources = [
                        "documentacion_publica_pdf",
                        "documentacion_publica_txt",
                        "documentacion_publica_md",
                        "corpus_bancario",
                    ]

                    # Add demo-specific sources based on domain
                    if demo_domain == "university":
                        public_sources.append("fce_iuc_demo")
                    elif demo_domain == "clinic":
                        public_sources.append("clinic_demo")

                    public_filter = qmodels.Filter(
                        should=[
                            qmodels.FieldCondition(
                                key="source",
                                match=qmodels.MatchValue(value=src),
                            )
                            for src in public_sources
                        ]
                    )

                public_hits = self._search_compat(
                    collection_name=self._collection,
                    query_vector=vector,
                    using=vector_name,
                    limit=k,
                    query_filter=public_filter,
                    with_payload=True,
                )

                # 1.5) Búsqueda prioritaria para documentos institucionales.
                # SKIP this when context_type is explicitly set (user chose a specific context)
                # Cuando el usuario pregunta sobre temas administrativos (calendario,
                # carreras, inscripciones, becas, etc.), priorizamos documentos de
                # esas categorías sobre los libros de texto académicos.
                institutional_hits: List[Any] = []

                # Only do institutional intent detection when no specific context is selected
                if not use_context_filtering:
                    is_institutional, matching_categories = self._detect_institutional_intent(query)

                    if is_institutional and matching_categories:
                        # Build filter to match institutional documents by folder
                        # Documents have metadata.folder with values like "calendario", "carreras", etc.
                        category_conditions = []
                        for category in matching_categories:
                            # Match documents whose metadata.folder matches the category
                            category_conditions.append(
                                qmodels.FieldCondition(
                                    key="metadata.folder",
                                    match=qmodels.MatchValue(value=category),
                                )
                            )

                        if category_conditions:
                            institutional_filter = qmodels.Filter(
                                must=[
                                    qmodels.FieldCondition(
                                        key="source",
                                        match=qmodels.MatchValue(value="fce_iuc_demo"),
                                    ),
                                ],
                                should=category_conditions,
                            )

                            try:
                                institutional_hits = self._search_compat(
                                    collection_name=self._collection,
                                    query_vector=vector,
                                    using=vector_name,
                                    limit=k,
                                    query_filter=institutional_filter,
                                    with_payload=True,
                                )
                                logger.info(
                                    "institutional_intent_search",
                                    is_institutional=True,
                                    categories=matching_categories,
                                    hits=len(institutional_hits),
                                )
                            except Exception as exc:
                                logger.warning(
                                    "institutional_search_failed",
                                    error=str(exc),
                                )

                # 2) Búsqueda adicional por subject_id (documentación sensible).
                private_hits: List[Any] = []
                if subject_id:
                    private_filter = qmodels.Filter(
                        must=[
                            qmodels.FieldCondition(
                                key="metadata.info_personal.id_cliente",
                                match=qmodels.MatchValue(value=subject_id),
                            )
                        ]
                    )
                    private_hits = self._search_compat(
                        collection_name=self._collection,
                        query_vector=vector,
                        using=vector_name,
                        limit=k,
                        query_filter=private_filter,
                        with_payload=True,
                    )

                # 3) Búsqueda adicional filtrada por documento mencionado.
                # Si el usuario menciona explícitamente un documento (ej:
                # "segun el documento programa_ortodoncia"), hacemos una
                # búsqueda adicional filtrada por filename para asegurar
                # que incluimos chunks de ese documento específico.
                mentioned_doc_hits: List[Any] = []
                mentioned_filename = self._extract_mentioned_filename(query)
                if mentioned_filename:
                    # Try matching by filename field (contains match for flexibility)
                    mentioned_filter = qmodels.Filter(
                        should=[
                            qmodels.FieldCondition(
                                key="filename",
                                match=qmodels.MatchText(text=mentioned_filename),
                            ),
                            # Also try exact match on doc_id suffix
                            qmodels.FieldCondition(
                                key="doc_id",
                                match=qmodels.MatchText(text=mentioned_filename),
                            ),
                        ]
                    )
                    try:
                        mentioned_doc_hits = self._search_compat(
                            collection_name=self._collection,
                            query_vector=vector,
                            using=vector_name,
                            limit=k,
                            query_filter=mentioned_filter,
                            with_payload=True,
                        )
                        logger.info(
                            "mentioned_doc_search",
                            mentioned_filename=mentioned_filename,
                            hits=len(mentioned_doc_hits),
                        )
                    except Exception as exc:
                        # MatchText may not be supported; fall back silently
                        logger.warning(
                            "mentioned_doc_search_failed",
                            error=str(exc),
                        )

                # 4) Búsqueda de texto cuando el usuario pregunta por una
                # "unidad/capitulo X" específica. La búsqueda semántica puede
                # no ser efectiva para este tipo de queries numéricas.
                text_search_hits: List[Any] = []
                unit_number = self._extract_unit_number(query)
                if unit_number and mentioned_filename:
                    # Search for text containing the unit number pattern
                    try:
                        # Use scroll with text filter to find chunks containing unit
                        text_filter = qmodels.Filter(
                            must=[
                                qmodels.FieldCondition(
                                    key="filename",
                                    match=qmodels.MatchText(text=mentioned_filename),
                                ),
                                qmodels.FieldCondition(
                                    key="text",
                                    match=qmodels.MatchText(text="UNIDAD"),
                                ),
                            ]
                        )
                        scroll_result = self._client.scroll(
                            collection_name=self._collection,
                            scroll_filter=text_filter,
                            limit=50,
                            with_payload=True,
                        )
                        # Filter results that actually contain the unit number
                        for point in scroll_result[0]:
                            text = point.payload.get("text", "").upper()
                            # Match patterns like "UNIDAD Nº7", "UNIDAD 7", etc.
                            if "UNIDAD N" in text or "UNIDAD " in text:
                                import re

                                if re.search(
                                    rf"UNIDAD\s*(?:N[º°O]?)?\s*{unit_number}\b",
                                    text,
                                    re.IGNORECASE,
                                ):
                                    text_search_hits.append(point)

                        if text_search_hits:
                            logger.info(
                                "unit_text_search",
                                unit_number=unit_number,
                                mentioned_filename=mentioned_filename,
                                hits=len(text_search_hits),
                            )
                    except Exception as exc:
                        logger.warning(
                            "unit_text_search_failed",
                            error=str(exc),
                        )

                # 5) Keyword-based text search fallback.
                # When user mentions a specific document and the semantic search
                # might miss content (e.g., due to poorly parsed PDF text without
                # proper spacing), we do a keyword search as fallback.
                keyword_hits: List[Any] = []
                if mentioned_filename:
                    keywords = self._extract_significant_keywords(query)
                    if keywords:
                        try:
                            # Get all chunks from the mentioned document
                            doc_filter = qmodels.Filter(
                                must=[
                                    qmodels.FieldCondition(
                                        key="filename",
                                        match=qmodels.MatchValue(value=mentioned_filename),
                                    ),
                                ]
                            )
                            scroll_result = self._client.scroll(
                                collection_name=self._collection,
                                scroll_filter=doc_filter,
                                limit=100,  # Limit to avoid timeout
                                with_payload=True,
                            )

                            # Find chunks containing keywords and score them by:
                            # - Number of keywords found
                            # - Priority for longer/more specific keywords
                            # (case-insensitive, handles text without spaces)
                            seen_ids = {str(getattr(h, "id", "")) for h in mentioned_doc_hits}
                            keyword_scored: list[tuple[Any, int]] = []

                            # Sort keywords by length (longer = more specific = higher priority)
                            sorted_keywords = sorted(keywords, key=len, reverse=True)

                            for point in scroll_result[0]:
                                if str(point.id) in seen_ids:
                                    continue  # Already have this from semantic search
                                text_lower = point.payload.get("text", "").lower()
                                text_no_spaces = text_lower.replace(" ", "")

                                # Score based on keyword matches
                                score = 0
                                for i, kw in enumerate(sorted_keywords):
                                    # Higher base score for longer keywords
                                    base_score = len(kw)
                                    # Bonus for earlier (more specific) keywords
                                    position_bonus = len(sorted_keywords) - i
                                    if kw in text_lower or kw in text_no_spaces:
                                        score += base_score + position_bonus

                                if score > 0:
                                    keyword_scored.append((point, score))
                                    seen_ids.add(str(point.id))

                            # Sort by score (descending) - chunks with more/longer keywords first
                            keyword_scored.sort(key=lambda x: x[1], reverse=True)
                            keyword_hits = [item[0] for item in keyword_scored]

                            if keyword_hits:
                                logger.info(
                                    "keyword_text_search",
                                    keywords=keywords,
                                    mentioned_filename=mentioned_filename,
                                    hits=len(keyword_hits),
                                    top_scores=[s for _, s in keyword_scored[:5]],
                                )
                        except Exception as exc:
                            logger.warning(
                                "keyword_text_search_failed",
                                error=str(exc),
                            )

                # IMPORTANT: Priority order for hit fusion:
                # 1. text_search_hits - exact text matches (e.g., "UNIDAD 7")
                # 2. keyword_hits - keyword-based matches in mentioned documents
                # 3. institutional_hits - documents from institutional categories (calendario, carreras, etc.)
                #    when the query is about administrative topics
                # 4. mentioned_doc_hits - results from explicitly mentioned documents
                # 5. public_hits - general semantic search results
                # 6. private_hits - user-specific private documents
                hits = (
                    list(text_search_hits)
                    + list(keyword_hits)
                    + list(institutional_hits)
                    + list(mentioned_doc_hits)
                    + list(public_hits)
                    + list(private_hits)
                )

                logger.info(
                    "qdrant_retrieval",
                    query=query,
                    subject_id=subject_id,
                    public_hits=len(public_hits),
                    private_hits=len(private_hits),
                    institutional_hits=len(institutional_hits),
                    text_search_hits=len(text_search_hits),
                    keyword_hits=len(keyword_hits),
                    total_hits=len(hits),
                )
            else:
                # Colecciones no principales (como "demo" en los tests):
                # preservamos el contrato original de aislamiento por
                # id_cliente sin mezclar con otros tipos de documentos.
                q_filter = None
                if subject_id:
                    q_filter = qmodels.Filter(
                        must=[
                            qmodels.FieldCondition(
                                key="metadata.info_personal.id_cliente",
                                match=qmodels.MatchValue(value=subject_id),
                            )
                        ]
                    )
                hits = self._search_compat(
                    collection_name=self._collection,
                    query_vector=vector,
                    using=vector_name,
                    limit=k,
                    query_filter=q_filter,
                    with_payload=True,
                )

                logger.info(
                    "qdrant_retrieval",
                    query=query,
                    subject_id=subject_id,
                    public_hits=0,
                    private_hits=len(hits),
                    total_hits=len(hits),
                )
            chunks: list[DocumentChunk] = []
            for h in hits:
                payload: Dict[str, Any] = getattr(h, "payload", {}) or {}

                # Optional enforcement: skip chunks explicitly marked as
                # high-sensitivity PII. This relies on the ingestion pipeline
                # populating payload["pii"]["sensitivity"] using
                # `classify_pii`. We do this unconditionally here because the
                # classifier is lightweight and deterministic, and banking
                # contexts generally prefer to err on the side of caution.
                pii_info = payload.get("pii") or {}
                if isinstance(pii_info, dict) and pii_info.get("sensitivity") == "high":
                    continue
                # Normalize possible payload key variations
                text = payload.get("text") or payload.get("chunk") or payload.get("content") or ""
                source = payload.get("source") or payload.get("doc") or payload.get("document") or "unknown"
                pii_info = payload.get("pii") or {}
                pii_sensitivity = None
                if isinstance(pii_info, dict):
                    val = pii_info.get("sensitivity")
                    if isinstance(val, str):
                        pii_sensitivity = val
                if text:
                    chunks.append(
                        DocumentChunk(
                            id=str(getattr(h, "id", "")),
                            text=str(text),
                            source=str(source),
                            doc_id=payload.get("doc_id"),
                            filename=payload.get("filename"),
                            score=getattr(h, "score", None),
                            pii_sensitivity=pii_sensitivity,
                        )
                    )
            return RetrievalResult(query=query, chunks=chunks)
        except Exception as exc:  # pragma: no cover - defensive path
            logger.warning("qdrant_retrieval_failed", error=str(exc))
            return RetrievalResult(query=query, chunks=[])
