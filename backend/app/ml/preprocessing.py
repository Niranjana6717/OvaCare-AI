"""
Builds a single-row model input frame from raw questionnaire responses.

This module does NOT impute or transform values — that lives inside the
saved sklearn Pipeline itself (see ml-platform/src/train.py), so the exact
same transformation is guaranteed at train time and serve time. This
module's only job is: given the feature schema the loaded model expects,
pull those named fields out of `raw_responses`, leave missing ones as None,
and flag which REQUIRED fields are missing so predictor.py can refuse to
serve an unreliable result (requirement #73/#74) instead of letting the
pipeline silently impute something clinically load-bearing.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from app.ml.model_loader import ModelMetadata


@dataclass
class PreparedInput:
    frame: pd.DataFrame
    missing_required_fields: list[str] = field(default_factory=list)
    out_of_range_fields: list[str] = field(default_factory=list)

    @property
    def is_sufficient(self) -> bool:
        return len(self.missing_required_fields) == 0 and len(self.out_of_range_fields) == 0


# Sentinel strings the frontend/questionnaire uses for "I don't have these
# results" (requirement #9). Anything matching these becomes a real missing
# value (None / NaN), never a fabricated number — it must never be coerced
# to 0 or a population average outside of the pipeline's documented,
# versioned imputation strategy.
_UNKNOWN_SENTINELS = {None, "", "unknown", "not_provided", "i_dont_have_these_results"}


def build_model_input(raw_responses: dict, metadata: ModelMetadata) -> PreparedInput:
    row: dict[str, object] = {}
    missing_required: list[str] = []
    out_of_range: list[str] = []

    for feature in metadata.features:
        value = raw_responses.get(feature.name)
        if isinstance(value, str) and value.strip().lower() in _UNKNOWN_SENTINELS:
            value = None
        if value in _UNKNOWN_SENTINELS:
            value = None

        if value is None and feature.required:
            missing_required.append(feature.name)

        if (
            value is not None
            and feature.dtype == "numeric"
            and (feature.min_value is not None or feature.max_value is not None)
        ):
            try:
                numeric_value = float(value)
            except (TypeError, ValueError):
                numeric_value = None
            if numeric_value is not None:
                below = feature.min_value is not None and numeric_value < feature.min_value
                above = feature.max_value is not None and numeric_value > feature.max_value
                if (below or above) and feature.required:
                    out_of_range.append(feature.name)

        row[feature.name] = value

    frame = pd.DataFrame([row], columns=metadata.all_feature_names)
    return PreparedInput(frame=frame, missing_required_fields=missing_required, out_of_range_fields=out_of_range)
