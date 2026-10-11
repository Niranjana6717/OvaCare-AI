"""Audit log — records security/administrative EVENTS, never raw health data.

See docs/security.md: the `metadata_json` field is validated by
audit_service to reject any of the sensitive field names listed in
SENSITIVE_FIELD_DENYLIST before a row is ever written.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base
from app.database.models.base_mixins import generate_uuid, utcnow


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    actor_user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    actor_role: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)

    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    target_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    target_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
