from __future__ import annotations

"""Domain service for reading synthetic banking transactional data.

At this stage the service is intentionally read-only and focused on the
demo banking scenario. It exposes a small, stable contract that higher
layers (API, LLM prompt builder, UI) can consume without depending on
SQLAlchemy models or session details.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, List, Optional

from cortex_ka.application.pii_masking import ViewerRole, build_subject_pii
from cortex_ka.auth.db import login_db_session
from cortex_ka.auth.models import Subject

from .models import ServiceInstance, ServiceTransaction


@dataclass(frozen=True)
class ProductSummary:
    service_type: str
    service_key: str
    status: str
    extra: dict[str, Any]


@dataclass(frozen=True)
class TransactionSummary:
    timestamp: datetime
    transaction_type: str
    amount: float
    currency: str
    description: str | None
    extra: dict[str, Any]


@dataclass(frozen=True)
class CustomerSnapshot:
    """Complete snapshot of a customer/subject for LLM context.

    This includes:
    - Identity: subject_key + optional personal data (masked by role)
    - Products: Active services/accounts
    - Transactions: Recent movements/grades

    Personal data fields (display_name, document_id, tax_id, email, phone)
    are PRE-MASKED according to the viewer's role before being set here.
    See pii_masking.py for the masking logic.

    Attributes:
        subject_key: External identifier (e.g., "CLI-81093", "STU-2024-001")
        products: List of active products/services
        recent_transactions: Recent transactions/movements
        display_name: Human-readable name (never masked)
        document_id: DNI/SSN (may be masked like "XX.XXX.789")
        tax_id: CUIL/CUIT (may be masked like "20-XXXXXXXX-3")
        email: Email address (may be masked like "m***@domain.com")
        phone: Phone number (may be masked like "+54 ****-5678")
    """

    subject_key: str
    products: List[ProductSummary]
    recent_transactions: List[TransactionSummary]
    # Personal data fields - PRE-MASKED by pii_masking before assignment
    display_name: str | None = None
    document_id: str | None = None
    tax_id: str | None = None
    email: str | None = None
    phone: str | None = None


class BankingDomainService:
    """Read-only view of transactional data for the banking demo.

    The methods here deliberately:

    * Accept logical identifiers (subject_key) instead of primary keys.
    * Return dataclasses instead of ORM entities.
    * Use the same login DB session factory for now (SQLite) to avoid
      extra infra in the demo. In a real deployment this service would
      point to a dedicated transactional database.
    """

    def __init__(self) -> None:
        # No stateful dependencies; we always acquire sessions on demand.
        pass

    def get_customer_snapshot(
        self,
        *,
        subject_key: str,
        max_transactions: int = 20,
        viewer_role: Optional[str] = None,
        is_own_data: bool = False,
    ) -> CustomerSnapshot | None:
        """Return a snapshot of products and recent movements for a subject.

        If the subject does not exist or has no products, returns None.

        Args:
            subject_key: External identifier of the subject
            max_transactions: Maximum number of transactions to include
            viewer_role: Role of user viewing data ("customer", "employee", "admin")
                         Determines PII masking level. Default: "employee" (masked)
            is_own_data: True if viewer is looking at their own data
                        (overrides role-based masking to show full data)

        Returns:
            CustomerSnapshot with appropriately masked PII fields,
            or None if subject not found.
        """
        # Map string role to enum, default to employee (most restrictive common role)
        role_map = {
            "customer": ViewerRole.CUSTOMER,
            "employee": ViewerRole.EMPLOYEE,
            "admin": ViewerRole.ADMIN,
            "system": ViewerRole.SYSTEM,
        }
        role_enum = role_map.get(viewer_role or "employee", ViewerRole.EMPLOYEE)

        with login_db_session() as db:
            subject = (
                db.query(Subject).filter(Subject.subject_key == subject_key, Subject.status == "active").one_or_none()
            )
            if not subject:
                return None

            instances: Iterable[ServiceInstance] = (
                db.query(ServiceInstance).filter(ServiceInstance.subject_id == subject.id).all()
            )
            if not instances:
                return None

            products: list[ProductSummary] = []
            tx_summaries: list[TransactionSummary] = []

            for inst in instances:
                products.append(
                    ProductSummary(
                        service_type=inst.service_type,
                        service_key=inst.service_key,
                        status=inst.status,
                        extra=dict(inst.extra_metadata or {}),
                    )
                )

                txs: Iterable[ServiceTransaction] = (
                    db.query(ServiceTransaction)
                    .filter(ServiceTransaction.service_instance_id == inst.id)
                    .order_by(ServiceTransaction.timestamp.desc())
                    .limit(max_transactions)
                    .all()
                )
                for tx in txs:
                    tx_summaries.append(
                        TransactionSummary(
                            timestamp=tx.timestamp,
                            transaction_type=tx.transaction_type,
                            amount=tx.amount,
                            currency=tx.currency,
                            description=tx.description,
                            extra=dict(tx.extra_metadata or {}),
                        )
                    )

            # Order transactions globally by timestamp desc and clip
            tx_summaries.sort(key=lambda t: t.timestamp, reverse=True)
            if len(tx_summaries) > max_transactions:
                tx_summaries = tx_summaries[:max_transactions]

            # Build masked PII based on viewer role
            pii = build_subject_pii(
                display_name=subject.display_name,
                full_name=subject.full_name,
                document_id=subject.document_id,
                tax_id=subject.tax_id,
                email=subject.email,
                phone=subject.phone,
                viewer_role=role_enum,
                is_own_data=is_own_data,
            )

            return CustomerSnapshot(
                subject_key=subject.subject_key,
                products=products,
                recent_transactions=tx_summaries,
                display_name=pii.display_name,
                document_id=pii.document_id,
                tax_id=pii.tax_id,
                email=pii.email,
                phone=pii.phone,
            )


__all__ = [
    "ProductSummary",
    "TransactionSummary",
    "CustomerSnapshot",
    "BankingDomainService",
]
