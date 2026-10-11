"""
ML monitoring + drift detection (admin-only).

Two kinds of signal, from two different places, deliberately:

  * Prediction DISTRIBUTION, missing-data rate, and model-version breakdown
    come straight from the `predictions`/`assessments` tables — real rows,
    recomputed fresh on every call, nothing cached or estimated.
  * Inference ERROR COUNT and LATENCY come from an in-process counter
    (`record_inference_outcome`, called from prediction_service.py around
    every real predictor.run_prediction() call), because those events don't
    have their own database table. This counter is **process-lifetime
    only** — it resets on restart and isn't shared across multiple worker
    processes. That's an honest limitation, not a hidden one: it's
    sufficient for a single-process deployment; a real production
    deployment should back this with a persistent metrics backend
    (Prometheus, CloudWatch, ...) instead. See docs/ml_documentation.md.

Drift detection compares the CURRENT window's higher/lower-indication split
against the loaded model's OWN recorded training-time positive rate (from
model_metadata.json's evaluation_metrics — never a second, independently
invented "expected" distribution) using the population stability index
(PSI). This only flags a number for a human to look at
(requirement: "Add drift detection where appropriate" +
"Do not automatically retrain or replace a production model because of
drift. Require controlled review before model promotion.") — nothing here
retrains, promotes, or demotes anything.
"""
from __future__ import annotations

import math
import threading
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

# ---------------------------------------------------------------------------
# In-process inference event counters — see module docstring.
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_inference_error_count = 0
_inference_latencies_ms: list[float] = []
_MAX_LATENCY_SAMPLES = 500  # bounded ring buffer — not unbounded memory growth


def record_inference_outcome(*, succeeded: bool, latency_ms: Optional[float] = None) -> None:
    """Called once per real predictor.run_prediction() invocation (see
    prediction_service.generate_prediction_for_assessment). `succeeded` is
    False only when run_prediction() itself raised — the three normal,
    documented outcomes (higher/lower_indication, insufficient_data) all
    count as succeeded=True, because insufficient_data is correct, designed
    behavior, not an error (requirement #54)."""
    global _inference_error_count
    with _lock:
        if not succeeded:
            _inference_error_count += 1
        if latency_ms is not None:
            _inference_latencies_ms.append(latency_ms)
            if len(_inference_latencies_ms) > _MAX_LATENCY_SAMPLES:
                _inference_latencies_ms.pop(0)


def get_inference_error_count() -> int:
    with _lock:
        return _inference_error_count


def get_latency_stats() -> dict[str, Any]:
    with _lock:
        samples = sorted(_inference_latencies_ms)
    if not samples:
        return {"p50_ms": None, "p95_ms": None, "n_samples": 0}

    def _pct(p: float) -> float:
        idx = min(len(samples) - 1, int(round(p * (len(samples) - 1))))
        return round(samples[idx], 2)

    return {"p50_ms": _pct(0.5), "p95_ms": _pct(0.95), "n_samples": len(samples)}


def reset_counters_for_tests() -> None:
    """Test-only helper — process-lifetime counters would otherwise leak
    state between test cases."""
    global _inference_error_count
    with _lock:
        _inference_error_count = 0
        _inference_latencies_ms.clear()


# ---------------------------------------------------------------------------
# Distribution / missing-data / drift — pure functions over already-fetched
# rows. No SQLAlchemy import anywhere above this line or below it in this
# module's "pure" half, so these are directly unit-testable without a
# database (see backend/tests/test_monitoring_service.py), same split as
# app/services/cycle_math.py.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PredictionRow:
    outcome: str
    model_version: str
    insufficient_data_reason: Optional[str] = None


def compute_prediction_distribution(rows: list[PredictionRow]) -> dict[str, Any]:
    total = len(rows)
    if total == 0:
        return {
            "total_predictions": 0,
            "outcome_distribution": {},
            "outcome_distribution_pct": {},
            "model_version_distribution": {},
            "missing_data_rate_pct": None,
            "model_unavailable_rate_pct": None,
        }

    outcome_counts = Counter(r.outcome for r in rows)
    version_counts = Counter(r.model_version for r in rows)

    # insufficient_data has two distinct causes in predictor.py — "the
    # submitted input was incomplete/out of range" vs. "no production model
    # is loaded at all" — worth reporting separately since they call for
    # different admin action. Matched against predictor.py's own static
    # templates (see its docstring) rather than a separate reason code,
    # since changing Prediction.insufficient_data_reason's contract is out
    # of scope here; a stable reason-code column would be a cleaner future
    # migration.
    missing_data_count = sum(
        1
        for r in rows
        if r.outcome == "insufficient_data"
        and r.insufficient_data_reason
        and "required information was" in r.insufficient_data_reason.lower()
    )
    model_unavailable_count = sum(
        1
        for r in rows
        if r.outcome == "insufficient_data"
        and r.insufficient_data_reason
        and "no validated production" in r.insufficient_data_reason.lower()
    )

    return {
        "total_predictions": total,
        "outcome_distribution": dict(outcome_counts),
        "outcome_distribution_pct": {k: round(v / total * 100, 1) for k, v in outcome_counts.items()},
        "model_version_distribution": dict(version_counts),
        "missing_data_rate_pct": round(missing_data_count / total * 100, 1),
        "model_unavailable_rate_pct": round(model_unavailable_count / total * 100, 1),
    }


