"""
Cycle calculation engine — SQLAlchemy-facing layer (requirement #17).

All the actual arithmetic lives in `cycle_math.py`, which has no database or
web-framework dependency and is unit-tested directly (see
backend/tests/test_cycle_math.py). This module's only job is fetching a
user's `CycleRecord` rows, handing their dates to `cycle_math`, and writing
the results back — it stays intentionally thin so a bug can't hide in a
mix of ORM plumbing and date arithmetic.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.cycle import CycleRecord
from app.services import cycle_math
from app.services.cycle_math import CycleEntry

# Re-exported for callers that only need the pure dataclasses/constants.
CycleSummaryData = cycle_math.CycleSummary
NextPeriodEstimateData = cycle_math.NextPeriodEstimate


def _get_history_ordered(db: Session, user_id: str) -> list[CycleRecord]:
    stmt = (
        select(CycleRecord)
        .where(CycleRecord.user_id == user_id)
        .order_by(CycleRecord.start_date.asc())
    )
    return list(db.scalars(stmt).all())


def recompute_derived_fields(db: Session, user_id: str) -> None:
    """Recompute `cycle_length_days` and `period_duration_days` for every
    CycleRecord belonging to `user_id`, from scratch, based on the raw
    start/end dates. Call this after any create/update/delete of a cycle
    record for that user, inside the same transaction."""
    records = _get_history_ordered(db, user_id)
    entries = [CycleEntry(start_date=r.start_date, end_date=r.end_date) for r in records]
    derived = cycle_math.compute_derived_fields(entries)

    for record, fields in zip(records, derived):
        record.cycle_length_days = fields.cycle_length_days
        record.period_duration_days = fields.period_duration_days
    db.flush()


def get_cycle_summary(db: Session, user_id: str):
    from app.safety.wording import INSUFFICIENT_CYCLE_HISTORY_TEXT  # local import: avoid cycle

    records = _get_history_ordered(db, user_id)
    entries = [CycleEntry(start_date=r.start_date, end_date=r.end_date) for r in records]
    summary = cycle_math.summarize(entries, INSUFFICIENT_CYCLE_HISTORY_TEXT)

    return summary, list(reversed(records))


def estimate_next_period(db: Session, user_id: str) -> cycle_math.NextPeriodEstimate:
    from app.safety.wording import INSUFFICIENT_CYCLE_HISTORY_TEXT  # local import: avoid cycle

    records = _get_history_ordered(db, user_id)
    entries = [CycleEntry(start_date=r.start_date, end_date=r.end_date) for r in records]
    return cycle_math.estimate_next_period(entries, INSUFFICIENT_CYCLE_HISTORY_TEXT)
