"""
Pure cycle-calculation math — no database, no web framework, no third-party
dependency beyond the standard library. `cycle_service.py` is a thin
SQLAlchemy-facing wrapper around this module.

This split exists so the actual arithmetic behind requirement #17 (never
assume a fixed 28-day cycle; never fabricate history; degrade honestly when
data is insufficient) can be executed and unit-tested with nothing but
`python3 -m unittest` — which matters a great deal in an environment where
SQLAlchemy itself may not be installable (see docs/deployment.md,
"Environment constraints encountered in the build session").
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import NamedTuple, Optional, Sequence

# A cycle's length is only meaningful once we have at least two period start
# dates to measure the gap between. An *estimate* additionally needs enough
# such gaps to average over, or a single unusual cycle would dominate it.
MIN_CYCLES_FOR_AVERAGE = 2
MIN_CYCLES_FOR_ESTIMATE = 2

# Purely a UI-messaging threshold ("your cycles have varied") — NOT a
# clinical inference boundary. Irregularity must never be mapped to a PCOS
# conclusion anywhere in this codebase (requirement #18/#83).
HIGH_VARIABILITY_STDEV_DAYS = 7.0

# How many most-recent cycles feed the rolling average/variability figures.
TREND_WINDOW = 6


class CycleEntry(NamedTuple):
    """Minimal, ORM-agnostic representation of one logged period, already
    sorted by start_date ascending by the caller."""

    start_date: date
    end_date: Optional[date]


@dataclass(frozen=True)
class DerivedFields:
    cycle_length_days: Optional[int]
    period_duration_days: Optional[int]


@dataclass
class CycleSummary:
    sufficient_data: bool
    message: Optional[str] = None
    average_cycle_length_days: Optional[float] = None
    average_period_duration_days: Optional[float] = None
    cycle_variability_stdev_days: Optional[float] = None
    is_high_variability: bool = False


@dataclass
class NextPeriodEstimate:
    sufficient_data: bool
    message: Optional[str] = None
    estimated_start_date: Optional[date] = None
    based_on_cycle_count: int = 0


def compute_derived_fields(entries: Sequence[CycleEntry]) -> list[DerivedFields]:
    """For each entry (assumed sorted ascending by start_date), compute the
    gap to the PREVIOUS entry's start_date, and the period's own duration.
    Returned list is the same length/order as `entries`."""
    results: list[DerivedFields] = []
    previous_start: Optional[date] = None
    for entry in entries:
        cycle_length = (entry.start_date - previous_start).days if previous_start else None
        period_duration = (entry.end_date - entry.start_date).days + 1 if entry.end_date else None
        results.append(DerivedFields(cycle_length_days=cycle_length, period_duration_days=period_duration))
        previous_start = entry.start_date
    return results


def summarize(entries: Sequence[CycleEntry], insufficient_data_message: str) -> CycleSummary:
    derived = compute_derived_fields(entries)
    lengths = [d.cycle_length_days for d in derived if d.cycle_length_days is not None]
    durations = [d.period_duration_days for d in derived if d.period_duration_days is not None]

    if len(lengths) < MIN_CYCLES_FOR_AVERAGE:
        return CycleSummary(sufficient_data=False, message=insufficient_data_message)

    recent_lengths = lengths[-TREND_WINDOW:]
    recent_durations = durations[-TREND_WINDOW:] if durations else []
    variability = statistics.pstdev(recent_lengths) if len(recent_lengths) >= 2 else 0.0

    return CycleSummary(
        sufficient_data=True,
        average_cycle_length_days=round(statistics.mean(recent_lengths), 1),
        average_period_duration_days=(
            round(statistics.mean(recent_durations), 1) if recent_durations else None
        ),
        cycle_variability_stdev_days=round(variability, 1),
        is_high_variability=variability >= HIGH_VARIABILITY_STDEV_DAYS,
    )


def estimate_next_period(entries: Sequence[CycleEntry], insufficient_data_message: str) -> NextPeriodEstimate:
    if not entries:
        return NextPeriodEstimate(sufficient_data=False, message=insufficient_data_message)

    derived = compute_derived_fields(entries)
    lengths = [d.cycle_length_days for d in derived if d.cycle_length_days is not None]

    if len(lengths) < MIN_CYCLES_FOR_ESTIMATE:
        return NextPeriodEstimate(sufficient_data=False, message=insufficient_data_message)

    recent_lengths = lengths[-TREND_WINDOW:]
    average_length = statistics.mean(recent_lengths)
    last_start = entries[-1].start_date
    estimated_start = last_start + timedelta(days=round(average_length))

    return NextPeriodEstimate(
        sufficient_data=True,
        estimated_start_date=estimated_start,
        based_on_cycle_count=len(recent_lengths),
    )
