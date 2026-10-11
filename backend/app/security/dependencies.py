"""FastAPI auth dependencies: current-user resolution and role-based access."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models.token import RevokedToken
from app.database.models.user import User, UserRole
from app.security.jwt_handler import InvalidTokenError, TokenType, decode_token

_bearer_scheme = HTTPBearer(auto_error=False)

_CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials.",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise _CREDENTIALS_EXCEPTION

    try:
        payload = decode_token(credentials.credentials, expected_type=TokenType.ACCESS)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if db.get(RevokedToken, payload.jti) is not None:
        raise _CREDENTIALS_EXCEPTION

    user = db.get(User, payload.sub)
    if user is None or not user.is_active or user.deleted_at is not None:
        raise _CREDENTIALS_EXCEPTION

    return user


def require_role(*allowed_roles: UserRole):
    """Dependency factory: `Depends(require_role(UserRole.ADMIN))`."""

    def _check(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action.",
            )
        return user

    return _check


require_admin = require_role(UserRole.ADMIN)
