"""PII Masking utilities for contextual data visibility.

This module implements enterprise-grade PII masking following:
- NIST SP 800-188: De-Identification of Personal Information
- ISO 27701: Privacy Information Management
- GDPR/LGPD principles: Data Minimization, Purpose Limitation

The masking strategy follows "Need-to-Know" principle:
- Customers see their OWN full data (self-service)
- Employees see partial data (enough to assist, not to exploit)
- Admins see full data (with audit trail)

IMPORTANT: This is PRE-CONTEXT masking (before LLM sees the data).
The DLP layer (enforce_dlp) provides POST-RESPONSE defense-in-depth.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ViewerRole(str, Enum):
    """Role of the user viewing the data.

    Determines masking level applied to PII fields.
    """

    CUSTOMER = "customer"  # Viewing their own data
    EMPLOYEE = "employee"  # Backoffice operator
    ADMIN = "admin"  # Full privileged access
    SYSTEM = "system"  # Internal processes (no masking)


@dataclass(frozen=True)
class MaskingPolicy:
    """Configuration for how PII should be masked per role.

    This dataclass allows future extension for domain-specific
    policies without changing function signatures.
    """

    show_last_n_digits_dni: int = 3
    show_last_n_digits_phone: int = 4
    show_first_n_chars_email: int = 1
    mask_char: str = "*"


# Default policy used across the application
DEFAULT_POLICY = MaskingPolicy()


def mask_dni(
    dni: Optional[str],
    viewer_role: ViewerRole,
    is_own_data: bool = False,
    policy: MaskingPolicy = DEFAULT_POLICY,
) -> Optional[str]:
    """Mask DNI/document ID based on viewer role and ownership.

    Args:
        dni: Document ID (e.g., "42.156.789" or "42156789")
        viewer_role: Role of the user viewing this data
        is_own_data: True if the viewer is looking at their own data
        policy: Masking configuration

    Returns:
        Masked DNI like "XX.XXX.789" for employees,
        or full DNI for owner/admin/system.

    Examples:
        >>> mask_dni("42.156.789", ViewerRole.EMPLOYEE)
        'XX.XXX.789'
        >>> mask_dni("42.156.789", ViewerRole.CUSTOMER, is_own_data=True)
        '42.156.789'
        >>> mask_dni("42156789", ViewerRole.EMPLOYEE)
        'XXXXX789'
    """
    if not dni:
        return None

    # Full access: own data, admin, or system
    if is_own_data or viewer_role in (ViewerRole.ADMIN, ViewerRole.SYSTEM):
        return dni

    # Employee gets partially masked view
    clean_dni = dni.replace(".", "").replace("-", "").replace(" ", "")
    n = policy.show_last_n_digits_dni

    if len(clean_dni) <= n:
        return dni  # Too short to mask meaningfully

    masked_part = "X" * (len(clean_dni) - n)
    visible_part = clean_dni[-n:]

    # Preserve original formatting if present
    if "." in dni:
        # Argentine format: XX.XXX.789
        if len(clean_dni) >= 8:
            return f"XX.XXX.{visible_part}"
        return f"XX.{visible_part}"

    return masked_part + visible_part


def mask_cuil(
    cuil: Optional[str],
    viewer_role: ViewerRole,
    is_own_data: bool = False,
    policy: MaskingPolicy = DEFAULT_POLICY,
) -> Optional[str]:
    """Mask CUIL/CUIT (Argentine tax ID) based on viewer role.

    Format: XX-XXXXXXXX-X (type-dni-verifier)
    Employee sees: 20-XXXXXXXX-X (preserves type prefix and verifier)

    Args:
        cuil: Tax ID (e.g., "20-42156789-3")
        viewer_role: Role of the user viewing this data
        is_own_data: True if viewing own data
        policy: Masking configuration

    Returns:
        Masked CUIL like "20-XXXXXXXX-3" for employees.
    """
    if not cuil:
        return None

    if is_own_data or viewer_role in (ViewerRole.ADMIN, ViewerRole.SYSTEM):
        return cuil

    # Match CUIL pattern: XX-XXXXXXXX-X
    match = re.match(r"^(\d{2})-?(\d{7,8})-?(\d)$", cuil.replace(" ", ""))
    if not match:
        # Fallback: mask middle portion
        if len(cuil) > 4:
            return cuil[:2] + "X" * (len(cuil) - 4) + cuil[-2:]
        return cuil

    prefix, dni_part, verifier = match.groups()
    masked_dni = "X" * len(dni_part)
    return f"{prefix}-{masked_dni}-{verifier}"


def mask_email(
    email: Optional[str],
    viewer_role: ViewerRole,
    is_own_data: bool = False,
    policy: MaskingPolicy = DEFAULT_POLICY,
) -> Optional[str]:
    """Mask email address based on viewer role.

    Args:
        email: Email address (e.g., "maria.garcia@university.edu")
        viewer_role: Role of the user viewing this data
        is_own_data: True if viewing own data
        policy: Masking configuration

    Returns:
        Masked email like "m***@university.edu" for employees.
    """
    if not email:
        return None

    if is_own_data or viewer_role in (ViewerRole.ADMIN, ViewerRole.SYSTEM):
        return email

    if "@" not in email:
        return "***@***"

    local, domain = email.rsplit("@", 1)
    n = policy.show_first_n_chars_email

    if len(local) <= n:
        masked_local = local[0] + "***" if local else "***"
    else:
        masked_local = local[:n] + "***"

    return f"{masked_local}@{domain}"


def mask_phone(
    phone: Optional[str],
    viewer_role: ViewerRole,
    is_own_data: bool = False,
    policy: MaskingPolicy = DEFAULT_POLICY,
) -> Optional[str]:
    """Mask phone number based on viewer role.

    Args:
        phone: Phone number (e.g., "+54 9 11 1234-5678")
        viewer_role: Role of the user viewing this data
        is_own_data: True if viewing own data
        policy: Masking configuration

    Returns:
        Masked phone like "+54 9 11 ****-5678" for employees.
    """
    if not phone:
        return None

    if is_own_data or viewer_role in (ViewerRole.ADMIN, ViewerRole.SYSTEM):
        return phone

    # Extract only digits
    digits = re.sub(r"\D", "", phone)
    n = policy.show_last_n_digits_phone

    if len(digits) <= n:
        return phone  # Too short to mask

    # Preserve country code prefix if present
    if phone.startswith("+"):
        # Find country code (2-3 digits after +)
        match = re.match(r"^\+(\d{1,3})", phone)
        if match:
            country_code = match.group(1)
            # Mask middle, show last n digits
            visible_end = digits[-n:]
            return f"+{country_code} {'*' * 4}-{visible_end}"

    # Simple format: mask all but last n
    visible_end = digits[-n:]
    return "*" * (len(digits) - n) + visible_end


@dataclass(frozen=True)
class SubjectPII:
    """Personal Identifiable Information for a Subject.

    This dataclass holds the masked or unmasked PII fields
    that can be safely passed to CustomerSnapshot.
    All fields are already processed through masking functions.
    """

    display_name: Optional[str] = None
    document_id: Optional[str] = None  # DNI - possibly masked
    tax_id: Optional[str] = None  # CUIL/CUIT - possibly masked
    email: Optional[str] = None  # Email - possibly masked
    phone: Optional[str] = None  # Phone - possibly masked


def build_subject_pii(
    *,
    display_name: Optional[str],
    full_name: Optional[str],
    document_id: Optional[str],
    tax_id: Optional[str],
    email: Optional[str],
    phone: Optional[str],
    viewer_role: ViewerRole,
    is_own_data: bool = False,
) -> SubjectPII:
    """Build a SubjectPII with appropriate masking for the viewer.

    This is the main entry point for creating masked PII.
    It applies role-based masking to all fields.

    Args:
        display_name: Human-readable name (never masked)
        full_name: Legal full name (used if display_name is None)
        document_id: DNI/SSN
        tax_id: CUIL/CUIT/EIN
        email: Email address
        phone: Phone number
        viewer_role: Role determining masking level
        is_own_data: Whether viewer is looking at their own data

    Returns:
        SubjectPII with appropriately masked fields.
    """
    # Use full_name as fallback for display_name
    name = display_name or full_name

    return SubjectPII(
        display_name=name,
        document_id=mask_dni(document_id, viewer_role, is_own_data),
        tax_id=mask_cuil(tax_id, viewer_role, is_own_data),
        email=mask_email(email, viewer_role, is_own_data),
        phone=mask_phone(phone, viewer_role, is_own_data),
    )


__all__ = [
    "ViewerRole",
    "MaskingPolicy",
    "SubjectPII",
    "mask_dni",
    "mask_cuil",
    "mask_email",
    "mask_phone",
    "build_subject_pii",
]
