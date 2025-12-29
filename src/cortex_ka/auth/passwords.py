"""Password hashing and verification utilities.

We use bcrypt for the demo as it is widely adopted and battle-tested. The
exact choice can be swapped later if needed without impacting callers.
"""

from __future__ import annotations

from passlib.context import CryptContext

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    return _pwd_ctx.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return _pwd_ctx.verify(plain_password, password_hash)
    except Exception:
        # Treat any internal error as verification failure; this is safer than
        # accidentally authenticating.
        return False
