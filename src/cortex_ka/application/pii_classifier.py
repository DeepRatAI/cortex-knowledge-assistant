"""PII classification contract used during document ingest.

This module intentionally provides a very small, stable interface that can be
plugged into the ingestion pipeline. For now it returns neutral values, but the
shape of the response is designed for future expansion:

- per-type flags (dni, cuit, card, phone, email, other),
- sensitivity level (e.g. low/medium/high),
- and a generic metadata field for auditors.

Having this contract in place allows us to wire the classifier in tests and
pipelines without committing to a specific model implementation yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Literal

from .pii import redact_pii

SensitivityLevel = Literal["none", "low", "medium", "high"]


@dataclass
class PiiClassification:
    """Aggregate PII classification result for a text fragment.

    Attributes:
        has_pii: Quick boolean indicating whether any PII was detected.
        by_type: Mapping from PII type (dni, cuit, card, phone, email, other)
            to a boolean flag.
        sensitivity: Coarse-grained sensitivity label for this fragment.
        meta: Optional metadata dictionary for future auditors/tools.
    """

    has_pii: bool
    by_type: Dict[str, bool]
    sensitivity: SensitivityLevel
    meta: Dict[str, str]


def classify_pii(text: str) -> PiiClassification:
    """Classify PII for a given text fragment.

    Current implementation is heuristic-only and aligned with `redact_pii`.

    Strategy (fast, deterministic, no external model):

    - run `redact_pii` on the fragment,
    - compare redacted vs original to detect if any of our PII patterns fired,
    - infer per-type flags from replacement tokens,
    - compute an overall sensitivity level.

    This keeps the classifier cheap enough to run on every chunk during ingest
    while still giving us a meaningful signal for downstream policies.
    """
    if not text:
        return PiiClassification(
            has_pii=False,
            by_type={
                "dni": False,
                "cuit": False,
                "card": False,
                "phone": False,
                "email": False,
                "other": False,
            },
            sensitivity="none",
            meta={},
        )

    redacted = redact_pii(text)

    # By design, `redact_pii` replaces detected literals with fixed tokens.
    # We use those tokens to infer which PII types were present without
    # re-implementing the regex logic here.
    by_type: Dict[str, bool] = {
        "dni": "<dni-redacted>" in redacted,
        "cuit": "<cuit-redacted>" in redacted,
        "card": "<card-redacted>" in redacted,
        "phone": "<phone-redacted>" in redacted,
        "email": "<email-redacted>" in redacted,
        # `other` is reserved for future detectors; keep it explicit so
        # downstream code can rely on the key being present.
        "other": False,
    }

    has_pii = any(by_type.values())

    # Sensitivity policy (coarse but auditable):
    # - high: card numbers or multiple PII types in the same chunk
    # - medium: single strong identifier (dni/cuit/email/phone)
    # - low: reserved for future, for now we map to medium/none
    if by_type["card"] or sum(v for v in by_type.values()) > 1:
        sensitivity: SensitivityLevel = "high"
    elif by_type["dni"] or by_type["cuit"] or by_type["email"] or by_type["phone"]:
        sensitivity = "medium"
    else:
        sensitivity = "none"

    return PiiClassification(
        has_pii=has_pii,
        by_type=by_type,
        sensitivity=sensitivity,
        meta={},
    )


__all__ = ["SensitivityLevel", "PiiClassification", "classify_pii"]
