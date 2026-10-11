"""Revoked-token registry, so logout and refresh-rotation are real, not cosmetic.

JWTs are stateless by design, so "logout" only works if we track which
token IDs (jti) have been explicitly invalidated. This table is deliberately
tiny (just jti + expiry) — never holds token contents or user health data.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base
from app.database.models.base_mixins import utcnow


class RevokedToken(Base):
    __tablename__ = "revoked_tokens"

    jti: Mapped[str] = mapped_column(String(36), primary_key=True)
    revoked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
