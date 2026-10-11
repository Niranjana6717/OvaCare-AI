from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.logging_config import log_structured
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
)
from app.middleware.rate_limit import limiter
from app.security.dependencies import get_current_user
from app.security.jwt_handler import InvalidTokenError, TokenType, decode_token
from app.services import auth_service
from app.services.audit_service import log_event

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger("ovacare.auth")


# Tighter than the app-wide default (RATE_LIMIT_PER_MINUTE, app/main.py) —
# these are the specific brute-force/enumeration-sensitive endpoints
# (security hardening review: rate limiting). slowapi keys by remote
# address (app/middleware/rate_limit.py), same as the app-wide limiter.
@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    try:
        user = auth_service.register_user(db, payload.email, payload.password)
    except auth_service.WeakPasswordError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except auth_service.EmailAlreadyRegisteredError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    tokens = auth_service.issue_tokens(user)
    log_event(db, action="user.register", actor_user_id=user.id, actor_role=user.role.value, ip_address=request.client.host if request.client else None)
    db.commit()
    return tokens


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    try:
        user = auth_service.authenticate_user(db, payload.email, payload.password)
    except auth_service.InvalidCredentialsError as exc:
        # Structured log only — never the email/password (see
        # app.logging_config's redaction, which also guards this). A
        # per-user audit_logs row isn't written here because a failed
        # login has no authenticated actor to attach one to; the
        # application log is the record of this event.
        log_structured(
            logger,
            logging.WARNING,
            "auth.login_failed",
            ip_address=request.client.host if request.client else None,
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    tokens = auth_service.issue_tokens(user)
    log_event(db, action="user.login", actor_user_id=user.id, actor_role=user.role.value, ip_address=request.client.host if request.client else None)
    db.commit()
    return tokens


@router.post("/logout", response_model=MessageResponse)
def logout(
    payload: LogoutRequest,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.removeprefix("Bearer ").strip()
    try:
        access_payload = decode_token(token, expected_type=TokenType.ACCESS)
    except InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    auth_service.logout(db, access_payload.jti, access_payload.exp, payload.refresh_token)
    log_event(db, action="user.logout", actor_user_id=user.id, actor_role=user.role.value)
    db.commit()
    return {"message": "Logged out."}


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    try:
        tokens = auth_service.refresh_access_token(db, payload.refresh_token)
    except auth_service.InvalidCredentialsError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    db.commit()
    return tokens


@router.post("/forgot-password", response_model=MessageResponse)
@limiter.limit("5/minute")
def forgot_password(payload: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)):
    # Always returns the same message, whether or not the email is
    # registered, to avoid confirming account existence to a caller.
    token = auth_service.initiate_password_reset(db, payload.email)
    if token:
        # In production this token is emailed via the configured SMTP
        # provider (see .env.example) — no provider is configured in this
        # environment, so the token is not actually delivered anywhere.
        # It is intentionally NOT returned in this response.
        pass
    db.commit()
    return {"message": "If an account with that email exists, password reset instructions have been sent."}


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    try:
        auth_service.complete_password_reset(db, payload.token, payload.new_password)
    except auth_service.WeakPasswordError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except auth_service.InvalidCredentialsError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    return {"message": "Password has been reset. You can now log in with your new password."}
