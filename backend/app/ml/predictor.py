"""
Pure prediction orchestration — no DB access here (see services/prediction_service.py
for persistence). This is the module that enforces requirement #54's single
most important rule: **never fabricate a prediction.**

Every exit path is one of exactly three outcomes:
  1. No production model is loaded                 -> insufficient_data
  2. Required inputs are missing or out of range    -> insufficient_data
  3. The model actually ran                          -> higher/lower_indication

There is no fourth path that returns a guessed number.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from app.config import get_settings
from app.ml.explainability import explain_prediction
from app.ml.model_loader import load_production_model
from app.ml.preprocessing import build_model_input


@dataclass
class PredictionResult:
    available: bool
    outcome: str  # "higher_indication" | "lower_indication" | "insufficient_data"
    probability: Optional[float]
    explanation: dict[str, Any]
    insufficient_data_reason: Optional[str]
    model_name: Optional[str] = None
    model_version: Optional[str] = None
    feature_schema_version: Optional[str] = None
    preprocessing_version: Optional[str] = None
    threshold_version: Optional[str] = None


def _humanize(field_names: list[str]) -> str:
    from app.ml.explainability import human_label  # reuse the same copy map

    return ", ".join(human_label(name) for name in field_names)


def run_prediction(raw_responses: dict[str, Any]) -> PredictionResult:
    loaded = load_production_model()

    if loaded is None:
        return PredictionResult(
            available=False,
            outcome="insufficient_data",
            probability=None,
            explanation={"method": "unavailable", "factors": []},
            insufficient_data_reason=(
                "No validated production screening model is currently deployed. "
                "This is a deliberate safety default, not an error to work around — "
                "see docs/ml_documentation.md."
            ),
        )

    prepared = build_model_input(raw_responses, loaded.metadata)

    if not prepared.is_sufficient:
        reasons = []
        if prepared.missing_required_fields:
            reasons.append(f"missing: {_humanize(prepared.missing_required_fields)}")
        if prepared.out_of_range_fields:
            reasons.append(f"outside the validated input range: {_humanize(prepared.out_of_range_fields)}")
        return PredictionResult(
            available=True,
            outcome="insufficient_data",
            probability=None,
            explanation={"method": "unavailable", "factors": []},
            insufficient_data_reason="Some required information was " + "; ".join(reasons) + ".",
            model_name=loaded.metadata.model_name,
            model_version=loaded.metadata.model_version,
            feature_schema_version=loaded.metadata.feature_schema_version,
            preprocessing_version=loaded.metadata.preprocessing_version,
            threshold_version=loaded.metadata.threshold_version,
        )

    probability = float(loaded.pipeline.predict_proba(prepared.frame)[0][1])
    outcome = "higher_indication" if probability >= loaded.metadata.decision_threshold else "lower_indication"

    model_dir = Path(get_settings().MODEL_PATH)
    explanation = explain_prediction(loaded.pipeline, prepared.frame, loaded.metadata, model_dir).to_dict()

    return PredictionResult(
        available=True,
        outcome=outcome,
        probability=round(probability, 4),
        explanation=explanation,
        insufficient_data_reason=None,
        model_name=loaded.metadata.model_name,
        model_version=loaded.metadata.model_version,
        feature_schema_version=loaded.metadata.feature_schema_version,
        preprocessing_version=loaded.metadata.preprocessing_version,
        threshold_version=loaded.metadata.threshold_version,
    )
