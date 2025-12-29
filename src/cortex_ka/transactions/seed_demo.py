from __future__ import annotations

"""Seed synthetic transactional data for the demo banking scenario.

This module is intentionally **separate** from ``auth.seed_demo`` which only
handles login identities and subject links. Here we populate the generic
transactional tables (:class:`ServiceInstance`, :class:`ServiceTransaction`)
with demo-friendly data for existing subjects.

The goal is to provide a realistic-looking but fully synthetic snapshot of
customer products and movements without introducing any additional PII
beyond the subject identifiers that already exist in the login DB.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from random import Random
from typing import Iterable

from cortex_ka.auth.db import login_db_session
from cortex_ka.auth.models import Subject
from cortex_ka.logging import logger

from .models import Base, ServiceInstance, ServiceTransaction

_RNG = Random(42)  # deterministic for reproducible demos


@dataclass(frozen=True)
class DemoSeedResult:
    """Result metrics for the transactional demo seed operation.

    This is used both for structured logging and for admin endpoints that
    expose a summary of how many records were created or skipped.
    """

    service_instances_created: int
    transactions_created: int
    subjects_skipped: int


def _iter_subjects() -> Iterable[Subject]:
    """Yield all active subjects from the login DB.

    We deliberately avoid joining any PII fields here; we only rely on the
    synthetic ``subject_key`` (e.g. CLI-xxxxx) that is already used as the
    logical tenant identifier across the system.
    """

    with login_db_session() as db:
        for subj in db.query(Subject).filter(Subject.status == "active"):
            yield subj


def _ensure_schema() -> None:
    """Create transactional tables if they do not exist yet.

    Uses the same engine as the login DB for the demo scenario. In a more
    advanced deployment these tables could live in a dedicated database, but
    sharing SQLite keeps the demo footprint minimal.
    """

    with login_db_session() as db:
        engine = db.get_bind()
        Base.metadata.create_all(bind=engine)  # type: ignore[arg-type]


def _create_bank_products_for_subject(subject: Subject) -> list[ServiceInstance]:
    """Create 1-2 synthetic banking products for a subject.

    - One current account (mandatory)
    - Optionally one personal loan (about 50% of subjects)
    """

    instances: list[ServiceInstance] = []
    key_fragment = subject.subject_key.replace("CLI-", "")[-4:]

    account = ServiceInstance(
        subject_id=subject.id,
        service_type="bank_account",
        service_key=f"ES76-0000-0000-{key_fragment}",
        status="active",
        extra_metadata={
            "currency": "EUR",
            "segment": "retail",
            "product_name": "Cuenta corriente nómina",
        },
    )
    instances.append(account)

    # Roughly half of the subjects get a personal loan
    if _RNG.random() < 0.5:
        principal = _RNG.choice([5000, 10000, 20000])
        rate = _RNG.choice([0.049, 0.059, 0.069])
        term_months = _RNG.choice([24, 36, 48])
        loan = ServiceInstance(
            subject_id=subject.id,
            service_type="loan",
            service_key=f"LOAN-{key_fragment}",
            status="active",
            extra_metadata={
                "currency": "EUR",
                "principal": principal,
                "interest_rate": rate,
                "term_months": term_months,
                "product_name": "Préstamo personal",
            },
        )
        instances.append(loan)

    return instances


def _create_synthetic_movements(instance: ServiceInstance) -> list[ServiceTransaction]:
    """Generate a small ledger of synthetic movements for one service instance."""

    now = datetime.now(timezone.utc)
    txs: list[ServiceTransaction] = []

    if instance.service_type == "bank_account":
        # 6 months of sparse movements
        for months_back in range(5, -1, -1):
            base_date = now - timedelta(days=30 * months_back)

            # Salary credit
            amount_salary = _RNG.choice([1200, 1500, 2000])
            txs.append(
                ServiceTransaction(
                    service_instance=instance,
                    timestamp=base_date.replace(day=1, hour=10, minute=0, second=0, microsecond=0),
                    transaction_type="credit",
                    amount=float(amount_salary),
                    currency="EUR",
                    description="Ingreso nómina",
                    extra_metadata={"category": "salary"},
                )
            )

            # 2-3 debit transactions (bills, card payments)
            for _ in range(_RNG.randint(2, 3)):
                day = _RNG.randint(5, 27)
                amount = float(_RNG.choice([25, 40, 60, 80, 100]))
                txs.append(
                    ServiceTransaction(
                        service_instance=instance,
                        timestamp=base_date.replace(day=day, hour=12, minute=0, second=0, microsecond=0),
                        transaction_type="debit",
                        amount=-amount,
                        currency="EUR",
                        description="Pago comercio / recibo",
                        extra_metadata={"category": "spending"},
                    )
                )

    elif instance.service_type == "loan":
        # A few monthly installments
        principal = float((instance.extra_metadata or {}).get("principal", 10000))
        term_months = int((instance.extra_metadata or {}).get("term_months", 36))
        installment = round(principal / term_months * 1.02, 2)  # simple uplift for interest

        for n in range(1, min(term_months, 6) + 1):
            pay_date = now - timedelta(days=30 * (6 - n))
            txs.append(
                ServiceTransaction(
                    service_instance=instance,
                    timestamp=pay_date.replace(day=3, hour=9, minute=0, second=0, microsecond=0),
                    transaction_type="debit",
                    amount=-float(installment),
                    currency="EUR",
                    description=f"Cuota préstamo {n}/{term_months}",
                    extra_metadata={"category": "loan_installment"},
                )
            )

    return txs


def _seed_demo_transactions_inner() -> DemoSeedResult:
    """Inner implementation that performs the demo seed and returns metrics.

    Idempotent at the level of "subject has data": if a subject already has
    at least one ServiceInstance, it is skipped. This avoids duplicating
    products on repeated runs.
    """

    _ensure_schema()
    created_instances = 0
    created_txs = 0
    subjects_skipped = 0

    with login_db_session() as db:
        for subject in db.query(Subject).filter(Subject.status == "active"):
            # Skip subjects that already have transactional products
            existing = db.query(ServiceInstance).filter(ServiceInstance.subject_id == subject.id).first()
            if existing:
                subjects_skipped += 1
                continue

            instances = _create_bank_products_for_subject(subject)
            for inst in instances:
                db.add(inst)
            db.flush()
            created_instances += len(instances)

            for inst in instances:
                txs = _create_synthetic_movements(inst)
                for tx in txs:
                    db.add(tx)
                created_txs += len(txs)

    return DemoSeedResult(
        service_instances_created=created_instances,
        transactions_created=created_txs,
        subjects_skipped=subjects_skipped,
    )


def seed_demo_transactions_with_metrics() -> DemoSeedResult:
    """Seed demo data and return structured metrics for admin consumption."""

    result = _seed_demo_transactions_inner()
    logger.info(
        "transactions_demo_seed_completed",
        service_instances=result.service_instances_created,
        transactions=result.transactions_created,
        subjects_skipped=result.subjects_skipped,
    )
    return result


def seed_demo_transactions() -> None:
    """CLI-friendly wrapper that preserves the original behaviour."""

    _ = seed_demo_transactions_with_metrics()


def main() -> None:
    seed_demo_transactions()
    print("[transactions.seed_demo] Transactional demo data seeded: see logs for counts.")


if __name__ == "__main__":  # pragma: no cover - script entry
    main()
