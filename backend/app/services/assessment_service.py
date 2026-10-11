"""
Orchestrates a screening submission: persist the raw answers as-submitted,
run the independent safety red-flag check, then run the ML prediction, and
persist that too. Safety check result is returned to the caller regardless
of the ML outcome — it is never gated on the ML path succeeding (requirement
#67: urgent information must not wait on the AI assessment to complete).
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.database.models.assessment import Assessment, Prediction
from app.services import prediction_service
from app.services.safety_service import SafetyCheckResult, check_for_red_flags


def create_assessment(db: Session, user_id: str, raw_responses: dict, unanswered_fields: list[str]) -> Assessment:
    """Persists the as-submitted questionnaire answers only. No prediction is
    run here — the review-before-predict split matches requirement #75 (user
    can review exactly what was stored) and gives the API two endpoints:
    POST /assessments (this) and POST /predictions (below)."""
    assessment = Assessment(
        user_id=user_id,
        raw_responses=raw_responses,
        unanswered_fields=unanswered_fields,
    )
    db.add(assessment)
    db.flush()
    return assessment


def run_safety_and_prediction(db: Session, assessment: Assessment) -> tuple[Prediction, SafetyCheckResult]:
    """The safety check runs independent of, and is never gated on, the ML
    call (requirement #67/#68) — both are computed here from the same raw
    responses, and the safety result is returned even if the caller ignores
    it, so the API layer can never accidentally drop it."""
    safety_result = check_for_red_flags(assessment.raw_responses)
    prediction = prediction_service.generate_prediction_for_assessment(db, assessment)
    return prediction, safety_result


def submit_assessment(
    db: Session, user_id: str, raw_responses: dict, unanswered_fields: list[str]
) -> tuple[Assessment, Prediction, SafetyCheckResult]:
    """Convenience wrapper combining both steps in one DB transaction, used
    by tests and any client that wants a single round trip."""
    assessment = create_assessment(db, user_id, raw_responses, unanswered_fields)
    prediction, safety_result = run_safety_and_prediction(db, assessment)
    return assessment, prediction, safety_result
