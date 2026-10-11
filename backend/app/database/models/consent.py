"""Informed consent records — auditable, versioned, never silently overwritten."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base
from app.database.models.base_mixins import TimestampMixin, generate_uuid


class ConsentType(str, enum.Enum):
    CORE_SERVICE = "core_service"
    HEALTH_DATA_PROCESSING = "health_data_processing"
    AI_SCREENING_ACKNOWLEDGEMENT = "ai_screening_acknowledgement"
    NOTIFICATION_PERMISSION = "notification_permission"
    ANALYTICS = "analytics"
    RESEARCH_MODEL_IMPROVEMENT = "research_model_improvement"


# Consents that are required to use core functionality — cannot be
# withdrawn without the associated feature stopping (see requirement #61).
REQUIRED_CONSENT_TYPES = {ConsentType.CORE_SERVICE, ConsentType.HEALTH_DATA_PROCESSING}

# Consents that are optional; withdrawing them must only disable the
# specific feature they gate, never the whole account (requirement #58/#61).
OPTIONAL_CONSENT_TYPES = {
    ConsentType.NOTIFICATION_PERMISSION,
    ConsentType.ANALYTICS,
    ConsentType.RESEARCH_MODEL_IMPROVEMENT,
}


class ConsentRecord(Base, TimestampMixin):
    """
    Each row is a single consent decision. A new decision (accept, or a
    version bump) creates a NEW row rather than mutating an old one, so the
    full consent history is always reconstructable (requirement #59/#60).
    """

    __tablename__ = "consent_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)

    consent_type: Mapped[ConsentType] = mapped_column(Enum(ConsentType), nullable=False)
    consent_version: Mapped[str] = mapped_column(String(20), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(20), nullable=False)
    app_version: Mapped[str] = mapped_column(String(20), nullable=False)

    accepted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    withdrawn_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="consent_records")
