"""DLP (Data Loss Prevention) facade for Cortex KA.

This module provides a generic interface for DLP policies while currently
delegating to the existing `redact_pii` function. It is intentionally kept
simple and optional:

- When CKA_DLP_ENABLED is false/missing, the DLP layer is a no-op and
  callers can behave as before.
- When enabled, `enforce_dlp` runs the active policies (today: redact_pii).

The goal is to have a single place to plug stricter controls in the future
without changing the API surface or the RAG pipeline contracts.
"""

from __future__ import annotations

import os
from typing import Any, Optional, Protocol

from .pii import redact_pii


class DlpEngine(Protocol):  # pragma: no cover - interface only
    def enforce(self, text: str) -> str: ...


class PiiRedactionEngine:
    """Simple DLP engine that delegates to redact_pii.

    This mirrors the current behaviour but goes through a dedicated interface
    so that we can evolve policies independently.
    """

    def enforce(self, text: str) -> str:
        return redact_pii(text)


def dlp_enabled() -> bool:
    """Return whether DLP is enabled via configuration.

    Controlled by CKA_DLP_ENABLED env var (1/true/yes). Default: enabled,
    because redact_pii is already part of the current behaviour. This
    function exists mainly to make future, stricter modes configurable.
    """

    flag = os.getenv("CKA_DLP_ENABLED", "true").lower()
    return flag in {"1", "true", "yes"}


def enforce_dlp(text: str, user: Optional[Any] = None) -> str:
    """Apply DLP policies to the provided text.

    Currently this just runs `redact_pii` when DLP is enabled; callers can
    continue to call `redact_pii` directly if they need the legacy behaviour.
    Over time, /query and /chat/stream can move to `enforce_dlp` to centralise
    governance without breaking compatibility.
    """

    # If DLP is globally disabled, behave as a no-op regardless of user.
    if not dlp_enabled():
        return text
    # "Privileged" DLP level is allowed to bypass redaction, modelling
    # tightly controlled backoffice tools. All other levels (or missing
    # user) go through the normal redaction engine. We avoid importing the
    # API layer here to keep boundaries clean, so ``user`` is treated as a
    # generic object with an optional ``dlp_level`` attribute.
    if user is not None and getattr(user, "dlp_level", "standard") == "privileged":
        return text
    engine: DlpEngine = PiiRedactionEngine()
    return engine.enforce(text)
