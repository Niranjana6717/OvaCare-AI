"""Symptom CRUD + trend aggregation. Never converts symptoms into a diagnosis
(requirement #23) — `get_symptom_trends` returns raw frequency/severity
series only; any interpretation happens in the UI's neutral insights copy."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.symptom import Symptom


def list_symptoms(db: Session, user_id: str, since: date | None = None) -> list[Symptom]:
    stmt = select(Symptom).where(Symptom.user_id == user_id)
    if since:
        stmt = stmt.where(Symptom.logged_date >= since)
    stmt = stmt.order_by(Symptom.logged_date.desc())
    return list(db.scalars(stmt).all())


def get_symptom_trends(db: Session, user_id: str, window_days: int = 90) -> dict:
    since = date.today() - timedelta(days=window_days)
    symptoms = list_symptoms(db, user_id, since=since)

    frequency: dict[str, int] = defaultdict(int)
    average_severity: dict[str, list[int]] = defaultdict(list)

    for symptom in symptoms:
        key = symptom.symptom_type.value
        frequency[key] += 1
        average_severity[key].append(symptom.severity)

    return {
        "window_days": window_days,
        "frequency": dict(frequency),
        "average_severity": {
            key: round(sum(values) / len(values), 1) for key, values in average_severity.items()
        },
        "total_logged": len(symptoms),
    }
