"""Registration, login, token refresh, logout, and password reset flows."""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.token import RevokedToken
from app.database.models.user import Profile, User, UserRole
from app.security.jwt_handler import (
    InvalidTokenError,
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.security.password import hash_password, password_meets_policy, verify_password


class AuthError(Exception):
    """Base class for expected auth failures (mapped to HTTP responses by the API layer)."""


class EmailAlreadyRegisteredError(AuthError):
    pass


class InvalidCredentialsError(AuthError):
    pass


class WeakPasswordError(AuthError):
    pass


def register_user(db: Session, email: str, password: str) -> User:
    ok, reason = password_meets_policy(password)
    if not ok:
        raise WeakPasswordError(reason)

    existing = db.scalar(select(User).where(User.email == email.lower()))
    if existing is not None:
        raise EmailAlreadyRegisteredError("An account with this email already exists.")

    user = User(
        email=email.lower(),
        hashed_password=hash_password(password),
        role=UserRole.USER,
        email_verification_token=secrets.token_urlsafe(32),
    )
    db.add(user)
    db.flush()

    db.add(Profile(user_id=user.id))
    db.flush()
    return user


def authenticate_user(db: Session, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == email.lower()))
    if user is None or user.deleted_at is not None or not verify_password(password, user.hashed_password):
        raise InvalidCredentialsError("Incorrect email or password.")
    if not user.is_active:
        raise InvalidCredentialsError("This account has been deactivated.")
    return user


def issue_tokens(user: User) -> dict[str, str]:
    return {
        "access_token": create_access_token(user.id, user.role.value),
        "refresh_token": create_refresh_token(user.id, user.role.value),
        "token_type": "bearer",
    }


def refresh_access_token(db: Session, refresh_token: str) -> dict[str, str]:
    try:
        payload = decode_token(refresh_token, expected_type=TokenType.REFRESH)
    except InvalidTokenError as exc:
        raise InvalidCredentialsError("Refresh token is invalid or expired.") from exc

    if db.get(RevokedToken, payload.jti) is not None:
        raise InvalidCredentialsError("Refresh token has been revoked.")

    user = db.get(User, payload.sub)
    if user is None or not user.is_active or user.deleted_at is not None:
        raise InvalidCredentialsError("Account is no longer active.")

    # Rotate: revoke the used refresh token so it can't be replayed.
    db.add(RevokedToken(jti=payload.jti, expires_at=payload.exp))
    db.flush()

    return issue_tokens(user)


def logout(db: Session, access_token_jti: str, access_token_exp: datetime, refresh_token: str | None = None) -> None:
    db.add(RevokedToken(jti=access_token_jti, expires_at=access_token_exp))
    if refresh_token:
        try:
            payload = decode_token(refresh_token, expected_type=TokenType.REFRESH)
            db.add(RevokedToken(jti=payload.jti, expires_at=payload.exp))
        except InvalidTokenError:
            pass  # already invalid; nothing to revoke
    db.flush()


def delete_account(db: Session, user: User) -> None:
    """Soft-delete (requirement #86): sets deleted_at + deactivates rather
    than physically removing the row, so audit history referencing this
    user stays meaningful. `get_current_user` treats a deleted user as
    unauthenticatable, so this takes effect immediately for any token
    still outstanding, without needing to enumerate and revoke them."""
    user.deleted_at = datetime.now(timezone.utc)
    user.is_active = False
    db.flush()


def initiate_password_reset(db: Session, email: str) -> str | None:
    """Returns the reset token if the account exists, else None. The API
    layer must respond identically either way, to avoid leaking which
    emails are registered."""
    user = db.scalar(select(User).where(User.email == email.lower()))
    if user is None:
        return None
    token = secrets.token_urlsafe(32)
    user.password_reset_token = token
    user.password_reset_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    db.flush()
    return token


def complete_password_reset(db: Session, token: str, new_password: str) -> None:
    ok, reason = password_meets_policy(new_password)
    if not ok:
        raise WeakPasswordError(reason)

    user = db.scalar(select(User).where(User.password_reset_token == token))
    if (
        user is None
        or user.password_reset_expires_at is None
        or user.password_reset_expires_at < datetime.now(timezone.utc)
    ):
        raise InvalidCredentialsError("This password reset link is invalid or has expired.")

    user.hashed_password = hash_password(new_password)
    user.password_reset_token = None
    user.password_reset_expires_at = None
    db.flush()
