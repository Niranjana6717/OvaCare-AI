"""Notification models: user preferences + a log of what was (or would be) sent."""
from __future__ import annotations

import enum
from datetime import datetime, time
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base
from app.database.models.base_mixins import TimestampMixin, generate_uuid


class NotificationType(str, enum.Enum):
    UPCOMING_PERIOD = "upcoming_period"
    PERIOD_LOGGING = "period_logging"
    CYCLE_TRACKING = "cycle_tracking"
    SYMPTOM_LOGGING = "symptom_logging"


class NotificationPreference(Base, TimestampMixin):
    __tablename__ = "notification_preferences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), unique=True, nullable=False)

    period_reminders_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    days_before_period: Mapped[int] = mapped_column(Integer, default=2, nullable=False)  # one of 1,2,3,5
    notification_time: Mapped[time] = mapped_column(Time, default=time(8, 0), nullable=False)

    cycle_reminders_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    symptom_reminders_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # True => lock-screen / preview text is generic ("You have an OvaCare
    # reminder."). False => full detail shown. Defaults to private per
    # requirement #21 — health information must not be exposed by default.
    privacy_mode: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)

    user: Mapped["User"] = relationship(back_populates="notification_preference")


class Notification(Base, TimestampMixin):
    """
    A record of a notification the system scheduled/generated. In this
    codebase, delivery to a real push provider (FCM/APNs) is not wired up
    (no provider credentials exist in this environment — see .env.example),
    so `delivered_at` stays null and `delivery_status` stays "logged_only"
    until a real provider is integrated. The scheduling and content logic
    upstream of delivery is fully implemented and tested.
    """

    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)

    notification_type: Mapped[NotificationType] = mapped_column(Enum(NotificationType), nullable=False)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    full_text: Mapped[str] = mapped_column(Text, nullable=False)
    private_text: Mapped[str] = mapped_column(Text, nullable=False, default="You have an OvaCare reminder.")

    delivery_status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
