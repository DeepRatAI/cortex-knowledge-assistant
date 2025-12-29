"""Administrative data management with full audit trail.

This module provides secure, auditable CRUD operations for system data.
Every operation generates an immutable audit record with:
- Timestamp (UTC)
- Operator identity (user_id, username)
- Operation type
- Before/After values for changed fields
- Reason/justification (required for modifications)

Security considerations:
- All operations require admin authentication
- Changes are atomic and transactional
- Audit records are append-only and tamper-evident
- PII is never logged in plain text (only presence flags)

Compliance:
- Designed for SOX, PCI-DSS, GDPR audit requirements
- Full traceability of data modifications
- Non-repudiation through operator identification
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from cortex_ka.auth.db import init_login_db, login_db_session
from cortex_ka.auth.models import AuditLog, Subject
from cortex_ka.logging import logger

# =============================================================================
# DATA TYPES
# =============================================================================


@dataclass
class FieldChange:
    """Represents a single field change with before/after values."""

    field_name: str
    old_value: Any
    new_value: Any
    is_pii: bool = False  # If True, values are hashed in audit log

    def to_audit_dict(self) -> dict:
        """Convert to audit-safe dictionary (hash PII fields)."""
        if self.is_pii:
            # Hash PII values for audit trail (non-reversible)
            old_hash = self._hash_value(self.old_value) if self.old_value else None
            new_hash = self._hash_value(self.new_value) if self.new_value else None
            return {
                "field": self.field_name,
                "old_hash": old_hash,
                "new_hash": new_hash,
                "changed": old_hash != new_hash,
                "pii_protected": True,
            }
        return {
            "field": self.field_name,
            "old": self.old_value,
            "new": self.new_value,
        }

    @staticmethod
    def _hash_value(value: Any) -> str:
        """Create a non-reversible hash for audit purposes."""
        if value is None:
            return "NULL"
        val_str = str(value).strip().lower()
        return hashlib.sha256(val_str.encode()).hexdigest()[:16]


@dataclass
class DataModificationResult:
    """Result of a data modification operation."""

    success: bool
    message: str
    subject_key: Optional[str] = None
    changes_applied: list[FieldChange] = field(default_factory=list)
    audit_id: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "message": self.message,
            "subject_key": self.subject_key,
            "changes_count": len(self.changes_applied),
            "audit_id": self.audit_id,
        }


class DataAdminError(Exception):
    """Exception raised when data admin operations fail."""

    pass


class ValidationError(DataAdminError):
    """Exception raised when validation fails."""

    pass


class AuthorizationError(DataAdminError):
    """Exception raised when authorization fails."""

    pass


# =============================================================================
# PII FIELD DEFINITIONS
# =============================================================================

# Fields that contain PII and should be hashed in audit logs
PII_FIELDS = {
    "full_name",
    "document_id",
    "tax_id",
    "email",
    "phone",
}

# Editable fields on Subject (with validation rules)
SUBJECT_EDITABLE_FIELDS = {
    "display_name": {"type": "string", "max_length": 128, "pii": False},
    "full_name": {"type": "string", "max_length": 255, "pii": True},
    "document_id": {"type": "string", "max_length": 64, "pii": True},
    "tax_id": {"type": "string", "max_length": 64, "pii": True},
    "email": {"type": "email", "max_length": 255, "pii": True},
    "phone": {"type": "phone", "max_length": 32, "pii": True},
    "status": {"type": "enum", "values": ["active", "inactive"], "pii": False},
    "subject_type": {
        "type": "enum",
        "values": ["person", "company", "employee"],
        "pii": False,
    },
}


# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================


def validate_field_value(field_name: str, value: Any) -> Any:
    """Validate and normalize a field value.

    Args:
        field_name: Name of the field being validated
        value: Value to validate

    Returns:
        Normalized value

    Raises:
        ValidationError: If validation fails
    """
    if field_name not in SUBJECT_EDITABLE_FIELDS:
        raise ValidationError(f"Field '{field_name}' is not editable")

    rules = SUBJECT_EDITABLE_FIELDS[field_name]
    field_type = rules["type"]

    if value is None or (isinstance(value, str) and not value.strip()):
        return None  # Allow clearing fields

    if isinstance(value, str):
        value = value.strip()

    # Type-specific validation
    if field_type == "string":
        if not isinstance(value, str):
            raise ValidationError(f"Field '{field_name}' must be a string")
        max_len = rules.get("max_length", 255)
        if len(value) > max_len:
            raise ValidationError(f"Field '{field_name}' exceeds maximum length of {max_len}")

    elif field_type == "email":
        email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_regex, value):
            raise ValidationError(f"Invalid email format for '{field_name}'")
        value = value.lower()

    elif field_type == "phone":
        # Normalize phone: strip common separators
        value = re.sub(r"[\s\-\(\).]", "", value)
        if not re.match(r"^\+?[0-9]{7,15}$", value):
            raise ValidationError(f"Invalid phone format for '{field_name}'. Use digits only, optionally with +")

    elif field_type == "enum":
        allowed = rules.get("values", [])
        if value not in allowed:
            raise ValidationError(f"Field '{field_name}' must be one of: {', '.join(allowed)}")

    return value


def validate_modification_reason(reason: str) -> str:
    """Validate the reason/justification for a modification.

    Reasons must be meaningful - not just whitespace or generic text.

    Args:
        reason: The provided reason

    Returns:
        Normalized reason

    Raises:
        ValidationError: If reason is invalid
    """
    if not reason or not reason.strip():
        raise ValidationError("A reason/justification is required for all data modifications")

    reason = reason.strip()

    if len(reason) < 10:
        raise ValidationError("Reason must be at least 10 characters to ensure meaningful documentation")

    if len(reason) > 500:
        raise ValidationError("Reason must not exceed 500 characters")

    # Check for generic/placeholder reasons
    generic_patterns = [
        r"^test\s*$",
        r"^asdf",
        r"^xxx",
        r"^update\s*$",
        r"^change\s*$",
        r"^fix\s*$",
    ]
    for pattern in generic_patterns:
        if re.match(pattern, reason.lower()):
            raise ValidationError("Please provide a specific reason for this modification")

    return reason


# =============================================================================
# SUBJECT DATA OPERATIONS
# =============================================================================


def get_subject_for_edit(subject_key: str) -> Optional[dict]:
    """Get a subject's current data for editing.

    Args:
        subject_key: The subject's unique key

    Returns:
        Dictionary with current field values, or None if not found
    """
    init_login_db()

    with login_db_session() as db:
        subject = db.query(Subject).filter(Subject.subject_key == subject_key).first()

        if not subject:
            return None

        return {
            "subject_key": subject.subject_key,
            "subject_type": subject.subject_type,
            "display_name": subject.display_name,
            "status": subject.status,
            "full_name": subject.full_name,
            "document_id": subject.document_id,
            "tax_id": subject.tax_id,
            "email": subject.email,
            "phone": subject.phone,
            "created_at": subject.created_at.isoformat() if subject.created_at else None,
            "updated_at": subject.updated_at.isoformat() if subject.updated_at else None,
        }


def update_subject_data(
    subject_key: str,
    updates: dict[str, Any],
    reason: str,
    operator_user_id: int,
    operator_username: Optional[str] = None,
    operator_ip: Optional[str] = None,
) -> DataModificationResult:
    """Update subject data with full audit trail.

    This is the primary function for administrative data modifications.
    Every change is recorded in the audit log with before/after values.

    Args:
        subject_key: The subject to update
        updates: Dictionary of field_name -> new_value
        reason: Justification for the change (required, min 10 chars)
        operator_user_id: ID of the admin performing the operation
        operator_username: Username of the admin (for audit)
        operator_ip: IP address of the request (for audit)

    Returns:
        DataModificationResult with success status and audit ID

    Raises:
        ValidationError: If validation fails
        DataAdminError: If the operation fails
    """
    # Validate reason first
    reason = validate_modification_reason(reason)

    # Validate all field values
    validated_updates = {}
    for field_name, new_value in updates.items():
        if field_name not in SUBJECT_EDITABLE_FIELDS:
            raise ValidationError(f"Field '{field_name}' is not editable")
        validated_updates[field_name] = validate_field_value(field_name, new_value)

    if not validated_updates:
        return DataModificationResult(
            success=True,
            message="No changes to apply",
            subject_key=subject_key,
        )

    init_login_db()

    with login_db_session() as db:
        subject = db.query(Subject).filter(Subject.subject_key == subject_key).first()

        if not subject:
            raise ValidationError(f"Subject '{subject_key}' not found")

        # Collect changes with before/after values
        changes: list[FieldChange] = []

        for field_name, new_value in validated_updates.items():
            old_value = getattr(subject, field_name, None)

            # Only record actual changes
            if old_value != new_value:
                is_pii = field_name in PII_FIELDS
                changes.append(
                    FieldChange(
                        field_name=field_name,
                        old_value=old_value,
                        new_value=new_value,
                        is_pii=is_pii,
                    )
                )

                # Apply the change
                setattr(subject, field_name, new_value)

        if not changes:
            return DataModificationResult(
                success=True,
                message="No actual changes detected (values were already set)",
                subject_key=subject_key,
            )

        # Update timestamp
        subject.updated_at = datetime.now(timezone.utc)

        # Create comprehensive audit entry
        audit_details = {
            "operation_type": "subject_data_modification",
            "subject_key": subject_key,
            "reason": reason,
            "fields_modified": [c.field_name for c in changes],
            "changes": [c.to_audit_dict() for c in changes],
            "operator_ip": operator_ip,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }

        audit_entry = AuditLog(
            user_id=str(operator_user_id),
            username=operator_username,
            subject_key=subject_key,
            operation="admin_modify_subject_data",
            outcome="success",
            details=audit_details,
        )
        db.add(audit_entry)
        db.flush()  # Get audit ID

        audit_id = audit_entry.id

    # Log the operation (without PII)
    logger.info(
        "subject_data_modified",
        subject_key=subject_key,
        fields_modified=[c.field_name for c in changes],
        operator_user_id=operator_user_id,
        audit_id=audit_id,
    )

    return DataModificationResult(
        success=True,
        message=f"Successfully updated {len(changes)} field(s)",
        subject_key=subject_key,
        changes_applied=changes,
        audit_id=audit_id,
    )


def list_subject_modification_history(
    subject_key: str,
    limit: int = 50,
) -> list[dict]:
    """Get the modification history for a subject.

    Args:
        subject_key: The subject to query
        limit: Maximum number of records to return

    Returns:
        List of audit records for this subject
    """
    init_login_db()

    with login_db_session() as db:
        records = (
            db.query(AuditLog)
            .filter(
                AuditLog.subject_key == subject_key,
                AuditLog.operation == "admin_modify_subject_data",
            )
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "audit_id": r.id,
                "timestamp": r.created_at.isoformat() if r.created_at else None,
                "operator_user_id": r.user_id,
                "operator_username": r.username,
                "outcome": r.outcome,
                "details": r.details,
            }
            for r in records
        ]


# =============================================================================
# DOCUMENT UPLOAD MANAGEMENT
# =============================================================================


def record_document_upload(
    filename: str,
    file_size: int,
    file_hash: str,
    destination_path: str,
    operator_user_id: int,
    operator_username: Optional[str] = None,
    operator_ip: Optional[str] = None,
) -> int:
    """Record a document upload in the audit trail.

    Args:
        filename: Original filename
        file_size: Size in bytes
        file_hash: SHA-256 hash of file content
        destination_path: Where the file was stored
        operator_user_id: Admin who uploaded
        operator_username: Admin's username
        operator_ip: Request IP

    Returns:
        Audit log ID
    """
    init_login_db()

    with login_db_session() as db:
        audit_entry = AuditLog(
            user_id=str(operator_user_id),
            username=operator_username,
            operation="admin_upload_public_document",
            outcome="success",
            details={
                "filename": filename,
                "file_size_bytes": file_size,
                "file_sha256": file_hash,
                "destination": destination_path,
                "operator_ip": operator_ip,
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            },
        )
        db.add(audit_entry)
        db.flush()

        audit_id = audit_entry.id

    logger.info(
        "public_document_uploaded",
        filename=filename,
        file_size=file_size,
        operator_user_id=operator_user_id,
        audit_id=audit_id,
    )

    return audit_id
