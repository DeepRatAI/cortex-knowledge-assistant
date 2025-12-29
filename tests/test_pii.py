"""Tests for PII redaction functionality."""

from cortex_ka.application.pii import redact_pii


class TestRedactPii:
    """Test suite for PII redaction."""

    def test_redacts_dni(self):
        """DNI numbers should be redacted."""
        text = "El DNI del cliente es 12345678"
        result = redact_pii(text)
        assert "12345678" not in result
        assert "<dni-redacted>" in result

    def test_redacts_cuit(self):
        """CUIT/CUIL numbers should be redacted or partially masked."""
        text = "CUIT: 20-12345678-9"
        result = redact_pii(text)
        # Either full CUIT redaction or DNI portion is redacted
        assert "12345678" not in result

    def test_redacts_card_number(self):
        """Credit card numbers should be redacted."""
        text = "Tarjeta: 4111-1111-1111-1111"
        result = redact_pii(text)
        assert "4111" not in result
        assert "<card-redacted>" in result

    def test_redacts_email(self):
        """Email addresses should be redacted."""
        text = "Contacto: usuario@ejemplo.com"
        result = redact_pii(text)
        assert "usuario@ejemplo.com" not in result
        assert "<email-redacted>" in result

    def test_preserves_normal_text(self):
        """Normal text without PII should be preserved."""
        text = "Este es un texto normal sin datos sensibles."
        result = redact_pii(text)
        assert result == text

    def test_handles_empty_string(self):
        """Empty string should return empty string."""
        assert redact_pii("") == ""
