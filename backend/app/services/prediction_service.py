"""
Persists predictions and maps ML output onto the safety-approved wording
layer. This is the only place `app.ml.predictor` output is turned into a
`Prediction` row, and the only place screening result TEXT is assembled for
the API to return — so `assert_safe_wording` runs exactly once, here, on
every screening response before it leaves the service layer.
"""
from __future__ import annotations

import logging
import time

from sqlalchemy.orm import Session

from app.database.models.assessment import Assessment, Prediction, ScreeningOutcome
from app.logging_config import log_structured
from app.ml.predictor import run_prediction
from app.safety.wording import (
    EXPLANATION_FRAMING_PREFIX,
    MEDICAL_DISCLAIMER,
    SCREENING_RESULT_TEXT,
    assert_safe_wording,
)
from app.services import monitoring_service

logger = logging.getLogger("ovacare.ml")

_OUTCOME_MAP = {
    "higher_indication": ScreeningOutcome.HIGHER_INDICATION,
    "lower_indication": ScreeningOutcome.LOWER_INDICATION,
    "insufficient_data": ScreeningOutcome.INSUFFICIENT_DATA,
}


def generate_prediction_for_assessment(db: Session, assessment: Assessment) -> Prediction:
    # Monitoring (requirement: "Track production inference metadata ...
    # inference errors, latency"). Observes the same run_prediction() call
    # this function always made — never changes what it returns, and an
    # exception here is re-raised exactly as before recording was added.
    started = time.monotonic()
    try:
        result = run_prediction(assessment.raw_responses)
    except Exception:
        monitoring_service.record_inference_outcome(
            succeeded=False, latency_ms=(time.monotonic() - started) * 1000
        )
        # Structured log, never the raw questionnaire responses — only the
        # assessment id (an opaque UUID, not health information) and the
        # exception itself.
        log_structured(
            logger,
            logging.ERROR,
            "ml.inference_error",
            assessment_id=assessment.id,
            exc_info=True,
        )
        raise
    monitoring_service.record_inference_outcome(succeeded=True, latency_ms=(time.monotonic() - started) * 1000)

    message_text = SCREENING_RESULT_TEXT[result.outcome]
    assert_safe_wording(message_text)

    prediction = Prediction(
        user_id=assessment.user_id,
        assessment_id=assessment.id,
        model_name=result.model_name or "unavailable",
        model_version=result.model_version or "unavailable",
        feature_schema_version=result.feature_schema_version or "unavailable",
        preprocessing_version=result.preprocessing_version or "unavailable",
        threshold_version=result.threshold_version or "unavailable",
        outcome=_OUTCOME_MAP[result.outcome],
        probability=result.probability,
        explanation=result.explanation,
        insufficient_data_reason=result.insufficient_data_reason,
    )
    db.add(prediction)
    db.flush()
    return prediction


def build_result_payload(prediction: Prediction) -> dict:
    """Assemble the exact API-facing payload, including the disclaimer and
    non-diagnostic framing, in one place so no endpoint can accidentally
    omit them."""
    outcome_key = prediction.outcome.value
    message_text = SCREENING_RESULT_TEXT[outcome_key]
    assert_safe_wording(message_text)

    return {
        "assessment_id": prediction.assessment_id,
        "outcome": outcome_key,
        "message": message_text,
        "probability": prediction.probability,
        "explanation_framing": EXPLANATION_FRAMING_PREFIX if prediction.explanation.get("factors") else None,
        "explanation": prediction.explanation,
        "insufficient_data_reason": prediction.insufficient_data_reason,
        "model_version": prediction.model_version,
        "feature_schema_version": prediction.feature_schema_version,
        "preprocessing_version": prediction.preprocessing_version,
        "threshold_version": prediction.threshold_version,
        "assessed_at": prediction.created_at.isoformat(),
        "medical_disclaimer": MEDICAL_DISCLAIMER,
    }
