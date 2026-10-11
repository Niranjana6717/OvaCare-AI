"""Menstrual cycle tracking model."""
from __future__ import annotations

import enum
from datetime import date
from typing import Optional

from sqlalchemy import Date, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base
from app.database.models.base_mixins import TimestampMixin, generate_uuid


class FlowLevel(str, enum.Enum):
    SPOTTING = "spotting"
    LIGHT = "light"
    MEDIUM = "medium"
    HEAVY = "heavy"


class CycleRecord(Base, TimestampMixin):
    """
    A single logged period. `cycle_length` is the number of days between this
    period's start date and the PREVIOUS period's start date — it is computed
    server-side (cycle_service), never entered directly by the user, so it
    can't drift from the source dates.
    """

    __tablename__ = "cycle_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)

    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    flow_level: Mapped[Optional[FlowLevel]] = mapped_column(Enum(FlowLevel), nullable=True)

    # Derived/cached fields — recomputed by cycle_service whenever a cycle in
    # this user's history is added, edited, or deleted. Never hand-set.
    cycle_length_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    period_duration_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(back_populates="cycle_records")
