"""Offline evaluation utilities for PII redaction.

This module loads the synthetic PII corpus (JSONL) used in tests and CI, runs
our redaction engine over each sample, and computes simple leakage metrics.

It is intentionally decoupled from the FastAPI layer so that it can be used
from unit tests, CLI tools or notebooks without importing the API app.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, MutableMapping, Sequence

from cortex_ka.application.pii import redact_pii


def _get_repo_root() -> Path:
    """Return the repository root directory.

    We assume this file lives under:
        <repo_root>/src/cortex_ka/eval/pii_evaluator.py

    So the repo root is three levels above src/cortex_ka/eval:
        eval -> cortex_ka -> src -> <repo_root>
    """
    return Path(__file__).resolve().parents[3]


@dataclass
class PiiSample:
    """Single entry from the synthetic PII test corpus.

    Attributes
    ----------
    doc_id: Unique identifier of the sample in the corpus.
    text: Original text that may contain PII.
    pii_ground_truth: Mapping from PII type (e.g. "dni", "cuit", "card",
        "phone", "email") to a list of literal strings that *must* disappear
        after redaction.
    """

    doc_id: str
    text: str
    pii_ground_truth: Mapping[str, Sequence[str]]


@dataclass
class PiiEvaluationResult:
    """Aggregated metrics for a run over the PII corpus."""

    total_samples: int
    total_pii_items: int
    leaked_items: int
    # Per-type breakdown: {"dni": {"total": int, "leaked": int}, ...}
    by_type: Dict[str, Dict[str, int]]

    @property
    def leakage_rate(self) -> float:
        """Fraction of PII items that were not removed by redaction.

        Returns 0.0 when there are no PII items to avoid division by zero.
        """

        if self.total_pii_items == 0:
            return 0.0
        return self.leaked_items / float(self.total_pii_items)


def load_pii_corpus(path: Path | str) -> List[PiiSample]:
    """Load synthetic PII corpus from a JSONL file.

    The expected schema for each line is::

        {"doc_id": str, "text": str, "pii_ground_truth": {<pii_type>: [str, ...]}}

    Any extra fields are ignored.
    """

    p = Path(path)
    # Permite pasar una ruta relativa al repo root, como "pii_test_corpus.jsonl"
    if not p.is_absolute():
        p = _get_repo_root() / p

    samples: List[PiiSample] = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            samples.append(
                PiiSample(
                    doc_id=data["doc_id"],
                    text=data["text"],
                    pii_ground_truth=data.get("pii_ground_truth", {}),
                )
            )
    return samples


def evaluate_redaction(samples: Iterable[PiiSample]) -> PiiEvaluationResult:
    """Run `redact_pii` on samples and compute leakage metrics.

    A PII item is considered leaked if the literal ground-truth string is still
    present in the redacted text. This is intentionally strict: masking that
    only partially modifies the string (e.g. keeping last 4 digits) would count
    as leakage for this metric, which matches a conservative banking posture.
    """

    total_samples = 0
    total_pii_items = 0
    leaked_items = 0
    by_type: MutableMapping[str, Dict[str, int]] = {}

    for sample in samples:
        total_samples += 1
        redacted = redact_pii(sample.text)

        for pii_type, values in sample.pii_ground_truth.items():
            type_stats = by_type.setdefault(pii_type, {"total": 0, "leaked": 0})
            for value in values:
                type_stats["total"] += 1
                total_pii_items += 1
                if value in redacted:
                    type_stats["leaked"] += 1
                    leaked_items += 1

    return PiiEvaluationResult(
        total_samples=total_samples,
        total_pii_items=total_pii_items,
        leaked_items=leaked_items,
        by_type=dict(by_type),
    )


__all__ = [
    "PiiSample",
    "PiiEvaluationResult",
    "load_pii_corpus",
    "evaluate_redaction",
]
