"""Maintenance tools for resetting Cortex data environment.

This module provides **operator-only** utilities to wipe runtime data for a
Cortex deployment while keeping the codebase and schema intact. It is intended
for controlled scenarios such as:

* Cleaning synthetic demo data (e.g. banking scenario) before onboarding a
  real customer.
* Resetting a shared dev environment between test runs.

Security & safety guarantees:

* No network calls or destructive actions are executed unless the caller
  explicitly opts in via environment variables or function parameters.
* The functions here are **not** exposed via public HTTP endpoints; they are
  meant to be invoked from the CLI or internal tooling only.

Usage (example):

    CKA_RESET_CONFIRM=YES python -m cortex_ka.maintenance.reset_environment

This will:

* Delete document chunks from the primary Qdrant collection used by the RAG
  service.
* Truncate authentication and transactional tables in the login database.

The exact set of tables/collections is kept intentionally narrow and focused on
runtime data, not on migrations or schema metadata.
"""

from __future__ import annotations

import os
from typing import Iterable

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from cortex_ka.auth.db import login_db_session
from cortex_ka.auth.models import AuditLog, Subject, SubjectService, User, UserSubject
from cortex_ka.config import settings
from cortex_ka.logging import logger
from cortex_ka.transactions.models import ServiceInstance, ServiceTransaction


def _require_confirmation(env_var: str = "CKA_RESET_CONFIRM") -> None:
    """Abort unless the operator has explicitly opted in via env var.

    To reduce the risk of accidental environment wipes, callers must set
    ``CKA_RESET_CONFIRM=YES`` (or a custom name via ``env_var``) before
    invoking the main reset routine.
    """

    value = os.getenv(env_var, "").strip().upper()
    if value not in {"YES", "I_UNDERSTAND"}:
        raise RuntimeError(f"Refusing to reset environment: set {env_var}=YES explicitly to proceed")


def reset_qdrant_documents(sources: Iterable[str] | None = None) -> int:
    """Delete document chunks from the primary Qdrant collection.

    By default, deletes all points whose ``source`` payload field matches any
    of the known demo sources (e.g. ``corpus_bancario``,
    ``documentacion_publica_pdf``). If ``sources`` is None, uses a safe
    built-in list.

    Returns the number of delete operations issued (not individual points).
    """

    if not settings.qdrant_url:
        logger.warning("reset_qdrant_skipped", reason="qdrant_url_not_configured")
        return 0

    client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    collection = settings.qdrant_collection_docs

    if sources is None:
        sources = ["corpus_bancario", "documentacion_publica_pdf"]

    ops = 0
    for src in sources:
        flt = qmodels.Filter(must=[qmodels.FieldCondition(key="source", match=qmodels.MatchValue(value=src))])
        try:
            client.delete(  # type: ignore[attr-defined]
                collection_name=collection,
                points_selector=qmodels.FilterSelector(filter=flt),
            )
            ops += 1
            logger.info("qdrant_reset_source", collection=collection, source=src)
        except Exception:
            logger.exception("qdrant_reset_source_failed", collection=collection, source=src)

    return ops


def reset_login_and_transactions() -> None:
    """Truncate authentication and transactional tables in the login DB.

    This removes demo users, subjects and transactional data while keeping the
    underlying database schema and migrations intact.
    """

    with login_db_session() as db:
        # Order matters because of foreign keys.
        db.query(AuditLog).delete()
        db.query(ServiceTransaction).delete()
        db.query(ServiceInstance).delete()
        db.query(UserSubject).delete()
        db.query(SubjectService).delete()
        db.query(Subject).delete()
        db.query(User).delete()
        db.commit()

    logger.info("login_and_transactions_reset_completed")


def reset_all() -> None:
    """High-level reset: Qdrant documents + login/transactional DB.

    This is the preferred entry point for operators.
    """

    _require_confirmation()

    logger.warning("environment_reset_start")
    qdrant_ops = reset_qdrant_documents()
    reset_login_and_transactions()
    logger.warning("environment_reset_completed", qdrant_delete_ops=qdrant_ops)


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    reset_all()
