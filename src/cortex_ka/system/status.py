"""System status and health verification module.

This module provides functions to check the overall health and configuration
state of the Cortex platform. It is used by:

1. The Setup Wizard to determine if first-run configuration is needed.
2. The admin dashboard to display system health.
3. Startup scripts to verify readiness before accepting requests.

Security considerations:
- Status endpoints that reveal system state should be protected or return
  minimal information to unauthenticated callers.
- Detailed diagnostics are only exposed to authenticated admins.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse

from cortex_ka.auth.db import init_login_db, login_db_session
from cortex_ka.auth.models import Subject, User
from cortex_ka.config import settings
from cortex_ka.logging import logger


@dataclass
class SystemStatus:
    """Comprehensive system status for the Cortex platform.

    This dataclass captures the state of all critical subsystems and is
    used to determine if the system is ready for operation or requires
    initial setup.
    """

    # Database status
    database_initialized: bool = False
    has_admin_user: bool = False
    admin_count: int = 0
    user_count: int = 0
    subject_count: int = 0

    # Qdrant/RAG status
    qdrant_reachable: bool = False
    qdrant_collection_exists: bool = False
    document_count: int = 0

    # LLM status
    llm_provider: str = ""
    llm_healthy: bool = False

    # Derived flags
    first_run: bool = True
    ready_for_queries: bool = False

    # Error details (for diagnostics)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "database": {
                "initialized": self.database_initialized,
                "has_admin": self.has_admin_user,
                "admin_count": self.admin_count,
                "user_count": self.user_count,
                "subject_count": self.subject_count,
            },
            "qdrant": {
                "reachable": self.qdrant_reachable,
                "collection_exists": self.qdrant_collection_exists,
                "document_count": self.document_count,
            },
            "llm": {
                "provider": self.llm_provider,
                "healthy": self.llm_healthy,
            },
            "system": {
                "first_run": self.first_run,
                "ready_for_queries": self.ready_for_queries,
            },
            "errors": self.errors if self.errors else None,
        }


def _check_database_status(status: SystemStatus) -> None:
    """Check database initialization and user counts."""
    try:
        # Ensure tables exist
        init_login_db()
        status.database_initialized = True

        with login_db_session() as db:
            # Count admins (employees with admin role)
            admin_query = db.query(User).filter(
                User.user_type == "employee",
                User.role == "admin",
                User.status == "active",
            )
            status.admin_count = admin_query.count()
            status.has_admin_user = status.admin_count > 0

            # Total user count
            status.user_count = db.query(User).filter(User.status == "active").count()

            # Subject count
            status.subject_count = db.query(Subject).count()

    except Exception as exc:
        status.errors.append(f"Database error: {str(exc)}")
        logger.warning("system_status_db_error", error=str(exc))


def _check_qdrant_status(status: SystemStatus) -> None:
    """Check Qdrant connectivity and collection state."""
    try:
        client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key or None,
            timeout=5.0,
        )

        # Test connectivity
        collections = client.get_collections()
        status.qdrant_reachable = True

        # Check if our collection exists
        collection_name = settings.qdrant_collection_docs
        collection_names = [c.name for c in collections.collections]
        status.qdrant_collection_exists = collection_name in collection_names

        # Get document count if collection exists
        if status.qdrant_collection_exists:
            try:
                info = client.get_collection(collection_name)
                status.document_count = info.points_count or 0
            except Exception:
                status.document_count = 0

    except UnexpectedResponse as exc:
        status.errors.append(f"Qdrant API error: {str(exc)}")
        logger.warning("system_status_qdrant_api_error", error=str(exc))
    except Exception as exc:
        status.errors.append(f"Qdrant connection error: {str(exc)}")
        logger.warning("system_status_qdrant_error", error=str(exc))


def _check_llm_status(status: SystemStatus) -> None:
    """Check LLM provider health."""
    import os

    provider = os.getenv("CKA_LLM_PROVIDER", settings.llm_provider).strip().lower()
    status.llm_provider = provider

    if provider == "fake":
        # Fake provider is always healthy (for testing)
        status.llm_healthy = True
        return

    if provider == "hf":
        # Check HF API key presence
        hf_key = os.getenv("HF_API_KEY") or settings.hf_api_key
        if not hf_key:
            status.errors.append("HF_API_KEY not configured")
            status.llm_healthy = False
            return

        # Try to instantiate and health check
        try:
            from cortex_ka.infrastructure.llm_hf import HFLLM

            model = os.getenv("CKA_HF_MODEL") or settings.hf_model
            llm = HFLLM(api_key=hf_key, model=model)
            status.llm_healthy = llm.healthy()
        except Exception as exc:
            status.errors.append(f"LLM health check failed: {str(exc)}")
            status.llm_healthy = False
    else:
        # Unknown provider
        status.errors.append(f"Unknown LLM provider: {provider}")
        status.llm_healthy = False


def get_system_status(
    check_llm: bool = True,
    include_errors: bool = False,
) -> SystemStatus:
    """Get comprehensive system status.

    Args:
        check_llm: Whether to perform LLM health check (can be slow).
        include_errors: Whether to include detailed error messages.

    Returns:
        SystemStatus with all checks performed.
    """
    status = SystemStatus()

    # Run all checks
    _check_database_status(status)
    _check_qdrant_status(status)

    if check_llm:
        _check_llm_status(status)
    else:
        import os

        status.llm_provider = os.getenv("CKA_LLM_PROVIDER", settings.llm_provider).strip().lower()
        status.llm_healthy = True  # Assume healthy if not checking

    # Derive first_run flag
    # System is in "first run" state if there's no admin user
    status.first_run = not status.has_admin_user

    # Derive ready_for_queries flag
    # System is ready if: has admin, qdrant reachable, collection exists with docs
    status.ready_for_queries = (
        status.has_admin_user
        and status.qdrant_reachable
        and status.qdrant_collection_exists
        and status.document_count > 0
    )

    # Clear errors if not requested
    if not include_errors:
        status.errors = []

    logger.info(
        "system_status_checked",
        first_run=status.first_run,
        ready=status.ready_for_queries,
        admin_count=status.admin_count,
        doc_count=status.document_count,
    )

    return status


def ensure_qdrant_collection() -> bool:
    """Ensure the Qdrant collection exists, creating it if necessary.

    This function is idempotent and safe to call on every startup.

    Returns:
        True if collection exists (or was created), False on error.
    """
    try:
        from cortex_ka.scripts.init_qdrant import ensure_collection

        ensure_collection()
        return True
    except Exception as exc:
        logger.error("ensure_qdrant_collection_failed", error=str(exc))
        return False