def compute_assessment_missing_field_rate(unanswered_field_lists: list[list[str]]) -> Optional[float]:
    """Fraction of SUBMITTED assessments that left at least one optional
    field blank/"don't have this" — a broader, earlier signal than
    predictions' missing_data_rate_pct above (which only counts submissions
    where the gap was severe enough to block a prediction)."""
    if not unanswered_field_lists:
        return None
    with_gaps = sum(1 for fields in unanswered_field_lists if fields)
    return round(with_gaps / len(unanswered_field_lists) * 100, 1)


def compute_drift_signal(
    current_rows: list[PredictionRow], baseline_positive_rate: Optional[float]
) -> dict[str, Any]:
    """Population Stability Index between the current window's
    higher-indication rate (among DECIDED predictions only — insufficient_data
    rows carry no class signal) and the loaded model's own training-time
    positive rate. PSI > 0.25 is the conventional "notable, needs review"
    threshold. Returns `available: False` with a plain reason rather than a
    fabricated number whenever there isn't enough to compute one."""
    if baseline_positive_rate is None:
        return {
            "available": False,
            "reason": "No production model loaded, or its metadata has no recorded training-time class balance.",
        }

    decided = [r for r in current_rows if r.outcome in ("higher_indication", "lower_indication")]
    MIN_DECIDED_FOR_DRIFT = 20
    if len(decided) < MIN_DECIDED_FOR_DRIFT:
        return {
            "available": False,
            "reason": f"Only {len(decided)} decided prediction(s) in this window "
            f"(need at least {MIN_DECIDED_FOR_DRIFT}) for a meaningful drift signal.",
        }

    current_positive_rate = sum(1 for r in decided if r.outcome == "higher_indication") / len(decided)
    psi = _population_stability_index(baseline_positive_rate, current_positive_rate)
    return {
        "available": True,
        "baseline_positive_rate": round(baseline_positive_rate, 4),
        "current_positive_rate": round(current_positive_rate, 4),
        "n_decided_predictions": len(decided),
        "population_stability_index": round(psi, 4),
        "notable_drift": psi > 0.25,
        "note": "A notable PSI is a signal for admin review, not an automatic action — no model is retrained "
        "or replaced based on this value.",
    }


def _population_stability_index(baseline_rate: float, current_rate: float) -> float:
    eps = 1e-6
    b_pos, b_neg = max(baseline_rate, eps), max(1 - baseline_rate, eps)
    c_pos, c_neg = max(current_rate, eps), max(1 - current_rate, eps)
    return (c_pos - b_pos) * math.log(c_pos / b_pos) + (c_neg - b_neg) * math.log(c_neg / b_neg)


def _baseline_positive_rate_from_metadata(evaluation_metrics: Optional[dict]) -> Optional[float]:
    """The loaded model's OWN held-out test-set class balance
    (n_positive/n_samples, written by ml-platform/src/evaluate.py) — the
    only "expected distribution" this module will ever compare against."""
    if not evaluation_metrics:
        return None
    n_samples = evaluation_metrics.get("n_samples")
    n_positive = evaluation_metrics.get("n_positive")
    if not n_samples:
        return None
    return n_positive / n_samples


# ---------------------------------------------------------------------------
# DB-facing snapshot — thin wrapper, same split as cycle_service.py around
# cycle_math.py. Imports SQLAlchemy, so (like most of this backend) it is
# written-and-reviewed but not executable in this project's sandbox; the
# pure functions above ARE executed directly by the test suite.
# ---------------------------------------------------------------------------

DEFAULT_WINDOW_DAYS = 30


def get_monitoring_snapshot(db, window_days: int = DEFAULT_WINDOW_DAYS) -> dict[str, Any]:
    from sqlalchemy import select

    from app.database.models.assessment import Assessment, Prediction
    from app.ml.model_loader import load_production_model

    window_start = datetime.now(timezone.utc) - timedelta(days=window_days)

    prediction_rows = db.scalars(select(Prediction).where(Prediction.created_at >= window_start)).all()
    assessment_rows = db.scalars(select(Assessment).where(Assessment.submitted_at >= window_start)).all()

    rows = [
        PredictionRow(
            outcome=p.outcome.value,
            model_version=p.model_version,
            insufficient_data_reason=p.insufficient_data_reason,
        )
        for p in prediction_rows
    ]

    loaded = load_production_model()
    baseline_positive_rate = (
        _baseline_positive_rate_from_metadata(loaded.metadata.evaluation_metrics) if loaded else None
    )

    return {
        "window_days": window_days,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "production_model_version": loaded.metadata.model_version if loaded else None,
        "prediction_distribution": compute_prediction_distribution(rows),
        "assessment_missing_field_rate_pct": compute_assessment_missing_field_rate(
            [a.unanswered_fields for a in assessment_rows]
        ),
        "drift": compute_drift_signal(rows, baseline_positive_rate),
        "inference_errors": {
            "count_since_process_start": get_inference_error_count(),
            "note": "Process-lifetime counter, resets on restart — see module docstring.",
        },
        "inference_latency": get_latency_stats(),
    }
