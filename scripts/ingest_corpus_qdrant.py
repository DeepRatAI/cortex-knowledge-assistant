"""Backward-compatible shim for corpus ingestion.

This module previously contained a custom implementation to ingest the
synthetic banking corpus directly into Qdrant. The canonical ingestion
pipeline now lives in :mod:`cortex_ka.scripts.ingest_docs` and exposes
the ``ingest_banking_corpus`` function, which is used by tests, docs,
and operational runbooks.

To avoid divergence, this shim simply delegates to that function. Any
existing references to ``python -m scripts.ingest_corpus_qdrant`` will
continue to work but will internally use the shared ingestion logic.
"""

from __future__ import annotations

from cortex_ka.scripts.ingest_docs import ingest_banking_corpus


def main() -> None:  # pragma: no cover - thin wrapper
    ingest_banking_corpus("corpus_bancario_completo.jsonl")


if __name__ == "__main__":  # pragma: no cover - utility script
    main()
