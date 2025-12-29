"""Prompt builder for RAG generation.

Encapsulates construction of prompts from retrieved chunks and optional
conversation history. Applies a simple character budget to avoid oversizing
the context window.
"""

from __future__ import annotations

import os
from typing import Iterable, Sequence, Tuple

# =============================================================================
# SYSTEM PROMPTS - Domain-configurable via CKA_DEMO_DOMAIN environment variable
# =============================================================================

# Base system prompt (common to all domains)
SYSTEM_PROMPT_BASE = """Eres un asistente de conocimiento experto y profesional. Tu rol es ayudar a los usuarios respondiendo preguntas basandote en la documentacion proporcionada en el contexto.

## REGLAS FUNDAMENTALES:

1. **Usa la informacion del contexto proporcionado**. Si el contexto contiene informacion relevante a la pregunta, DEBES usarla para responder.

2. **Responde siempre en espanol**, de manera clara, profesional y completa.

3. **FORMATO DE RESPUESTA - CRITICO**:
   - Escribe de forma FLUIDA y CONVERSACIONAL.
   - USA UN SOLO SALTO DE LINEA entre parrafos, nunca dos o mas.
   - NO dejes lineas en blanco excesivas.
   - Usa listas SOLO cuando sea necesario enumerar items.
   - Para formulas matematicas, usa notacion LaTeX: $formula$ para inline o $$formula$$ para bloque.
   - Ejemplo de formula: La probabilidad es $P(X=k) = \\frac{e^{-\\lambda} \\lambda^k}{k!}$

4. **Se flexible con los temas**: La documentacion puede cubrir cualquier area.

5. **Nunca inventes** datos que no esten en el contexto.

6. **RESPONDE COMPLETO**: Da respuestas completas sin cortarte a mitad de frase. Termina siempre tus explicaciones.

7. **Tono**: Profesional pero cercano."""


# Domain-specific additions (appended when CKA_DEMO_DOMAIN is set)
DOMAIN_PROMPT_ADDITIONS = {
    "university": """

## ROL ADICIONAL: ASISTENTE ACADEMICO (FCE-IUC)

Ademas de responder consultas, actuas como tutor academico del Instituto Universitario Cortex:

- **Explicaciones pedagogicas**: Cuando expliques conceptos de materias (contabilidad, economia, administracion, etc.), hazlo de manera didactica, con ejemplos practicos cuando sea apropiado.

- **Material de estudio**: Si el contexto incluye programas de materias o material educativo, referencialo para que el alumno pueda profundizar.

- **Motivacion**: Usa un tono motivador y constructivo, animando al estudiante en su proceso de aprendizaje.

- **Precision academica**: En temas tecnicos (normas contables, legislacion, formulas), se riguroso y preciso.

- **Contexto institucional**: Conoces la estructura de FCE-IUC, sus carreras, programas y servicios.""",
    "clinic": """

## ROL ADICIONAL: ASISTENTE DE GESTION CLINICA

Ademas de responder consultas, actuas como asistente administrativo de una clinica privada:

- **Informacion medica**: Proporciona informacion administrativa sobre servicios, turnos y procedimientos. NO des consejos medicos.

- **Precision**: En temas de facturacion, cobertura y tramites, se preciso y claro.

- **Empatia**: Usa un tono empatico y profesional apropiado para el contexto de salud.""",
    "banking": "",  # Default - no additions needed
}


def _get_system_prompt() -> str:
    """Get the appropriate system prompt based on domain configuration."""
    domain = os.environ.get("CKA_DEMO_DOMAIN", "banking").lower()
    addition = DOMAIN_PROMPT_ADDITIONS.get(domain, "")
    return SYSTEM_PROMPT_BASE + addition


# Backward compatibility: SYSTEM_PROMPT_ES now calls function for dynamic domain support
# Note: This is evaluated at import time for backward compat, but build_prompt()
# calls _get_system_prompt() directly for runtime flexibility.
SYSTEM_PROMPT_ES = _get_system_prompt()


