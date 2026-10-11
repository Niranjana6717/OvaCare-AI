"""Registry of trained ML model artifacts and their lifecycle stage."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base
from app.database.models.base_mixins import TimestampMixin, generate_uuid


class ModelStage(str, enum.Enum):
    DEVELOPMENT = "development"
    VALIDATION = "validation"
    STAGING = "staging"
    PRODUCTION = "production"
    ARCHIVED = "archived"


class ModelVersion(Base, TimestampMixin):
    __tablename__ = "model_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)

    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    feature_schema_version: Mapped[str] = mapped_column(String(50), nullable=False)
    preprocessing_version: Mapped[str] = mapped_column(String(50), nullable=False)
    threshold_version: Mapped[str] = mapped_column(String(50), nullable=False)

    stage: Mapped[ModelStage] = mapped_column(Enum(ModelStage), default=ModelStage.DEVELOPMENT, nullable=False)

    artifact_path: Mapped[str] = mapped_column(String(500), nullable=False)
    training_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Full metric report (accuracy, precision, recall, F1, ROC-AUC, PR-AUC,
    # calibration, confusion matrix, subgroup results where available).
    evaluation_metrics: Mapped[dict] = mapped_column(JSON, nullable=False)

    dataset_reference: Mapped[str] = mapped_column(Text, nullable=False)
    # Nullable: a row registered from an OLDER artifact (saved before
    # train.py recorded these) legitimately has neither — never fabricated
    # to fill the gap. See migration 0002_add_model_calibration_fields.
    dataset_version: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    calibration_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    limitations: Mapped[str] = mapped_column(Text, nullable=False)

    # Clinical/content review tracking (requirement #69).
    review_status: Mapped[str] = mapped_column(String(30), default="pending_review", nullable=False)
    reviewed_by_role: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    promoted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    promoted_by_user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
