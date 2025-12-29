"""Demo environment auto-reset scheduler.

This module provides a background scheduler that automatically resets the demo
environment at configurable intervals. It is designed for public "first-run"
demos where users can explore Cortex with clean data.

Security:
* Reset is triggered ONLY by the internal scheduler, never via HTTP endpoints.
* The /api/demo/status endpoint only returns timer information (read-only).
* All reset operations are logged for audit purposes.

Configuration (via environment variables):
* CKA_DEMO_RESET_ENABLED: Set to "true" to enable auto-reset (default: false)
* CKA_DEMO_RESET_INTERVAL_HOURS: Hours between resets (default: 4)
* CKA_DEMO_SEED_AFTER_RESET: Set to "true" to re-seed demo data (default: true)

Usage:
    The scheduler is started automatically when the API boots if enabled.

    from cortex_ka.demos.scheduler import demo_scheduler
    demo_scheduler.start()  # Called in main.py startup
"""

from __future__ import annotations

import os
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from cortex_ka.logging import logger


class DemoResetScheduler:
    """Background scheduler for periodic demo environment resets."""

    def __init__(self) -> None:
        self._scheduler: Optional[BackgroundScheduler] = None
        self._next_reset: Optional[datetime] = None
        self._last_reset: Optional[datetime] = None
        self._interval_hours: int = 4
        self._enabled: bool = False
        self._seed_after_reset: bool = True
        self._lock = threading.Lock()
        self._reset_count: int = 0

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def interval_hours(self) -> int:
        return self._interval_hours

    @property
    def next_reset(self) -> Optional[datetime]:
        return self._next_reset

    @property
    def last_reset(self) -> Optional[datetime]:
        return self._last_reset

    @property
    def reset_count(self) -> int:
        return self._reset_count

    def _load_config(self) -> None:
        """Load configuration from environment variables."""
        self._enabled = os.getenv("CKA_DEMO_RESET_ENABLED", "").lower() == "true"

        try:
            self._interval_hours = int(os.getenv("CKA_DEMO_RESET_INTERVAL_HOURS", "4"))
        except ValueError:
            self._interval_hours = 4
            logger.warning(
                "demo_scheduler_invalid_interval",
                message="Invalid interval, using default 4 hours",
            )

        self._seed_after_reset = os.getenv("CKA_DEMO_SEED_AFTER_RESET", "true").lower() == "true"

    def _calculate_next_reset(self) -> datetime:
        """Calculate the next reset time based on interval."""
        return datetime.now(timezone.utc) + timedelta(hours=self._interval_hours)

    def _perform_reset(self) -> None:
        """Execute the demo environment reset.

        This method is called by the scheduler and should NEVER be exposed
        via HTTP endpoints.
        """
        with self._lock:
            logger.warning(
                "demo_auto_reset_starting",
                reset_number=self._reset_count + 1,
                interval_hours=self._interval_hours,
            )

            try:
                # Import here to avoid circular imports
                from cortex_ka.maintenance.reset_environment import (
                    reset_login_and_transactions,
                    reset_qdrant_documents,
                )

                # Reset Qdrant documents
                qdrant_ops = reset_qdrant_documents()

                # Reset database tables
                reset_login_and_transactions()

                self._last_reset = datetime.now(timezone.utc)
                self._reset_count += 1

                logger.warning(
                    "demo_auto_reset_completed",
                    reset_number=self._reset_count,
                    qdrant_delete_ops=qdrant_ops,
                )

                # Optionally re-seed demo data
                if self._seed_after_reset:
                    self._seed_demo_data()

                # Calculate next reset time
                self._next_reset = self._calculate_next_reset()
                logger.info(
                    "demo_next_reset_scheduled",
                    next_reset_utc=self._next_reset.isoformat(),
                )

            except Exception:
                logger.exception("demo_auto_reset_failed")

    def _seed_demo_data(self) -> None:
        """Re-seed demo data after reset."""
        try:
            # Import here to avoid circular imports
            from cortex_ka.system.setup import create_initial_admin
            from cortex_ka.transactions.seed_demo import (
                seed_demo_transactions_with_metrics,
            )

            logger.info("demo_reseed_starting")

            # Create initial admin user
            try:
                create_initial_admin()
                logger.info("demo_reseed_admin_created")
            except Exception as e:
                # Admin might already exist if reset was partial
                logger.info("demo_reseed_admin_skipped", reason=str(e))

            # Seed demo transactions (optional, based on domain)
            try:
                seed_demo_transactions_with_metrics()
                logger.info("demo_reseed_transactions_completed")
            except Exception:
                logger.warning("demo_reseed_transactions_skipped")

            logger.info("demo_reseed_completed")

        except Exception:
            logger.exception("demo_reseed_failed")

    def start(self) -> None:
        """Start the demo reset scheduler if enabled."""
        self._load_config()

        if not self._enabled:
            logger.info(
                "demo_scheduler_disabled",
                message="Set CKA_DEMO_RESET_ENABLED=true to enable auto-reset",
            )
            return

        if self._scheduler is not None:
            logger.warning("demo_scheduler_already_running")
            return

        logger.info(
            "demo_scheduler_starting",
            interval_hours=self._interval_hours,
            seed_after_reset=self._seed_after_reset,
        )

        self._scheduler = BackgroundScheduler(timezone="UTC")

        # Schedule periodic reset
        self._scheduler.add_job(
            self._perform_reset,
            trigger=IntervalTrigger(hours=self._interval_hours),
            id="demo_reset_job",
            name="Demo Environment Auto-Reset",
            replace_existing=True,
            max_instances=1,  # Prevent overlapping resets
        )

        self._scheduler.start()
        self._next_reset = self._calculate_next_reset()

        logger.info("demo_scheduler_started", next_reset_utc=self._next_reset.isoformat())

    def stop(self) -> None:
        """Stop the demo reset scheduler."""
        if self._scheduler is not None:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
            self._next_reset = None
            logger.info("demo_scheduler_stopped")

    def get_status(self) -> dict:
        """Get current scheduler status for the /api/demo/status endpoint.

        This is the ONLY information exposed externally. No trigger mechanism.
        """
        now = datetime.now(timezone.utc)

        time_until_reset = None
        if self._next_reset is not None:
            delta = self._next_reset - now
            time_until_reset = max(0, int(delta.total_seconds()))

        return {
            "enabled": self._enabled,
            "interval_hours": self._interval_hours if self._enabled else None,
            "next_reset_utc": (self._next_reset.isoformat() if self._next_reset else None),
            "seconds_until_reset": time_until_reset,
            "last_reset_utc": (self._last_reset.isoformat() if self._last_reset else None),
            "reset_count": self._reset_count,
            "server_time_utc": now.isoformat(),
        }


# Singleton instance
demo_scheduler = DemoResetScheduler()
