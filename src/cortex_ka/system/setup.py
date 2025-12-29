"""First-run setup module for Cortex.

This module handles the initial configuration of a fresh Cortex installation:

1. Creating the first admin user
2. Initializing the document collection
3. Configuring basic system settings

Security considerations:
- Setup endpoints are ONLY available when no admin exists (first_run=True)
- Once an admin is created, these endpoints return 403 Forbidden
- All setup actions are logged to the audit trail
- Passwords are properly hashed using bcrypt
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from cortex_ka.auth.db import init_login_db, login_db_session
from cortex_ka.auth.models import AuditLog, User
from cortex_ka.auth.passwords import hash_password
from cortex_ka.logging import logger
from cortex_ka.system.status import get_system_status

# Password validation rules for security
PASSWORD_MIN_LENGTH = 8
PASSWORD_REGEX = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&_\-])[A-Za-z\d@$!%*?&_\-]{8,}$")


@dataclass
class SetupResult:
    """Result of a setup operation."""

    success: bool
    message: str
    user_id: Optional[int] = None
    username: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "message": self.message,
            "user_id": self.user_id,
            "username": self.username,
        }


class SetupError(Exception):
    """Exception raised when setup operations fail."""

    pass


class SetupNotAllowedError(SetupError):
    """Exception raised when setup is attempted but system is already configured."""

    pass


class ValidationError(SetupError):
    """Exception raised when input validation fails."""

    pass


def validate_username(username: str) -> str:
    """Validate and normalize a username.

    Rules:
    - 3-64 characters
    - Alphanumeric, dots, underscores, hyphens allowed
    - Must start with alphanumeric
    - Lowercase normalized

    Returns:
        Normalized username

    Raises:
        ValidationError: If validation fails
    """
    username = username.strip().lower()

    if not username:
        raise ValidationError("Username is required")

    if len(username) < 3:
        raise ValidationError("Username must be at least 3 characters")

    if len(username) > 64:
        raise ValidationError("Username must be at most 64 characters")

    if not re.match(r"^[a-z0-9][a-z0-9._-]*$", username):
        raise ValidationError(
            "Username must start with alphanumeric and contain only " "letters, numbers, dots, underscores, and hyphens"
        )

    return username


def validate_password(password: str) -> None:
    """Validate password strength.

    Rules:
    - At least 8 characters
    - At least one lowercase letter
    - At least one uppercase letter
    - At least one digit
    - At least one special character (@$!%*?&_-)

    Raises:
        ValidationError: If validation fails
    """
    if not password:
        raise ValidationError("Password is required")

    if len(password) < PASSWORD_MIN_LENGTH:
        raise ValidationError(f"Password must be at least {PASSWORD_MIN_LENGTH} characters")

    if not PASSWORD_REGEX.match(password):
        raise ValidationError(
            "Password must contain at least one lowercase letter, "
            "one uppercase letter, one digit, and one special character (@$!%*?&_-)"
        )


def validate_display_name(display_name: str) -> str:
    """Validate and normalize a display name.

    Rules:
    - 1-128 characters
    - Trimmed

    Returns:
        Normalized display name

    Raises:
        ValidationError: If validation fails
    """
    display_name = display_name.strip()

    if not display_name:
        raise ValidationError("Display name is required")

    if len(display_name) > 128:
        raise ValidationError("Display name must be at most 128 characters")

    return display_name


def is_setup_allowed() -> bool:
    """Check if setup operations are allowed.

    Setup is only allowed when no admin user exists (first run).

    Returns:
        True if setup is allowed, False otherwise.
    """
    status = get_system_status(check_llm=False, include_errors=False)
    return status.first_run


def create_initial_admin(
    username: str,
    password: str,
    display_name: Optional[str] = None,
) -> SetupResult:
    """Create the first admin user during initial setup.

    This function:
    1. Validates that setup is allowed (no existing admin)
    2. Validates username and password
    3. Creates the admin user with full privileges
    4. Logs the action to the audit trail

    Args:
        username: Admin username (will be normalized to lowercase)
        password: Admin password (must meet complexity requirements)
        display_name: Optional display name (defaults to username)

    Returns:
        SetupResult with success status and details

    Raises:
        SetupNotAllowedError: If an admin already exists
        ValidationError: If input validation fails
    """
    # Check if setup is allowed
    if not is_setup_allowed():
        raise SetupNotAllowedError(
            "Setup is not allowed: an admin user already exists. " "Use the admin panel to create additional users."
        )

    # Validate inputs
    username = validate_username(username)
    validate_password(password)
    display_name = validate_display_name(display_name or username)

    # Ensure database is initialized
    init_login_db()

    with login_db_session() as db:
        # Double-check no admin exists (race condition protection)
        existing_admin = (
            db.query(User)
            .filter(
                User.user_type == "employee",
                User.role == "admin",
                User.status == "active",
            )
            .first()
        )

        if existing_admin:
            raise SetupNotAllowedError("An admin user was created while processing this request.")

        # Check username uniqueness
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            raise ValidationError(f"Username '{username}' is already taken")

        # Create the admin user
        admin = User(
            username=username,
            password_hash=hash_password(password),
            user_type="employee",
            role="admin",
            dlp_level="privileged",
            status="active",
            can_access_all_subjects=True,
        )
        db.add(admin)
        db.flush()  # Get the assigned ID

        user_id = admin.id

        # Audit log
        audit_entry = AuditLog(
            user_id=str(user_id),
            username=username,
            operation="setup_create_admin",
            outcome="success",
            details={
                "display_name": display_name,
                "first_admin": True,
            },
        )
        db.add(audit_entry)

    logger.info(
        "setup_admin_created",
        username=username,
        user_id=user_id,
    )

    return SetupResult(
        success=True,
        message=f"Admin user '{username}' created successfully",
        user_id=user_id,
        username=username,
    )


def create_user(
    username: str,
    password: str,
    user_type: str,
    role: str,
    display_name: Optional[str] = None,
    dlp_level: str = "standard",
    can_access_all_subjects: bool = False,
    subject_ids: Optional[list[str]] = None,
    created_by_user_id: Optional[int] = None,
    # Personal data fields for Subject record
    full_name: Optional[str] = None,
    document_id: Optional[str] = None,
    tax_id: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
) -> SetupResult:
    """Create a new user (admin function, not setup).

    This is a general user creation function for use by admins after
    initial setup is complete.

    Args:
        username: User's username
        password: User's password
        user_type: "customer" or "employee"
        role: Role name (e.g., "customer", "support", "admin")
        display_name: Optional display name
        dlp_level: "standard" or "privileged"
        can_access_all_subjects: Whether user can access all subjects
        subject_ids: List of subject IDs to link (for customers)
        created_by_user_id: ID of admin creating this user
        full_name: Full legal name (stored in Subject)
        document_id: National ID (DNI, SSN, etc.)
        tax_id: Tax ID (CUIL/CUIT, NIF, EIN, etc.)
        email: Contact email
        phone: Phone number

    Returns:
        SetupResult with success status

    Raises:
        ValidationError: If input validation fails
    """
    import re

    from cortex_ka.auth.models import Subject, UserSubject

    # Validate inputs
    username = validate_username(username)
    validate_password(password)
    display_name = validate_display_name(display_name or username)

    if user_type not in ("customer", "employee"):
        raise ValidationError("user_type must be 'customer' or 'employee'")

    if dlp_level not in ("standard", "privileged"):
        raise ValidationError("dlp_level must be 'standard' or 'privileged'")

    # Validate email format if provided
    if email:
        email = email.strip().lower()
        email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_regex, email):
            raise ValidationError("Invalid email format")

    # Normalize phone (strip spaces, dashes)
    if phone:
        phone = re.sub(r"[\s\-\(\)]", "", phone.strip())

    # Normalize document_id and tax_id (uppercase, strip)
    if document_id:
        document_id = document_id.strip().upper()
    if tax_id:
        tax_id = tax_id.strip().upper().replace("-", "")

    init_login_db()

    with login_db_session() as db:
        # Check username uniqueness
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            raise ValidationError(f"Username '{username}' is already taken")

        # Create user
        user = User(
            username=username,
            password_hash=hash_password(password),
            user_type=user_type,
            role=role,
            dlp_level=dlp_level,
            status="active",
            can_access_all_subjects=can_access_all_subjects,
        )
        db.add(user)
        db.flush()

        user_id = user.id

        # =======================================================================
        # AUTO-GENERATE SUBJECT FOR CUSTOMERS
        # =======================================================================
        # For customers, we always create a Subject automatically.
        # Each customer gets their own unique Subject (1:1 relationship).
        # Employees with can_access_all_subjects don't need a Subject.
        # =======================================================================

        if user_type == "customer":
            # Generate unique subject_key for customer
            # Format: CLI-{user_id} ensures uniqueness
            auto_subject_key = f"CLI-{user_id:05d}"

            # Check if this subject_key already exists (shouldn't happen)
            existing_subject = db.query(Subject).filter(Subject.subject_key == auto_subject_key).first()

            if existing_subject:
                # Update existing subject with personal data
                subject = existing_subject
                if full_name:
                    subject.full_name = full_name
                    subject.display_name = full_name
                if document_id:
                    subject.document_id = document_id
                if tax_id:
                    subject.tax_id = tax_id
                if email:
                    subject.email = email
                if phone:
                    subject.phone = phone
            else:
                # Create new subject for this customer
                subject = Subject(
                    subject_key=auto_subject_key,
                    subject_type="person",
                    display_name=full_name or display_name or username,
                    status="active",
                    full_name=full_name,
                    document_id=document_id,
                    tax_id=tax_id,
                    email=email,
                    phone=phone,
                )
                db.add(subject)
                db.flush()

            # Link user to their subject
            link = UserSubject(
                user_id=user_id,
                subject_pk=subject.id,
                subject_id=auto_subject_key,
            )
            db.add(link)

        elif subject_ids:
            # For employees with specific subject access (not common)
            for subject_id in subject_ids:
                subject = db.query(Subject).filter(Subject.subject_key == subject_id).first()

                if subject:
                    # Update subject with personal data if provided
                    if full_name:
                        subject.full_name = full_name
                        subject.display_name = full_name
                    if document_id:
                        subject.document_id = document_id
                    if tax_id:
                        subject.tax_id = tax_id
                    if email:
                        subject.email = email
                    if phone:
                        subject.phone = phone
                else:
                    # Create new subject with personal data
                    subject = Subject(
                        subject_key=subject_id,
                        subject_type="employee",
                        display_name=full_name or display_name or subject_id,
                        status="active",
                        full_name=full_name,
                        document_id=document_id,
                        tax_id=tax_id,
                        email=email,
                        phone=phone,
                    )
                    db.add(subject)
                    db.flush()

                link = UserSubject(
                    user_id=user_id,
                    subject_pk=subject.id if subject else None,
                    subject_id=subject_id,
                )
                db.add(link)

        # Determine the subject_key for logging (auto-generated for customers)
        linked_subject_key = f"CLI-{user_id:05d}" if user_type == "customer" else None

        # Audit log (do NOT log PII in audit - only operation metadata)
        audit_entry = AuditLog(
            user_id=str(created_by_user_id) if created_by_user_id else None,
            username=None,
            subject_key=linked_subject_key,
            operation="admin_create_user",
            outcome="success",
            details={
                "created_username": username,
                "created_user_id": user_id,
                "user_type": user_type,
                "role": role,
                "subject_key": linked_subject_key,
                "has_personal_data": bool(full_name or document_id or email),
            },
        )
        db.add(audit_entry)

    logger.info(
        "user_created",
        username=username,
        user_id=user_id,
        user_type=user_type,
        role=role,
        subject_key=linked_subject_key,
        created_by=created_by_user_id,
    )

    return SetupResult(
        success=True,
        message=f"User '{username}' created successfully",
        user_id=user_id,
        username=username,
    )


@dataclass
class UserInfo:
    """User information for listing/display."""

    id: int
    username: str
    user_type: str
    role: str
    dlp_level: str
    status: str
    can_access_all_subjects: bool
    subject_ids: list[str]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "user_type": self.user_type,
            "role": self.role,
            "dlp_level": self.dlp_level,
            "status": self.status,
            "can_access_all_subjects": self.can_access_all_subjects,
            "subject_ids": self.subject_ids,
        }


def list_users(
    include_inactive: bool = False,
    user_type_filter: Optional[str] = None,
) -> list[UserInfo]:
    """List all users in the system.

    Args:
        include_inactive: If True, include inactive/deleted users
        user_type_filter: Optional filter by user_type ("customer" or "employee")

    Returns:
        List of UserInfo objects
    """
    from cortex_ka.auth.models import UserSubject

    init_login_db()

    with login_db_session() as db:
        query = db.query(User)

        if not include_inactive:
            query = query.filter(User.status == "active")

        if user_type_filter:
            query = query.filter(User.user_type == user_type_filter)

        query = query.order_by(User.id)
        users = query.all()

        result = []
        for u in users:
            # Get subject IDs
            subject_links = db.query(UserSubject).filter(UserSubject.user_id == u.id).all()
            subject_ids = [link.subject_id for link in subject_links if link.subject_id]

            result.append(
                UserInfo(
                    id=u.id,
                    username=u.username,
                    user_type=u.user_type,
                    role=u.role,
                    dlp_level=u.dlp_level,
                    status=u.status,
                    can_access_all_subjects=u.can_access_all_subjects,
                    subject_ids=subject_ids,
                )
            )

        return result


def get_user(user_id: int) -> Optional[UserInfo]:
    """Get a single user by ID.

    Args:
        user_id: The user's ID

    Returns:
        UserInfo if found, None otherwise
    """
    from cortex_ka.auth.models import UserSubject

    init_login_db()

    with login_db_session() as db:
        user = db.query(User).filter(User.id == user_id).first()

        if not user:
            return None

        # Get subject IDs
        subject_links = db.query(UserSubject).filter(UserSubject.user_id == user.id).all()
        subject_ids = [link.subject_id for link in subject_links if link.subject_id]

        return UserInfo(
            id=user.id,
            username=user.username,
            user_type=user.user_type,
            role=user.role,
            dlp_level=user.dlp_level,
            status=user.status,
            can_access_all_subjects=user.can_access_all_subjects,
            subject_ids=subject_ids,
        )


def update_user(
    user_id: int,
    role: Optional[str] = None,
    dlp_level: Optional[str] = None,
    status: Optional[str] = None,
    can_access_all_subjects: Optional[bool] = None,
    new_password: Optional[str] = None,
    updated_by_user_id: Optional[int] = None,
) -> SetupResult:
    """Update an existing user.

    Only admins can update users. Cannot change username or user_type.

    Args:
        user_id: ID of user to update
        role: New role (optional)
        dlp_level: New DLP level (optional)
        status: New status - "active" or "inactive" (optional)
        can_access_all_subjects: New access setting (optional)
        new_password: New password if changing (optional)
        updated_by_user_id: ID of admin making the change

    Returns:
        SetupResult with success status

    Raises:
        ValidationError: If validation fails
    """
    init_login_db()

    with login_db_session() as db:
        user = db.query(User).filter(User.id == user_id).first()

        if not user:
            raise ValidationError(f"User with ID {user_id} not found")

        # Save username before any changes (for return value)
        username = user.username
        changes = {}

        if role is not None:
            user.role = role
            changes["role"] = role

        if dlp_level is not None:
            if dlp_level not in ("standard", "privileged"):
                raise ValidationError("dlp_level must be 'standard' or 'privileged'")
            user.dlp_level = dlp_level
            changes["dlp_level"] = dlp_level

        if status is not None:
            if status not in ("active", "inactive"):
                raise ValidationError("status must be 'active' or 'inactive'")
            user.status = status
            changes["status"] = status

        if can_access_all_subjects is not None:
            user.can_access_all_subjects = can_access_all_subjects
            changes["can_access_all_subjects"] = can_access_all_subjects

        if new_password is not None:
            validate_password(new_password)
            user.password_hash = hash_password(new_password)
            changes["password"] = "***changed***"

        if not changes:
            return SetupResult(
                success=True,
                message="No changes to apply",
                user_id=user_id,
                username=username,
            )

        # Audit log
        audit_entry = AuditLog(
            user_id=str(updated_by_user_id) if updated_by_user_id else None,
            username=None,
            operation="admin_update_user",
            outcome="success",
            details={
                "updated_user_id": user_id,
                "updated_username": username,
                "changes": changes,
            },
        )
        db.add(audit_entry)

    logger.info(
        "user_updated",
        user_id=user_id,
        username=username,
        changes=list(changes.keys()),
        updated_by=updated_by_user_id,
    )

    return SetupResult(
        success=True,
        message=f"User '{username}' updated successfully",
        user_id=user_id,
        username=username,
    )


def delete_user(
    user_id: int,
    deleted_by_user_id: Optional[int] = None,
    hard_delete: bool = False,
) -> SetupResult:
    """Delete or deactivate a user.

    By default, this soft-deletes (sets status='inactive').
    Set hard_delete=True to permanently remove (not recommended).

    Cannot delete the last admin user.

    Args:
        user_id: ID of user to delete
        deleted_by_user_id: ID of admin making the deletion
        hard_delete: If True, permanently delete. If False, deactivate.

    Returns:
        SetupResult with success status

    Raises:
        ValidationError: If validation fails (e.g., last admin)
    """
    init_login_db()

    with login_db_session() as db:
        user = db.query(User).filter(User.id == user_id).first()

        if not user:
            raise ValidationError(f"User with ID {user_id} not found")

        # Prevent deleting the last admin
        if user.user_type == "employee" and user.role == "admin":
            admin_count = (
                db.query(User)
                .filter(
                    User.user_type == "employee",
                    User.role == "admin",
                    User.status == "active",
                    User.id != user_id,
                )
                .count()
            )

            if admin_count == 0:
                raise ValidationError("Cannot delete the last admin user. Create another admin first.")

        username = user.username

        if hard_delete:
            db.delete(user)
            operation = "admin_hard_delete_user"
            message = f"User '{username}' permanently deleted"
        else:
            user.status = "inactive"
            operation = "admin_deactivate_user"
            message = f"User '{username}' deactivated"

        # Audit log
        audit_entry = AuditLog(
            user_id=str(deleted_by_user_id) if deleted_by_user_id else None,
            username=None,
            operation=operation,
            outcome="success",
            details={
                "deleted_user_id": user_id,
                "deleted_username": username,
                "hard_delete": hard_delete,
            },
        )
        db.add(audit_entry)

    logger.info(
        "user_deleted",
        user_id=user_id,
        username=username,
        hard_delete=hard_delete,
        deleted_by=deleted_by_user_id,
    )

    return SetupResult(
        success=True,
        message=message,
        user_id=user_id,
        username=username,
    )
