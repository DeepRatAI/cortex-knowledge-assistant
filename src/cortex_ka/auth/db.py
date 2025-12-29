"""Database configuration for the login store.

This module owns the SQLAlchemy engine and session factory used for the login
DB (users + user_subjects). The connection string is controlled via the
DATABASE_URL environment variable and defaults to a local SQLite file for
self-contained demos.

The login DB is deliberately separate in concern from any analytical or
vector-store data; it only knows about identities and their relation to
subject identifiers.

Supported databases:
  - PostgreSQL (production): DATABASE_URL=postgresql+psycopg://user:pass@host/db
  - SQLite (development): DATABASE_URL=sqlite:///path/to/file.db
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from .models import Base

# Default location uses /app/data in Docker (volume-mounted, writable by cortex user)
# or current directory for local development
_DEFAULT_SQLITE_URL = "sqlite:////app/data/login.db"


def _get_database_url() -> str:
    """Get database URL from environment or default to SQLite.

    In production, DATABASE_URL should point to PostgreSQL:
        postgresql+psycopg://cortex:password@postgres:5432/cortex

    For local development without Docker, defaults to SQLite.
    """
    return os.getenv("DATABASE_URL", _DEFAULT_SQLITE_URL)


def _create_engine():
    """Create SQLAlchemy engine with appropriate settings for the database type."""
    url = _get_database_url()

    # SQLite requires special handling for thread safety
    if url.startswith("sqlite"):
        return create_engine(
            url,
            future=True,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

    # PostgreSQL with connection pooling
    return create_engine(
        url,
        future=True,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,  # Verify connections before use
        pool_recycle=300,  # Recycle connections after 5 minutes
    )


_engine = _create_engine()
_SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False, future=True)


def init_login_db() -> None:
    """Create tables for the login DB if they do not already exist.

    This function is idempotent and safe to call on startup. It does not touch
    any data beyond ensuring the schema exists.
    """

    Base.metadata.create_all(bind=_engine)


@contextmanager
def login_db_session() -> Iterator[Session]:
    """Provide a transactional scope around a series of operations.

    This mirrors the common SQLAlchemy pattern and is kept very small on
    purpose so that higher layers can focus on business logic and error
    handling.
    """

    session: Session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
