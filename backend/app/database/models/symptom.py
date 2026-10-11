"""Symptom tracking model."""
from __future__ import annotations

import enum
from datetime import date
from typing import Optional

from sqlalchemy import Date, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base
from app.database.models.base_mixins import TimestampMixin, generate_uuid


class SymptomType(str, enum.Enum):
    ACNE = "acne"
    HAIR_GROWTH_CHANGES = "hair_growth_changes"
    HAIR_LOSS = "hair_loss"
    PELVIC_DISCOMFORT = "pelvic_discomfort"
    FATIGUE = "fatigue"
    MOOD_CHANGES = "mood_changes"
    OTHER = "other"


class Symptom(Base, TimestampMixin):
    __tablename__ = "symptoms"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)

    symptom_type: Mapped[SymptomType] = mapped_column(Enum(SymptomType), nullable=False)
    custom_label: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)  # used when symptom_type == OTHER
    severity: Mapped[int] = mapped_column(Integer, nullable=False)  # 1 (mild) .. 5 (severe)
    logged_date: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(back_populates="symptoms")
