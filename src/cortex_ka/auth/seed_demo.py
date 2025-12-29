"""Seed the login database with synthetic demo users and subject links.

This script is *only* for local demo environments. It creates:

- One user per banking customer from `lista_de_clientes.txt`, with:
  - user_type = "customer"
  - role = "customer"
  - dlp_level = "standard"
  - can_access_all_subjects = False
  - one subject_id per user (the CLI-xxxxx code from the file)

- Two employee users from `lista_de_empleados.txt` (hard-coded mapping):
  - Gonzalo Guerra (admin, privileged, can_access_all_subjects=True)
  - Luis Lucci    (support, standard, can_access_all_subjects=True)

Passwords are strong random-like strings but still memorable for the demo.
In a real deployment, credentials would be provisioned via a secure channel,
not through this script.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from .db import init_login_db, login_db_session
from .models import Subject, SubjectService, User, UserSubject
from .passwords import hash_password

ROOT_DIR = Path(__file__).resolve().parents[3]
CLIENTS_FILE = ROOT_DIR / "lista_de_clientes.txt"
EMPLOYEES_FILE = ROOT_DIR / "lista_de_empleados.txt"


CLIENT_ID_RE = re.compile(r"CLI-\d+")


def _iter_client_ids(text: str) -> Iterable[str]:
    """Extract all distinct CLI-xxxx identifiers from the clientes file.

    We don't store any PII here; only synthetic subject identifiers that
    already exist in the vector store as metadata.info_personal.id_cliente.
    """

    seen: set[str] = set()
    for match in CLIENT_ID_RE.finditer(text):
        cli = match.group(0).strip()
        if cli and cli not in seen:
            seen.add(cli)
            yield cli


def seed_customers() -> None:
    if not CLIENTS_FILE.exists():
        raise FileNotFoundError(f"Clientes file not found: {CLIENTS_FILE}")

    content = CLIENTS_FILE.read_text(encoding="utf-8")
    subject_ids = list(_iter_client_ids(content))

    with login_db_session() as db:
        for cli in subject_ids:
            username = f"cliente_{cli.lower()}"
            # Skip if already exists (idempotent seeding)
            existing = db.query(User).filter_by(username=username).one_or_none()
            if existing:
                continue

            # Ensure a Subject row exists for this synthetic customer. The
            # subject_key mirrors the CLI-xxxxx identifier already present in
            # the vector store metadata.
            subject = db.query(Subject).filter(Subject.subject_key == cli).one_or_none()
            if not subject:
                subject = Subject(
                    subject_key=cli,
                    subject_type="person",
                    display_name=cli,
                    status="active",
                    attributes=None,
                )
                db.add(subject)
                db.flush()  # assign subject.id

            user = User(
                username=username,
                password_hash=hash_password(f"Demo!{cli}"),
                user_type="customer",
                role="customer",
                dlp_level="standard",
                status="active",
                can_access_all_subjects=False,
            )
            db.add(user)
            db.flush()  # assign user.id

            # Link user to subject using both the logical id and the
            # relational foreign key for new deployments.
            link = UserSubject(user_id=user.id, subject_pk=subject.id, subject_id=cli)
            db.add(link)

        # After all users/subjects are ensured, create minimal synthetic
        # services per subject for the banking demo (idempotent).
        for subject in db.query(Subject).all():
            # Skip if services already exist to keep seeding idempotent.
            if db.query(SubjectService).filter(SubjectService.subject_id == subject.id).first():
                continue

            # Simple deterministic-ish identifiers based on subject_key to
            # avoid leaking any real-world PII.
            key_fragment = subject.subject_key.replace("CLI-", "")[-4:]

            account = SubjectService(
                subject_id=subject.id,
                service_type="account",
                service_key=f"ES76-0000-0000-{key_fragment}",
                display_name="Cuenta corriente nómina",
                status="active",
                extra_metadata={"currency": "EUR", "segment": "retail"},
            )
            card = SubjectService(
                subject_id=subject.id,
                service_type="card",
                service_key=f"**** **** **** {key_fragment}",
                display_name="Tarjeta de crédito Visa",
                status="active",
                extra_metadata={"limit": 3000, "currency": "EUR"},
            )
            db.add(account)
            db.add(card)


def seed_employees() -> None:
    """Create two synthetic employees for the demo.

    We don't persist any real-world identifiers, only usernames and roles.
    """

    employees = [
        {
            "display_name": "Gonzalo Guerra",
            "username": "gguerra.admin",
            "password": "Admin!G0nzalo",  # strong-ish demo password
            "user_type": "employee",
            "role": "admin",
            "dlp_level": "privileged",
            "can_access_all_subjects": True,
        },
        {
            "display_name": "Luis Lucci",
            "username": "llucci.support",
            "password": "Support!Lu1s",
            "user_type": "employee",
            "role": "support",
            "dlp_level": "standard",
            "can_access_all_subjects": True,
        },
    ]

    with login_db_session() as db:
        for emp in employees:
            existing = db.query(User).filter_by(username=emp["username"]).one_or_none()
            if existing:
                # Update core flags to stay aligned with the spec but
                # never downgrade privileged users silently.
                existing.user_type = emp["user_type"]
                existing.role = emp["role"]
                existing.dlp_level = emp["dlp_level"]
                existing.can_access_all_subjects = bool(emp["can_access_all_subjects"])
                continue

            user = User(
                username=emp["username"],
                password_hash=hash_password(emp["password"]),
                user_type=emp["user_type"],
                role=emp["role"],
                dlp_level=emp["dlp_level"],
                status="active",
                can_access_all_subjects=bool(emp["can_access_all_subjects"]),
            )
            db.add(user)


def main() -> None:
    # Ensure schema exists first. This only creates tables if missing and
    # never drops or truncates data.
    init_login_db()

    seed_customers()
    seed_employees()

    print("[seed_demo] Login DB seeded with demo customers and employees.")
    print("[seed_demo] Example credentials (do NOT reuse in production):")
    print("  - Customer Alma (example): username=cliente_cli-81093, password=Demo!CLI-81093")
    print("  - Admin Gonzalo: username=gguerra.admin, password=Admin!G0nzalo")
    print("  - Support Luis: username=llucci.support, password=Support!Lu1s")


if __name__ == "__main__":
    main()
