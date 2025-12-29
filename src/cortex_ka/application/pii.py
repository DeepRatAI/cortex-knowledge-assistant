"""PII redaction utilities shared across API and DLP layers."""

from __future__ import annotations

import re


def redact_pii(text: str) -> str:
    """Best-effort redaction of common PII patterns in LLM answers.

    This keeps the demo usable while ensuring that highly sensitive fields
    (DNI, CUIT/CUIL, card numbers, emails, phones) are masked before being
    sent to clients or logs. Patterns are intentionally conservative.
    """

    if not text:
        return text

    patterns = [
        # DNI / numeric identifiers of 7-9 digits
        (re.compile(r"\b(\d{7,9})\b"), r"<dni-redacted>"),
        # CUIT/CUIL-like patterns 2-8-1 digits
        (re.compile(r"\b\d{2}-\d{7,8}-\d\b"), r"<cuit-redacted>"),
        # 16-digit card numbers or 4-4-4-4 formats
        (re.compile(r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b"), r"<card-redacted>"),
        # Email addresses
        (
            re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"),
            r"<email-redacted>",
        ),
        # Phone numbers with +country and digits
        (re.compile(r"\+?\d[\d\s\-]{6,}\d"), r"<phone-redacted>"),
    ]
    redacted = text
    for pattern, repl in patterns:
        redacted = pattern.sub(repl, redacted)
    return redacted
