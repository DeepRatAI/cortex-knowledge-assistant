"""System management module for Cortex.

This package contains modules for system-level operations:
- status: System health and configuration verification
- setup: First-run setup and admin creation
"""

from cortex_ka.system.status import (
    SystemStatus,
    ensure_qdrant_collection,
    get_system_status,
)

__all__ = [
    "SystemStatus",
    "get_system_status",
    "ensure_qdrant_collection",
]