def build_prompt(
    query: str,
    chunk_texts: Sequence[str],
    history: Iterable[Tuple[str, str]] | None = None,
    budget_chars: int = 12000,
    include_system_prompt: bool = True,
) -> str:
    """Assemble a concise, professional prompt.

    Args:
        query: The current user question.
        chunk_texts: Context chunks ordered by relevance.
        history: Optional list of previous (user, assistant) tuples.
        budget_chars: Maximum characters allowed for the final prompt.
        include_system_prompt: Whether to include the system prompt.
    Returns:
        Prompt string ready for the LLM.
    """
    # System prompt - call function for runtime domain detection
    system_prompt = _get_system_prompt()
    header = system_prompt + "\n\n" if include_system_prompt else ""

    # Conversation history (if any)
    hist = ""
    if history:
        hist_lines = []
        for q, a in history:
            hist_lines.append(f"Usuario: {q}")
            hist_lines.append(f"Asistente: {a}")
        hist = "### Conversación previa:\n" + "\n".join(hist_lines) + "\n\n"

    # Context header
    context_header = "### Documentación de referencia:\n\n"

    # Build context from chunks, respecting budget
    bullet_chunks: list[str] = []
    used = len(header) + len(hist) + len(context_header) + len(query) + 150  # reserve for question section

    for i, t in enumerate(chunk_texts, 1):
        # Format chunk with number for reference
        bullet = f"[Doc {i}] {t.strip()}\n"
        if used + len(bullet) > budget_chars:
            break
        bullet_chunks.append(bullet)
        used += len(bullet)

    # If no chunks, note it
    if not bullet_chunks:
        context_section = context_header + "(No se encontró documentación relevante para esta consulta)\n\n"
    else:
        context_section = context_header + "\n".join(bullet_chunks) + "\n"

    # Question section - detect if user wants complete list
    query_lower = query.lower()
    wants_full_list = any(
        phrase in query_lower
        for phrase in [
            "toda la lista",
            "lista completa",
            "todos los",
            "todas las",
            "enumera todo",
            "dame todo",
            "listame todo",
            "la lista completa",
        ]
    )

    if wants_full_list:
        list_instruction = """
IMPORTANTE: El usuario solicita una LISTA COMPLETA. Debes:
- Enumerar TODOS los elementos que encuentres en la documentación
- NO resumir ni omitir ningún punto
- Usar numeración (1, 2, 3...) para cada elemento
- Incluir subapartados si los hay (a, b, c...)
- EVITAR REPETICIONES: si un elemento ya fue mencionado, no lo repitas
- Agrupa los elementos por categoría si corresponde (ej: "En materia económica:", "En materia judicial:")
"""
    else:
        list_instruction = ""

    question_section = f"""### Pregunta del usuario:
{query}
{list_instruction}
### Tu respuesta (en español, basada solo en la documentación anterior):
"""

    return header + hist + context_section + question_section


def build_prompt_simple(
    query: str,
    context: str,
    language: str = "es",
) -> str:
    """Build a simpler prompt for quick queries.

    Args:
        query: User question.
        context: Pre-formatted context string.
        language: Response language code.
    Returns:
        Formatted prompt string.
    """
    if language == "es":
        return f"""Contexto:
{context}

Pregunta: {query}

Responde de manera profesional y concisa, basándote únicamente en el contexto proporcionado. Si no hay información suficiente, indícalo claramente."""
    else:
        return f"""Context:
{context}

Question: {query}

Answer professionally and concisely, based only on the provided context. If there is not enough information, state it clearly."""


def build_customer_context_prompt(
    query: str,
    doc_context: str,
    customer_context: str,
) -> str:
    """Build prompt that includes both documentation and customer-specific context.

    Args:
        query: User question.
        doc_context: Documentation chunks.
        customer_context: Customer snapshot (products, transactions).
    Returns:
        Formatted prompt string.
    """
    # Use dynamic system prompt for domain-specific behavior
    system_prompt = _get_system_prompt()

    return f"""{system_prompt}

### Información del cliente actual:
{customer_context}

### Documentación de referencia:
{doc_context}

### Pregunta:
{query}

### Tu respuesta (personalizada para este cliente, basada en su información y la documentación):
"""
