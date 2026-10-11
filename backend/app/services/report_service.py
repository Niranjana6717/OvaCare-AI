"""
Health summary report generation (requirement #35, #85, #87).

The caller (API layer) always passes an explicit `sections` set reflecting
what the USER selected to include/share — this module never defaults to
"everything." Every section that contains AI output is wrapped so it is
labeled distinctly from user-provided data (requirement #87).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.assessment import Assessment
from app.database.models.cycle import CycleRecord
from app.database.models.symptom import Symptom
from app.database.models.user import Profile
from app.services.prediction_service import build_result_payload

ALL_SECTIONS = {"profile", "cycle_history", "symptom_history", "screening_history"}


def generate_health_report(db: Session, user_id: str, sections: Iterable[str]) -> dict:
    sections = set(sections) & ALL_SECTIONS
    report: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_source_labels": {
            "user_provided_health_data": ["profile", "cycle_history", "symptom_history"],
            "ai_generated_screening_information": ["screening_history"],
        },
    }

    if "profile" in sections:
        profile = db.scalar(select(Profile).where(Profile.user_id == user_id))
        report["profile"] = (
            {
                "full_name": profile.full_name,
                "date_of_birth": profile.date_of_birth.isoformat() if profile.date_of_birth else None,
                "height_cm": profile.height_cm,
                "weight_kg": profile.weight_kg,
                "bmi": profile.bmi,
                "country": profile.country,
            }
            if profile
            else None
        )

    if "cycle_history" in sections:
        cycles = db.scalars(
            select(CycleRecord).where(CycleRecord.user_id == user_id).order_by(CycleRecord.start_date.desc())
        ).all()
        report["cycle_history"] = [
            {
                "start_date": c.start_date.isoformat(),
                "end_date": c.end_date.isoformat() if c.end_date else None,
                "cycle_length_days": c.cycle_length_days,
                "period_duration_days": c.period_duration_days,
                "flow_level": c.flow_level.value if c.flow_level else None,
            }
            for c in cycles
        ]

    if "symptom_history" in sections:
        symptoms = db.scalars(
            select(Symptom).where(Symptom.user_id == user_id).order_by(Symptom.logged_date.desc())
        ).all()
        report["symptom_history"] = [
            {
                "symptom_type": s.symptom_type.value,
                "custom_label": s.custom_label,
                "severity": s.severity,
                "logged_date": s.logged_date.isoformat(),
            }
            for s in symptoms
        ]

    if "screening_history" in sections:
        assessments = db.scalars(
            select(Assessment).where(Assessment.user_id == user_id).order_by(Assessment.submitted_at.desc())
        ).all()
        report["screening_history"] = [
            build_result_payload(a.prediction) for a in assessments if a.prediction is not None
        ]

    return report
