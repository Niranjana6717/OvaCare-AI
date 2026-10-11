"""PCOS screening assessment + prediction models.

Kept as two tables by design (see docs/architecture.md): `Assessment` is the
immutable record of what the user actually submitted; `Prediction` is the
immutable record of what the model returned for that submission, tagged with
every version identifier needed to reproduce it later. Splitting them means a
later model change can never silently rewrite what a past assessment's input
was, and a past prediction always keeps the model version that produced it
(see requirement #76 — prediction traceability, and #39 — model versioning).
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base
from app.database.models.base_mixins import TimestampMixin, generate_uuid, utcnow


class ScreeningOutcome(str, enum.Enum):
    """
    Deliberately not "POSITIVE" / "NEGATIVE" / "HAS_PCOS" — see
    docs/clinical_safety.md. These are screening *indications*, not
    diagnoses, and the wording layer (safety_service) enforces that no UI
    or API text ever collapses these into diagnostic language.
    """

    LOWER_INDICATION = "lower_indication"
    HIGHER_INDICATION = "higher_indication"
    INSUFFICIENT_DATA = "insufficient_data"  # model correctly declined to predict


class Assessment(Base, TimestampMixin):
    __tablename__ = "assessments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)

    # Raw, as-submitted questionnaire answers. Stored verbatim (after
    # validation) so a user can review exactly what they submitted, per
    # requirement #75 (user correction / review-before-submit).
    raw_responses: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Which optional sections the user chose to skip ("I don't have these
    # results") vs. which were never asked. Distinguishing "unknown" from
    # "not applicable" is required by #74 (missing data safety).
    unanswered_fields: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    user: Mapped["User"] = relationship(back_populates="assessments")
    prediction: Mapped[Optional["Prediction"]] = relationship(
        back_populates="assessment", uselist=False, cascade="all, delete-orphan"
    )


class Prediction(Base, TimestampMixin):
    __tablename__ = "predictions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    assessment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("assessments.id"), unique=True, nullable=False
    )

    # --- Full traceability (requirement #39 / #76) ---
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    feature_schema_version: Mapped[str] = mapped_column(String(50), nullable=False)
    preprocessing_version: Mapped[str] = mapped_column(String(50), nullable=False)
    threshold_version: Mapped[str] = mapped_column(String(50), nullable=False)

    outcome: Mapped[ScreeningOutcome] = mapped_column(Enum(ScreeningOutcome), nullable=False)

    # Calibrated probability. Nullable: when outcome is INSUFFICIENT_DATA,
    # there is deliberately no probability — see prediction_service.
    probability: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Explainability payload (top contributing factors, human-readable).
    # Never a bare "this proves X" claim — enforced in safety_service.
    explanation: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Why INSUFFICIENT_DATA was returned, if applicable (never fabricated).
    insufficient_data_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    assessment: Mapped["Assessment"] = relationship(back_populates="prediction")
