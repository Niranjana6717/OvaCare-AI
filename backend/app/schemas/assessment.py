"""
Assessment submission schema.

`responses` carries the questionnaire answers keyed by the SAME feature
names the deployed model's feature_schema.json declares (age,
cycle_regularity, acne, ...) — deliberately not hardcoded to a fixed Pydantic
model, because the valid feature set is versioned by the model artifact, not
the API contract (requirement #9: "Only use fields supported by the final
validated model"). Basic type/range sanity is enforced generically here;
feature-specific validation happens in app.ml.preprocessing against the
model's own schema.

The red-flag safety fields ARE explicit, typed fields (not folded into the
free-form `responses` bag) because `app.safety.red_flag_rules` is a fixed,
reviewable ruleset that must not silently break if the ML feature set changes.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AssessmentSubmitRequest(BaseModel):
    # --- Free-form ML questionnaire responses (validated against the model's
    # own feature schema in app.ml.preprocessing, not here) ---
    responses: dict[str, Any] = Field(default_factory=dict)

    # Fields the user explicitly skipped via "I don't have these results"
    # (distinct from fields never asked — requirement #74).
    unanswered_fields: list[str] = Field(default_factory=list)

    # --- Red-flag safety fields (requirement #67/#68) — always collected,
    # always checked, independent of the ML path ---
    soaking_through_protection_hourly: bool = False
    bleeding_with_dizziness_or_fainting: bool = False
    pelvic_pain_severity: int | None = Field(default=None, ge=1, le=5)
    fainting_or_severe_dizziness: bool = False
    chest_pain_or_breathing_difficulty: bool = False

    def to_raw_responses(self) -> dict[str, Any]:
        safety_fields = {
            "soaking_through_protection_hourly": self.soaking_through_protection_hourly,
            "bleeding_with_dizziness_or_fainting": self.bleeding_with_dizziness_or_fainting,
            "pelvic_pain_severity": self.pelvic_pain_severity,
            "fainting_or_severe_dizziness": self.fainting_or_severe_dizziness,
            "chest_pain_or_breathing_difficulty": self.chest_pain_or_breathing_difficulty,
        }
        return {**self.responses, **safety_fields}


class SafetyCheckResponse(BaseModel):
    urgent: bool
    message: str | None
    triggered_rule_ids: list[str]


class PredictionResultResponse(BaseModel):
    assessment_id: str
    outcome: str
    message: str
    probability: float | None
    explanation_framing: str | None
    explanation: dict[str, Any]
    insufficient_data_reason: str | None
    model_version: str
    feature_schema_version: str
    preprocessing_version: str
    threshold_version: str
    assessed_at: str
    medical_disclaimer: str


class AssessmentSubmitResponse(BaseModel):
    assessment_id: str
    safety: SafetyCheckResponse
    result: PredictionResultResponse


class AssessmentHistoryItem(BaseModel):
    assessment_id: str
    submitted_at: str
    result: PredictionResultResponse
