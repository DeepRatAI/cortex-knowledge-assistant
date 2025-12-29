from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, declarative_base, mapped_column, relationship

from cortex_ka.auth.models import Subject  # reuse existing subject table

Base = declarative_base()


class ServiceInstance(Base):
    """Generic service/contract instance linked to a subject.

    This is intentionally domain-agnostic so it can model:
    - bank_account / credit_card / loan (banking)
    - mobile_line / internet_broadband (telco)
    - insurance_policy (insurance)

    Domain-specific fields live in ``extra_metadata``.
    """

    __tablename__ = "service_instances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subject_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(Subject.id, ondelete="CASCADE"),
        nullable=False,
    )

    # E.g. "bank_account", "credit_card", "loan", "mobile_line", "insurance_policy".
    service_type: Mapped[str] = mapped_column(String(64), nullable=False)

    # Business identifier (IBAN, masked PAN, MSISDN, policy number, etc.).
    service_key: Mapped[str] = mapped_column(String(128), nullable=False)

    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)

    opened_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Flexible JSON for domain-specific attributes.
    extra_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    subject: Mapped[Subject] = relationship(Subject, backref="service_instances")


class ServiceTransaction(Base):
    """Generic transactional/event record for a service instance.

    Examples:
    - Banking: account debit/credit, card purchase, loan installment.
    - Telco: invoice issued, payment registered, data usage bucket.
    - Insurance: premium charge, claim opened/paid.
    """

    __tablename__ = "service_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    service_instance_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(ServiceInstance.id, ondelete="CASCADE"),
        nullable=False,
    )

    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # E.g. "debit", "credit", "fee", "invoice", "payment", "claim_opened".
    transaction_type: Mapped[str] = mapped_column(String(64), nullable=False)

    amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="EUR")
    description: Mapped[str | None] = mapped_column(String(256), nullable=True)

    extra_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    service_instance: Mapped[ServiceInstance] = relationship(ServiceInstance, backref="transactions")
