"""JWT helpers for issuing and verifying access tokens.

Tokens carry just enough information to reconstruct the CurrentUserContext
without hitting the database on every request. For revocation or status
changes, callers can still consult the DB when needed.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import jwt

from .models import CurrentUserContext


def _jwt_secret() -> str:
    secret = os.getenv("CKA_JWT_SECRET")
    if not secret:
        # For security, we prefer failing fast rather than silently issuing
        # unsigned or trivially guessable tokens. In CI we can provide a
        # throwaway secret via environment.
        raise RuntimeError("CKA_JWT_SECRET is not configured")
    return secret


def _jwt_algorithm() -> str:
    return os.getenv("CKA_JWT_ALG", "HS256")


def _jwt_exp_delta() -> timedelta:
    minutes = int(os.getenv("CKA_JWT_EXP_MINUTES", "30"))
    return timedelta(minutes=minutes)


def issue_access_token(user: CurrentUserContext) -> str:
    """Issue a signed JWT for the given user context."""

    now = datetime.now(tz=timezone.utc)
    exp = now + _jwt_exp_delta()
    payload: Dict[str, Any] = {
        "sub": user.user_id,
        "username": user.username,
        "user_type": user.user_type,
        "role": user.role,
        "dlp_level": user.dlp_level,
        "subject_ids": user.subject_ids,
        "can_access_all_subjects": user.can_access_all_subjects,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "iss": os.getenv("CKA_JWT_ISS", "cortex-ka"),
        "aud": os.getenv("CKA_JWT_AUD", "cortex-client"),
    }
    token = jwt.encode(payload, _jwt_secret(), algorithm=_jwt_algorithm())
    # PyJWT returns str for HS* algorithms
    return token


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT, returning its payload.

    This enforces signature, expiry and audience/issuer checks. Any failure
    raises jwt.PyJWTError, which callers should translate to HTTP 401.
    """

    options = {"require": ["exp", "iat", "sub"]}
    payload = jwt.decode(
        token,
        _jwt_secret(),
        algorithms=[_jwt_algorithm()],
        audience=os.getenv("CKA_JWT_AUD", "cortex-client"),
        issuer=os.getenv("CKA_JWT_ISS", "cortex-ka"),
        options=options,
    )
    return payload


def current_user_from_claims(claims: Dict[str, Any]) -> CurrentUserContext:
    """Rebuild a CurrentUserContext from validated JWT claims."""

    subject_ids = claims.get("subject_ids") or []
    if not isinstance(subject_ids, list):
        subject_ids = []
    return CurrentUserContext(
        user_id=str(claims["sub"]),
        username=str(claims.get("username", "")),
        user_type=str(claims.get("user_type", "")),
        role=str(claims.get("role", "")),
        dlp_level=str(claims.get("dlp_level", "standard")),
        subject_ids=[str(s) for s in subject_ids],
        can_access_all_subjects=bool(claims.get("can_access_all_subjects", False)),
    )
