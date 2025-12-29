"""Relational models for login and subject linkage.

Initial version uses SQLite by default via DATABASE_URL, but is designed to work
with PostgreSQL/MySQL as well. This module is intentionally small and focused on
identity; domain data continues to live in the RAG/vector store.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Subject(Base):
    """Generic subject/entity observed by Cortex.

    This is a multi-domain abstraction: in banking it may represent a
    customer or account; in telco a line; in SaaS an organization, etc.

    The ``subject_key`` field is the external identifier that flows through
    JWT claims and API payloads (what we historically called ``subject_id``),
    while the integer primary key is used purely for relational integrity.
    """

    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # Stable external identifier, e.g. "CLI-81093" in the banking demo.
    subject_key = Column(String(255), unique=True, nullable=False, index=True)
    # High-level type, e.g. "person", "account", "organization", "line".
    subject_type = Column(String(64), nullable=False, default="entity")
    # Human-readable display name for UI and logs.
    display_name = Column(String(255), nullable=False)
    # Lifecycle status such as "active", "closed", "suspended".
    status = Column(String(32), nullable=False, default="active")

    # ==========================================================================
    # PERSONAL/ENTITY IDENTIFICATION DATA (PII - Protected)
    # ==========================================================================
    # Full legal name (person) or business name (organization).
    full_name = Column(String(255), nullable=True)
    # National ID number (DNI, SSN, NIF, etc.) - ENCRYPTED AT REST recommended.
    document_id = Column(String(64), nullable=True, index=True)
    # Tax ID (CUIL/CUIT in Argentina, NIF in Spain, EIN in US, etc.).
    tax_id = Column(String(64), nullable=True, index=True)
    # Primary contact email address.
    email = Column(String(255), nullable=True, index=True)
    # Phone number (E.164 format recommended: +54911XXXXXXXX).
    phone = Column(String(32), nullable=True)

    # Flexible attributes for domain-specific metadata (additional fields).
    attributes = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Associated products/services for this subject (accounts, cards, etc.).
    services = relationship("SubjectService", back_populates="subject", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    user_type = Column(String(32), nullable=False)  # e.g. "customer" or "employee"
    role = Column(String(64), nullable=False, default="user")
    dlp_level = Column(String(32), nullable=False, default="standard")
    status = Column(String(32), nullable=False, default="active")
    can_access_all_subjects = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    subjects = relationship("UserSubject", back_populates="user", cascade="all, delete-orphan")


class UserSubject(Base):
    __tablename__ = "user_subjects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    # Foreign key to the subjects table; this is the internal relational id.
    subject_pk = Column(
        Integer,
        ForeignKey("subjects.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    # Backwards-compatible logical subject identifier (external key) used by
    # JWT claims and RAG scoping. In new installations this should mirror
    # Subject.subject_key; in legacy rows without a Subject it continues to
    # carry the stable id such as "CLI-81093".
    subject_id = Column(String(255), nullable=False, index=True)

    user = relationship("User", back_populates="subjects")
    subject = relationship("Subject")


class SubjectService(Base):
    """Generic service/product attached to a Subject.

    This provides a minimal transactional view of what the subject "has"
    (accounts, cards, loans, subscriptions, etc.) while keeping the rich
    domain knowledge in the RAG corpus.
    """

    __tablename__ = "subject_services"

    id = Column(Integer, primary_key=True, autoincrement=True)
    subject_id = Column(
        Integer,
        ForeignKey("subjects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # High-level type such as "account", "card", "loan", "product".
    service_type = Column(String(64), nullable=False, default="service")
    # External identifier for the service (masked account number, card PAN, etc.).
    service_key = Column(String(255), nullable=False, index=True)
    # Human-readable label for UI and logs.
    display_name = Column(String(255), nullable=False)
    # Lifecycle status: "active", "closed", "suspended", etc.
    status = Column(String(32), nullable=False, default="active")
    # Flexible metadata for domain-specific attributes (currency, limits, dates).
    extra_metadata = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    subject = relationship("Subject", back_populates="services")


class AuditLog(Base):
    """Security/audit trail for sensitive operations.

    This table is intentionally small and denormalised; it is not meant for
    complex analytics, but for answering concrete questions such as:

    - "Who queried subject X yesterday?"
    - "Which subjects did user Y access in the last N hours?"
    - "How many login failures did we see for username Z?"
    """

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # The authenticated principal performing the action, if known.
    user_id = Column(String(64), nullable=True, index=True)
    username = Column(String(255), nullable=True, index=True)
    # Optional business subject key (e.g. CLI-xxxx) targeted by the action.
    subject_key = Column(String(255), nullable=True, index=True)

    # High-level verb describing the operation, e.g. "login_success",
    # "login_failure", "query", "view_subject", "view_services".
    operation = Column(String(64), nullable=False, index=True)

    # Coarse-grained outcome: "success", "failure", "denied", etc.
    outcome = Column(String(32), nullable=False, default="success")

    # Arbitrary structured metadata (reason codes, remote_ip, hashes, etc.).
    details = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)


@dataclass
class CurrentUserContext:
    """Lightweight representation used by auth layer to build API-level CurrentUser.

    This mirrors the shape that will be embedded in JWT claims and passed
    around inside the application. It is intentionally separate from the
    FastAPI-facing CurrentUser model to avoid import cycles.
    """

    user_id: str
    username: str
    user_type: str
    role: str
    dlp_level: str
    subject_ids: list[str]
    can_access_all_subjects: bool = False

    @classmethod
    def from_orm(cls, user: User, subject_ids: Iterable[str]) -> "CurrentUserContext":
        return cls(
            user_id=str(user.id),
            username=user.username,
            user_type=user.user_type,
            role=user.role,
            dlp_level=user.dlp_level,
            subject_ids=list(subject_ids),
            can_access_all_subjects=bool(user.can_access_all_subjects),
        )
