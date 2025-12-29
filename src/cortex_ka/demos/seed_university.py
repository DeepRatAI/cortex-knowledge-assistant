"""Seed the database with synthetic university demo data (FCE-IUC).

This module creates a complete university simulation with:
- Students (Subject with subject_type="student")
- Faculty & Staff (User with user_type="employee")
- Enrollments (ServiceInstance with service_type="enrollment")
- Course registrations (ServiceInstance with service_type="course_registration")
- Payment plans (ServiceInstance with service_type="payment_plan")
- Grades (ServiceTransaction with transaction_type="grade")
- Tuition payments (ServiceTransaction with transaction_type="tuition_payment")

IMPORTANT: This is a DEMO seeder for the FCE-IUC demonstration.
Cortex remains domain-agnostic. See docs/demos/DEMO_FCE_IUC.md for details.

To revert to banking demo:
    python -m cortex_ka.auth.seed_demo  # Original banking seeder
    python -m cortex_ka.transactions.seed_demo  # Banking transactions
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from random import Random
from typing import Iterable

from cortex_ka.auth.db import init_login_db, login_db_session
from cortex_ka.auth.models import Subject, SubjectService, User, UserSubject
from cortex_ka.auth.passwords import hash_password
from cortex_ka.logging import logger
from cortex_ka.transactions.models import Base, ServiceInstance, ServiceTransaction

# Deterministic RNG for reproducible demos
_RNG = Random(42)


# =============================================================================
# SYNTHETIC DATA: FCE-IUC University
# =============================================================================

# Students with Argentine-style names
STUDENTS = [
    {
        "id": "ALU-20210001",
        "name": "María Fernanda García",
        "dni": "42.156.789",
        "email": "mfgarcia@mail.iuc.edu.ar",
        "career": "contador",
    },
    {
        "id": "ALU-20210002",
        "name": "Juan Pablo Rodríguez",
        "dni": "41.234.567",
        "email": "jprodriguez@mail.iuc.edu.ar",
        "career": "contador",
    },
    {
        "id": "ALU-20210003",
        "name": "Luciana Martínez",
        "dni": "43.567.890",
        "email": "lmartinez@mail.iuc.edu.ar",
        "career": "administracion",
    },
    {
        "id": "ALU-20210004",
        "name": "Agustín López",
        "dni": "40.987.654",
        "email": "alopez@mail.iuc.edu.ar",
        "career": "economia",
    },
    {
        "id": "ALU-20210005",
        "name": "Valentina Sánchez",
        "dni": "44.321.098",
        "email": "vsanchez@mail.iuc.edu.ar",
        "career": "contador",
    },
    {
        "id": "ALU-20210006",
        "name": "Tomás Fernández",
        "dni": "42.654.321",
        "email": "tfernandez@mail.iuc.edu.ar",
        "career": "sistemas",
    },
    {
        "id": "ALU-20210007",
        "name": "Camila Pérez",
        "dni": "43.111.222",
        "email": "cperez@mail.iuc.edu.ar",
        "career": "contador",
    },
    {
        "id": "ALU-20210008",
        "name": "Nicolás González",
        "dni": "41.333.444",
        "email": "ngonzalez@mail.iuc.edu.ar",
        "career": "administracion",
    },
    {
        "id": "ALU-20210009",
        "name": "Sofía Romero",
        "dni": "44.555.666",
        "email": "sromero@mail.iuc.edu.ar",
        "career": "economia",
    },
    {
        "id": "ALU-20210010",
        "name": "Matías Díaz",
        "dni": "40.777.888",
        "email": "mdiaz@mail.iuc.edu.ar",
        "career": "contador",
    },
    {
        "id": "ALU-20220011",
        "name": "Florencia Acosta",
        "dni": "45.123.456",
        "email": "facosta@mail.iuc.edu.ar",
        "career": "contador",
    },
    {
        "id": "ALU-20220012",
        "name": "Sebastián Ruiz",
        "dni": "44.789.012",
        "email": "sruiz@mail.iuc.edu.ar",
        "career": "sistemas",
    },
    {
        "id": "ALU-20220013",
        "name": "Martina Giménez",
        "dni": "45.345.678",
        "email": "mgimenez@mail.iuc.edu.ar",
        "career": "administracion",
    },
    {
        "id": "ALU-20220014",
        "name": "Franco Morales",
        "dni": "43.901.234",
        "email": "fmorales@mail.iuc.edu.ar",
        "career": "contador",
    },
    {
        "id": "ALU-20220015",
        "name": "Antonella Castro",
        "dni": "45.567.890",
        "email": "acastro@mail.iuc.edu.ar",
        "career": "economia",
    },
    {
        "id": "ALU-20230016",
        "name": "Joaquín Vargas",
        "dni": "46.111.222",
        "email": "jvargas@mail.iuc.edu.ar",
        "career": "contador",
    },
    {
        "id": "ALU-20230017",
        "name": "Catalina Medina",
        "dni": "46.333.444",
        "email": "cmedina@mail.iuc.edu.ar",
        "career": "sistemas",
    },
    {
        "id": "ALU-20230018",
        "name": "Bruno Herrera",
        "dni": "45.555.666",
        "email": "bherrera@mail.iuc.edu.ar",
        "career": "administracion",
    },
    {
        "id": "ALU-20230019",
        "name": "Julieta Peralta",
        "dni": "46.777.888",
        "email": "jperalta@mail.iuc.edu.ar",
        "career": "contador",
    },
    {
        "id": "ALU-20230020",
        "name": "Lautaro Aguirre",
        "dni": "46.999.000",
        "email": "laguirre@mail.iuc.edu.ar",
        "career": "economia",
    },
    {
        "id": "ALU-20240021",
        "name": "Milagros Torres",
        "dni": "47.123.456",
        "email": "mtorres@mail.iuc.edu.ar",
        "career": "contador",
    },
    {
        "id": "ALU-20240022",
        "name": "Facundo Ríos",
        "dni": "47.234.567",
        "email": "frios@mail.iuc.edu.ar",
        "career": "sistemas",
    },
    {
        "id": "ALU-20240023",
        "name": "Abril Campos",
        "dni": "47.345.678",
        "email": "acampos@mail.iuc.edu.ar",
        "career": "administracion",
    },
    {
        "id": "ALU-20240024",
        "name": "Thiago Molina",
        "dni": "47.456.789",
        "email": "tmolina@mail.iuc.edu.ar",
        "career": "contador",
    },
    {
        "id": "ALU-20240025",
        "name": "Emma Suárez",
        "dni": "47.567.890",
        "email": "esuarez@mail.iuc.edu.ar",
        "career": "economia",
    },
]

# Faculty members (professors)
PROFESSORS = [
    {
        "username": "prof.malvestiti",
        "name": "Dr. Daniel Malvestiti",
        "password": "Prof!Dan1el2025",
        "department": "Contabilidad",
        "role": "professor",
    },
    {
        "username": "prof.garcia",
        "name": "Dra. Laura García",
        "password": "Prof!Laura2025",
        "department": "Economía",
        "role": "professor",
    },
    {
        "username": "prof.mendoza",
        "name": "Mg. Roberto Mendoza",
        "password": "Prof!Robert2025",
        "department": "Administración",
        "role": "professor",
    },
    {
        "username": "prof.villanueva",
        "name": "Mg. Andrés Villanueva",
        "password": "Prof!Andres2025",
        "department": "Sistemas",
        "role": "professor",
    },
    {
        "username": "prof.rossi",
        "name": "Dr. Miguel Rossi",
        "password": "Prof!Miguel2025",
        "department": "Derecho",
        "role": "professor",
    },
    {
        "username": "prof.suarez",
        "name": "Cra. Patricia Suárez",
        "password": "Prof!Patri2025",
        "department": "Impuestos",
        "role": "professor",
    },
    {
        "username": "prof.cartier",
        "name": "Cr. Enrique Cartier",
        "password": "Prof!Enriqu2025",
        "department": "Costos",
        "role": "professor",
    },
    {
        "username": "prof.bianchi",
        "name": "Mg. Ricardo Bianchi",
        "password": "Prof!Ricardo2025",
        "department": "Finanzas",
        "role": "professor",
    },
]

# Administrative staff
STAFF = [
    {
        "username": "admin.secretaria",
        "name": "Secretaría Académica",
        "password": "Admin!Secre2025",
        "role": "admin",
        "dlp_level": "privileged",
    },
    {
        "username": "admin.tesoreria",
        "name": "Tesorería FCE-IUC",
        "password": "Admin!Tesor2025",
        "role": "support",
        "dlp_level": "standard",
    },
    {
        "username": "admin.bedelía",
        "name": "Bedelía FCE-IUC",
        "password": "Admin!Bedel2025",
        "role": "support",
        "dlp_level": "standard",
    },
]

# Courses aligned with the synthetic corpus
COURSES = {
    "contador": [
        {"code": "CON101", "name": "Contabilidad I", "year": 1, "credits": 8},
        {
            "code": "ECO101",
            "name": "Introducción a la Economía",
            "year": 1,
            "credits": 6,
        },
        {"code": "ADM101", "name": "Administración I", "year": 1, "credits": 6},
        {"code": "MAT101", "name": "Matemática I", "year": 1, "credits": 8},
        {"code": "DER101", "name": "Derecho Privado I", "year": 1, "credits": 6},
        {"code": "CON201", "name": "Contabilidad II", "year": 2, "credits": 8},
        {"code": "ECO203", "name": "Economía II", "year": 2, "credits": 6},
        {"code": "FIS201", "name": "Impuestos I", "year": 2, "credits": 8},
        {"code": "EST101", "name": "Estadística I", "year": 2, "credits": 6},
        {"code": "CON301", "name": "Contabilidad III", "year": 3, "credits": 8},
        {"code": "AUD101", "name": "Auditoría I", "year": 3, "credits": 8},
        {"code": "FIS302", "name": "Impuestos II", "year": 3, "credits": 8},
    ],
    "administracion": [
        {"code": "ADM101", "name": "Administración I", "year": 1, "credits": 8},
        {
            "code": "ECO101",
            "name": "Introducción a la Economía",
            "year": 1,
            "credits": 6,
        },
        {"code": "MAT101", "name": "Matemática I", "year": 1, "credits": 6},
        {"code": "CON101", "name": "Contabilidad I", "year": 1, "credits": 6},
        {"code": "ADM201", "name": "Administración II", "year": 2, "credits": 8},
        {"code": "ADM301", "name": "Recursos Humanos", "year": 2, "credits": 6},
        {"code": "ADM302", "name": "Marketing", "year": 2, "credits": 6},
        {"code": "FIN101", "name": "Finanzas de Empresas", "year": 3, "credits": 8},
    ],
    "economia": [
        {
            "code": "ECO101",
            "name": "Introducción a la Economía",
            "year": 1,
            "credits": 8,
        },
        {"code": "MAT101", "name": "Matemática I", "year": 1, "credits": 8},
        {"code": "ECO102", "name": "Microeconomía I", "year": 1, "credits": 6},
        {"code": "ECO103", "name": "Macroeconomía I", "year": 1, "credits": 6},
        {"code": "ECO203", "name": "Economía II", "year": 2, "credits": 8},
        {"code": "ECO301", "name": "Finanzas Públicas", "year": 2, "credits": 6},
        {"code": "ECO401", "name": "Comercio Internacional", "year": 3, "credits": 6},
        {"code": "ECO501", "name": "Econometría", "year": 3, "credits": 8},
    ],
    "sistemas": [
        {
            "code": "SIS101",
            "name": "Introducción a los Sistemas",
            "year": 1,
            "credits": 6,
        },
        {"code": "MAT101", "name": "Matemática I", "year": 1, "credits": 8},
        {"code": "CON101", "name": "Contabilidad I", "year": 1, "credits": 6},
        {"code": "SIS201", "name": "Sistemas de Información", "year": 2, "credits": 8},
        {
            "code": "SIS301",
            "name": "Tecnologías de Información",
            "year": 2,
            "credits": 8,
        },
        {"code": "AUD402", "name": "Auditoría de Sistemas", "year": 3, "credits": 6},
    ],
}

# Tuition costs (monthly, in ARS)
TUITION_MONTHLY = {
    "contador": 85000,
    "administracion": 82000,
    "economia": 80000,
    "sistemas": 88000,
}


@dataclass(frozen=True)
class UniversitySeedResult:
    """Result metrics for university demo seeding."""

    students_created: int
    employees_created: int
    enrollments_created: int
    course_registrations_created: int
    grades_created: int
    payments_created: int


def _ensure_schema() -> None:
    """Ensure all required tables exist."""
    with login_db_session() as db:
        engine = db.get_bind()
        Base.metadata.create_all(bind=engine)


def _clear_existing_data() -> None:
    """Clear existing demo data for a fresh start.

    WARNING: This deletes all subjects, users, and related data.
    Only use in demo environments.
    """
    with login_db_session() as db:
        # Clear transactions first (FK constraints)
        db.query(ServiceTransaction).delete()
        db.query(ServiceInstance).delete()
        db.query(SubjectService).delete()
        db.query(UserSubject).delete()
        db.query(Subject).delete()
        # Keep admin users but clear demo users
        db.query(User).filter(User.user_type.in_(["customer", "employee"])).delete()
        db.commit()
        logger.info("university_seed_cleared_existing_data")


def _create_students() -> int:
    """Create student subjects and their user accounts."""
    created = 0

    with login_db_session() as db:
        for student in STUDENTS:
            # Check if already exists
            existing = db.query(Subject).filter(Subject.subject_key == student["id"]).first()
            if existing:
                continue

            # Create Subject (the student entity)
            subject = Subject(
                subject_key=student["id"],
                subject_type="student",
                display_name=student["name"],
                status="active",
                full_name=student["name"],
                document_id=student["dni"],
                email=student["email"],
                attributes={
                    "career": student["career"],
                    "enrollment_year": int(student["id"].split("-")[1][:4]),
                },
            )
            db.add(subject)
            db.flush()

            # Create User account for the student
            username = f"alumno_{student['id'].lower()}"
            user = User(
                username=username,
                password_hash=hash_password(f"Demo!{student['id']}"),
                user_type="customer",
                role="customer",
                dlp_level="standard",
                status="active",
                can_access_all_subjects=False,
            )
            db.add(user)
            db.flush()

            # Link user to subject
            link = UserSubject(
                user_id=user.id,
                subject_pk=subject.id,
                subject_id=student["id"],
            )
            db.add(link)
            created += 1

    return created


def _create_employees() -> int:
    """Create professor and staff user accounts."""
    created = 0

    with login_db_session() as db:
        # Professors
        for prof in PROFESSORS:
            existing = db.query(User).filter(User.username == prof["username"]).first()
            if existing:
                continue

            user = User(
                username=prof["username"],
                password_hash=hash_password(prof["password"]),
                user_type="employee",
                role=prof["role"],
                dlp_level="standard",
                status="active",
                can_access_all_subjects=True,  # Professors see all students
            )
            db.add(user)
            created += 1

        # Administrative staff
        for staff in STAFF:
            existing = db.query(User).filter(User.username == staff["username"]).first()
            if existing:
                continue

            user = User(
                username=staff["username"],
                password_hash=hash_password(staff["password"]),
                user_type="employee",
                role=staff["role"],
                dlp_level=staff["dlp_level"],
                status="active",
                can_access_all_subjects=True,
            )
            db.add(user)
            created += 1

    return created


def _create_enrollments() -> int:
    """Create career enrollment (matrícula) for each student."""
    created = 0
    now = datetime.now(timezone.utc)

    with login_db_session() as db:
        for student in STUDENTS:
            subject = db.query(Subject).filter(Subject.subject_key == student["id"]).first()
            if not subject:
                continue

            # Check if enrollment already exists
            existing = (
                db.query(ServiceInstance)
                .filter(
                    ServiceInstance.subject_id == subject.id,
                    ServiceInstance.service_type == "enrollment",
                )
                .first()
            )
            if existing:
                continue

            enrollment_year = int(student["id"].split("-")[1][:4])
            career = student["career"]

            enrollment = ServiceInstance(
                subject_id=subject.id,
                service_type="enrollment",
                service_key=f"MAT-{enrollment_year}-{student['id'][-4:]}",
                status="active",
                extra_metadata={
                    "career": career,
                    "career_name": {
                        "contador": "Contador Público",
                        "administracion": "Licenciatura en Administración",
                        "economia": "Licenciatura en Economía",
                        "sistemas": "Licenciatura en Sistemas de Información",
                    }.get(career, career),
                    "enrollment_date": f"{enrollment_year}-03-01",
                    "expected_graduation": f"{enrollment_year + 5}-12-15",
                    "academic_status": "regular",
                },
            )
            db.add(enrollment)
            created += 1

    return created


def _create_course_registrations() -> int:
    """Create course registrations (cursadas) for students."""
    created = 0
    now = datetime.now(timezone.utc)
    current_year = now.year

    with login_db_session() as db:
        for student in STUDENTS:
            subject = db.query(Subject).filter(Subject.subject_key == student["id"]).first()
            if not subject:
                continue

            career = student["career"]
            enrollment_year = int(student["id"].split("-")[1][:4])
            years_enrolled = current_year - enrollment_year + 1

            # Get courses for this career based on years enrolled
            available_courses = [
                c for c in COURSES.get(career, []) if c["year"] <= min(years_enrolled, 3)  # Max 3 years of courses
            ]

            # Register for courses (some completed, some in progress)
            for course in available_courses:
                existing = (
                    db.query(ServiceInstance)
                    .filter(
                        ServiceInstance.subject_id == subject.id,
                        ServiceInstance.service_key == f"CUR-{course['code']}-{student['id'][-4:]}",
                    )
                    .first()
                )
                if existing:
                    continue

                # Determine status based on course year vs enrollment time
                course_year = enrollment_year + course["year"] - 1
                if course_year < current_year:
                    status = "completed" if _RNG.random() > 0.15 else "failed"  # 85% pass rate
                elif course_year == current_year:
                    status = "in_progress"
                else:
                    status = "pending"

                if status == "pending":
                    continue  # Don't create registrations for future courses

                registration = ServiceInstance(
                    subject_id=subject.id,
                    service_type="course_registration",
                    service_key=f"CUR-{course['code']}-{student['id'][-4:]}",
                    status=status,
                    extra_metadata={
                        "course_code": course["code"],
                        "course_name": course["name"],
                        "credits": course["credits"],
                        "academic_year": course_year,
                        "semester": _RNG.choice(["1er cuatrimestre", "2do cuatrimestre"]),
                    },
                )
                db.add(registration)
                created += 1

    return created


def _create_grades() -> int:
    """Create grade transactions for course registrations."""
    created = 0
    now = datetime.now(timezone.utc)

    with login_db_session() as db:
        # Get all completed or in-progress course registrations
        registrations = (
            db.query(ServiceInstance)
            .filter(
                ServiceInstance.service_type == "course_registration",
                ServiceInstance.status.in_(["completed", "in_progress", "failed"]),
            )
            .all()
        )

        for reg in registrations:
            # Check if grades already exist
            existing_grades = (
                db.query(ServiceTransaction)
                .filter(
                    ServiceTransaction.service_instance_id == reg.id,
                    ServiceTransaction.transaction_type == "grade",
                )
                .count()
            )
            if existing_grades > 0:
                continue

            metadata = reg.extra_metadata or {}
            course_year = metadata.get("academic_year", 2024)

            # Base date for the course
            base_date = datetime(course_year, 4, 1, tzinfo=timezone.utc)

            if reg.status in ["completed", "failed"]:
                # Generate parciales and final
                # Parcial 1
                grade_p1 = _RNG.uniform(4.0, 10.0) if reg.status == "completed" else _RNG.uniform(2.0, 5.0)
                db.add(
                    ServiceTransaction(
                        service_instance_id=reg.id,
                        timestamp=base_date + timedelta(days=45),
                        transaction_type="grade",
                        amount=round(grade_p1, 1),
                        currency="points",
                        description=f"Parcial 1 - {metadata.get('course_name', 'Materia')}",
                        extra_metadata={
                            "exam_type": "partial_1",
                            "course_code": metadata.get("course_code"),
                            "max_grade": 10,
                            "passing_grade": 4,
                        },
                    )
                )
                created += 1

                # Parcial 2
                grade_p2 = _RNG.uniform(4.0, 10.0) if reg.status == "completed" else _RNG.uniform(2.0, 5.0)
                db.add(
                    ServiceTransaction(
                        service_instance_id=reg.id,
                        timestamp=base_date + timedelta(days=90),
                        transaction_type="grade",
                        amount=round(grade_p2, 1),
                        currency="points",
                        description=f"Parcial 2 - {metadata.get('course_name', 'Materia')}",
                        extra_metadata={
                            "exam_type": "partial_2",
                            "course_code": metadata.get("course_code"),
                            "max_grade": 10,
                            "passing_grade": 4,
                        },
                    )
                )
                created += 1

                # Final (only if passed partials)
                if grade_p1 >= 4 and grade_p2 >= 4:
                    grade_final = _RNG.uniform(5.0, 10.0) if reg.status == "completed" else _RNG.uniform(2.0, 5.0)
                    db.add(
                        ServiceTransaction(
                            service_instance_id=reg.id,
                            timestamp=base_date + timedelta(days=120),
                            transaction_type="grade",
                            amount=round(grade_final, 1),
                            currency="points",
                            description=f"Final - {metadata.get('course_name', 'Materia')}",
                            extra_metadata={
                                "exam_type": "final",
                                "course_code": metadata.get("course_code"),
                                "max_grade": 10,
                                "passing_grade": 4,
                            },
                        )
                    )
                    created += 1

            elif reg.status == "in_progress":
                # Only first partial so far (or nothing)
                if _RNG.random() > 0.3:  # 70% already took first partial
                    grade_p1 = round(_RNG.uniform(4.0, 10.0), 1)
                    db.add(
                        ServiceTransaction(
                            service_instance_id=reg.id,
                            timestamp=now - timedelta(days=_RNG.randint(10, 60)),
                            transaction_type="grade",
                            amount=grade_p1,
                            currency="points",
                            description=f"Parcial 1 - {metadata.get('course_name', 'Materia')}",
                            extra_metadata={
                                "exam_type": "partial_1",
                                "course_code": metadata.get("course_code"),
                                "max_grade": 10,
                                "passing_grade": 4,
                            },
                        )
                    )
                    created += 1

    return created


def _create_payment_plans() -> int:
    """Create payment plans and tuition payment transactions."""
    created = 0
    now = datetime.now(timezone.utc)
    current_year = now.year

    with login_db_session() as db:
        for student in STUDENTS:
            subject = db.query(Subject).filter(Subject.subject_key == student["id"]).first()
            if not subject:
                continue

            career = student["career"]
            enrollment_year = int(student["id"].split("-")[1][:4])
            monthly_amount = TUITION_MONTHLY.get(career, 80000)

            # Create payment plan for current year
            plan_key = f"PLAN-{current_year}-{student['id'][-4:]}"
            existing_plan = db.query(ServiceInstance).filter(ServiceInstance.service_key == plan_key).first()

            if not existing_plan:
                payment_plan = ServiceInstance(
                    subject_id=subject.id,
                    service_type="payment_plan",
                    service_key=plan_key,
                    status="active",
                    extra_metadata={
                        "year": current_year,
                        "monthly_amount": monthly_amount,
                        "total_installments": 10,  # Mar-Dec
                        "payment_method": _RNG.choice(["débito_automático", "transferencia", "efectivo"]),
                    },
                )
                db.add(payment_plan)
                db.flush()
                created += 1
            else:
                payment_plan = existing_plan

            # Create payment transactions for months already passed
            current_month = now.month

            # Get all existing transactions for this payment plan to avoid duplicates
            existing_txs = (
                db.query(ServiceTransaction)
                .filter(
                    ServiceTransaction.service_instance_id == payment_plan.id,
                    ServiceTransaction.transaction_type == "tuition_payment",
                )
                .all()
            )
            existing_months = set()
            for tx in existing_txs:
                if tx.extra_metadata and "month" in tx.extra_metadata:
                    existing_months.add(tx.extra_metadata["month"])

            for month in range(3, min(current_month + 1, 13)):  # March onwards
                if month in existing_months:
                    continue

                # Simulate: 90% pay on time, 8% late, 2% unpaid
                rand = _RNG.random()
                if rand < 0.90:
                    status = "paid"
                    pay_day = _RNG.randint(1, 10)
                elif rand < 0.98:
                    status = "paid_late"
                    pay_day = _RNG.randint(15, 28)
                else:
                    if month < current_month - 1:  # Only mark old months as pending
                        status = "pending"
                        pay_day = None
                    else:
                        status = "paid"
                        pay_day = _RNG.randint(1, 10)

                payment_date = datetime(current_year, month, pay_day or 1, 10, 0, 0, tzinfo=timezone.utc)

                db.add(
                    ServiceTransaction(
                        service_instance_id=payment_plan.id,
                        timestamp=payment_date,
                        transaction_type="tuition_payment",
                        amount=float(monthly_amount),
                        currency="ARS",
                        description=f"Cuota {month}/2025 - {career.title()}",
                        extra_metadata={
                            "month": month,
                            "year": current_year,
                            "status": status,
                            "due_date": f"{current_year}-{month:02d}-10",
                            "receipt_number": f"REC-{current_year}{month:02d}-{student['id'][-4:]}",
                        },
                    )
                )
                created += 1

    return created


def seed_university_demo(clean: bool = False) -> UniversitySeedResult:
    """Main entry point for seeding university demo data.

    Args:
        clean: If True, clears existing data before seeding.

    Returns:
        UniversitySeedResult with counts of created entities.
    """
    init_login_db()
    _ensure_schema()

    if clean:
        _clear_existing_data()

    students = _create_students()
    employees = _create_employees()
    enrollments = _create_enrollments()
    course_regs = _create_course_registrations()
    grades = _create_grades()
    payments = _create_payment_plans()

    result = UniversitySeedResult(
        students_created=students,
        employees_created=employees,
        enrollments_created=enrollments,
        course_registrations_created=course_regs,
        grades_created=grades,
        payments_created=payments,
    )

    logger.info(
        "university_demo_seed_completed",
        students=result.students_created,
        employees=result.employees_created,
        enrollments=result.enrollments_created,
        course_registrations=result.course_registrations_created,
        grades=result.grades_created,
        payments=result.payments_created,
    )

    return result


def main() -> None:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Seed FCE-IUC university demo data")
    parser.add_argument("--clean", action="store_true", help="Clear existing data first")
    args = parser.parse_args()

    result = seed_university_demo(clean=args.clean)

    print("\n" + "=" * 60)
    print("FCE-IUC University Demo Data Seeded Successfully")
    print("=" * 60)
    print(f"  Students created:            {result.students_created}")
    print(f"  Employees created:           {result.employees_created}")
    print(f"  Career enrollments:          {result.enrollments_created}")
    print(f"  Course registrations:        {result.course_registrations_created}")
    print(f"  Grades recorded:             {result.grades_created}")
    print(f"  Payment transactions:        {result.payments_created}")
    print("=" * 60)
    print("\nExample credentials (demo only, do NOT use in production):")
    print("  Student: alumno_alu-20210001 / Demo!ALU-20210001")
    print("  Professor: prof.malvestiti / Prof!Dan1el2025")
    print("  Admin: admin.secretaria / Admin!Secre2025")
    print("=" * 60)


if __name__ == "__main__":
    main()
