"""
JWT access/refresh token creation and verification.

Uses PyJWT rather than python-jose: both are standard, actively-maintained
choices with near-identical APIs for this use case, and PyJWT is what was
actually installable/testable in this project's original development
sandbox (see docs/deployment.md) — this module's logic is therefore one of
the pieces of this backend that has real, executed test coverage
(backend/tests/test_jwt_handler.py), not just written-and-assumed code.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt as pyjwt
from pydantic import BaseModel

from app.config import get_settings


class TokenType(str, enum.Enum):
    ACCESS = "access"
    REFRESH = "refresh"


class TokenPayload(BaseModel):
    sub: str  # user id
    role: str
    type: TokenType
    jti: str
    exp: datetime
    iat: datetime


class InvalidTokenError(Exception):
    pass


def _create_token(user_id: str, role: str, token_type: TokenType, expires_delta: timedelta) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "role": role,
        "type": token_type.value,
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + expires_delta,
    }
    return pyjwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_access_token(user_id: str, role: str) -> str:
    settings = get_settings()
    return _create_token(
        user_id, role, TokenType.ACCESS, timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )


def create_refresh_token(user_id: str, role: str) -> str:
    settings = get_settings()
    return _create_token(
        user_id, role, TokenType.REFRESH, timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )


def decode_token(token: str, expected_type: Optional[TokenType] = None) -> TokenPayload:
    settings = get_settings()
    try:
        raw: dict[str, Any] = pyjwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except pyjwt.PyJWTError as exc:
        raise InvalidTokenError("Token is invalid or expired.") from exc

    try:
        payload = TokenPayload(**raw)
    except Exception as exc:  # malformed claims
        raise InvalidTokenError("Token payload is malformed.") from exc

    if expected_type and payload.type != expected_type:
        raise InvalidTokenError(f"Expected a {expected_type.value} token.")

    return payload
