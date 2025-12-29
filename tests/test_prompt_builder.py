"""Tests for prompt_builder - prompt construction for LLM.

Tests cover:
- Basic prompt construction
- Character budget enforcement
- History inclusion
- Domain-specific prompts
- Customer context prompts
"""

from __future__ import annotations

from cortex_ka.application.prompt_builder import (
    DOMAIN_PROMPT_ADDITIONS,
    SYSTEM_PROMPT_BASE,
    build_customer_context_prompt,
    build_prompt,
    build_prompt_simple,
)

# ---------------------------------------------------------------------------
# SYSTEM_PROMPT_BASE Tests
# ---------------------------------------------------------------------------


class TestSystemPromptBase:
    """Tests for the base system prompt."""

    def test_system_prompt_exists(self) -> None:
        """SYSTEM_PROMPT_BASE should be defined and non-empty."""
        assert SYSTEM_PROMPT_BASE is not None
        assert len(SYSTEM_PROMPT_BASE) > 100  # Should be substantial

    def test_system_prompt_spanish(self) -> None:
        """SYSTEM_PROMPT_BASE should be in Spanish for the target domain."""
        # Check for common Spanish words
        spanish_markers = ["documentación", "información", "respuesta", "pregunta"]
        prompt_lower = SYSTEM_PROMPT_BASE.lower()
        has_spanish = any(marker in prompt_lower for marker in spanish_markers)
        assert has_spanish, "System prompt should be in Spanish"


class TestDomainPromptAdditions:
    """Tests for domain-specific prompt additions."""

    def test_domain_additions_is_dict(self) -> None:
        """DOMAIN_PROMPT_ADDITIONS should be a dictionary."""
        assert isinstance(DOMAIN_PROMPT_ADDITIONS, dict)

    def test_domain_additions_values_are_strings(self) -> None:
        """All domain additions should be string values."""
        for key, value in DOMAIN_PROMPT_ADDITIONS.items():
            assert isinstance(key, str), f"Key {key} should be string"
            assert isinstance(value, str), f"Value for {key} should be string"


# ---------------------------------------------------------------------------
# build_prompt Tests
# ---------------------------------------------------------------------------


class TestBuildPrompt:
    """Tests for build_prompt function."""

    def test_basic_prompt_generation(self) -> None:
        """build_prompt should combine query with context."""
        query = "¿Cuál es el plazo de inscripción?"
        context = [
            "Chunk 1: El plazo es de 30 días.",
            "Chunk 2: Inscripciones abiertas.",
        ]

        prompt = build_prompt(query, context)

        assert query in prompt
        assert "30 días" in prompt
        assert "Inscripciones" in prompt

    def test_prompt_with_empty_context(self) -> None:
        """build_prompt should handle empty context gracefully."""
        query = "¿Pregunta sin contexto?"
        prompt = build_prompt(query, [])

        assert query in prompt
        # Should still produce a valid prompt structure

    def test_prompt_budget_enforcement(self) -> None:
        """build_prompt should respect character budget."""
        query = "Test query"
        # Create very large context chunks
        large_chunk = "X" * 5000
        context = [large_chunk] * 10  # 50k chars

        prompt = build_prompt(query, context, budget_chars=10000)

        # Prompt should be within budget (with some tolerance for structure)
        assert len(prompt) < 15000  # Allow overhead for prompt structure

    def test_prompt_includes_system_context(self) -> None:
        """build_prompt should include system prompt elements."""
        query = "Test"
        context = ["Some context"]

        prompt = build_prompt(query, context)

        # Should have structured sections
        assert len(prompt) > len(query) + len(context[0])

    def test_prompt_with_history(self) -> None:
        """build_prompt should incorporate conversation history."""
        query = "¿Y el segundo requisito?"
        context = ["Requisito 1: DNI", "Requisito 2: Foto carnet"]
        # history is list of (user_question, assistant_answer) tuples
        history = [
            ("¿Cuáles son los requisitos?", "Los requisitos son: DNI y foto."),
        ]

        prompt = build_prompt(query, context, history=history)

        # History should be incorporated
        assert "requisitos" in prompt.lower()


# ---------------------------------------------------------------------------
# build_prompt_simple Tests
# ---------------------------------------------------------------------------


class TestBuildPromptSimple:
    """Tests for build_prompt_simple function."""

    def test_simple_prompt_generation(self) -> None:
        """build_prompt_simple should create a basic prompt."""
        query = "¿Qué es el RAG?"
        context = "RAG significa Retrieval-Augmented Generation."

        prompt = build_prompt_simple(query, context)

        assert query in prompt
        assert "RAG" in prompt

    def test_simple_prompt_with_empty_context(self) -> None:
        """build_prompt_simple should handle empty context."""
        query = "Test"
        prompt = build_prompt_simple(query, "")

        assert query in prompt

    def test_simple_prompt_shorter_than_full(self) -> None:
        """build_prompt_simple should be more compact than full build_prompt."""
        query = "Test query"
        context_str = "Some context text."
        context_list = [context_str]

        simple = build_prompt_simple(query, context_str)
        full = build_prompt(query, context_list)

        # Simple should be more compact (no elaborate structure)
        assert len(simple) <= len(full)


# ---------------------------------------------------------------------------
# build_customer_context_prompt Tests
# ---------------------------------------------------------------------------


class TestBuildCustomerContextPrompt:
    """Tests for build_customer_context_prompt function."""

    def test_customer_context_generation(self) -> None:
        """build_customer_context_prompt should include customer data."""
        query = "¿Cuál es mi saldo?"
        doc_context = "Tu cuenta tiene un saldo de $1000."
        customer_context = "Cliente: Juan Pérez\nCuenta: 123456"

        prompt = build_customer_context_prompt(query, doc_context, customer_context)

        assert query in prompt
        assert "Juan Pérez" in prompt
        assert "123456" in prompt

    def test_customer_context_with_empty_data(self) -> None:
        """build_customer_context_prompt should handle empty customer data."""
        query = "Test"
        doc_context = "Some documentation"

        prompt = build_customer_context_prompt(query, doc_context, "")

        assert query in prompt

    def test_customer_context_full_structure(self) -> None:
        """build_customer_context_prompt should include all sections."""
        query = "Test query"
        doc_context = "Documentation section"
        customer_context = "Customer info section"

        prompt = build_customer_context_prompt(query, doc_context, customer_context)

        # Should include all three parts
        assert "Test query" in prompt
        assert "Documentation" in prompt
        assert "Customer" in prompt


# ---------------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge case tests for prompt builder."""

    def test_unicode_handling(self) -> None:
        """Prompt builder should handle unicode correctly."""
        query = "¿Cuántos años tiene la institución?"
        context = ["Fundada en el año 2000. Celebración del aniversario."]

        prompt = build_prompt(query, context)

        assert "años" in prompt
        assert "Celebración" in prompt

    def test_special_characters(self) -> None:
        """Prompt builder should handle special characters."""
        query = "Email: test@example.com & phone: 123-456"
        context = ["Contact info with <brackets> and 'quotes'."]

        prompt = build_prompt(query, context)

        # Should not crash or corrupt data
        assert "test@example.com" in prompt

    def test_very_short_query(self) -> None:
        """Prompt builder should handle very short queries."""
        prompt = build_prompt("?", ["context"])
        assert "?" in prompt

    def test_multiline_context(self) -> None:
        """Prompt builder should handle multiline context chunks."""
        query = "Test"
        context = ["Line 1\nLine 2\nLine 3", "Another\nchunk"]

        prompt = build_prompt(query, context)

        assert "Line 1" in prompt
        assert "Line 3" in prompt
