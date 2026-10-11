"""User account and profile models."""
from __future__ import annotations

import enum
from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import Boolean, Date, DateTime, Enum, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base
from app.database.models.base_mixins import TimestampMixin, generate_uuid


class UserRole(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"
    CLINICAL_REVIEWER = "clinical_reviewer"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.USER, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    email_verification_token: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    password_reset_token: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    password_reset_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    profile: Mapped[Optional["Profile"]] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    cycle_records: Mapped[List["CycleRecord"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    symptoms: Mapped[List["Symptom"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    assessments: Mapped[List["Assessment"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    consent_records: Mapped[List["ConsentRecord"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    notification_preference: Mapped[Optional["NotificationPreference"]] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )


class Profile(Base, TimestampMixin):
    __tablename__ = "profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), unique=True, nullable=False)

    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    height_cm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    weight_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)

    user: Mapped["User"] = relationship(back_populates="profile")

    @property
    def bmi(self) -> Optional[float]:
        """
        BMI is informational only. Per product policy it must never be used as
        the central/primary PCOS prediction factor — see ml.preprocessing for
        the enforced feature-weighting rationale.
        """
        if not self.height_cm or not self.weight_kg or self.height_cm <= 0:
            return None
        height_m = self.height_cm / 100
        return round(self.weight_kg / (height_m**2), 1)
