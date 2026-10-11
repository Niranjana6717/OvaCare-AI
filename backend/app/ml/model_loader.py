"""
Loads the production model artifact + its metadata sidecar.

The artifact is a full scikit-learn `Pipeline` (preprocessing + classifier)
saved with joblib by ml-platform/src/train.py, plus a JSON metadata file
written alongside it (same basename, `.json`). Loading BOTH from the same
directory, at the same time, is what guarantees a served prediction's
model_version/feature_schema_version/preprocessing_version/threshold_version
always describe the pipeline object actually in memory — they can never
drift apart because they're never set independently.

If no artifact is present at MODEL_PATH, `load_production_model()` returns
`None` rather than raising or fabricating a stand-in. Every caller
(predictor.py) must treat `None` as "screening is unavailable" and say so,
per requirement #54: "never fabricate ML predictions."
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from app.config import get_settings


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    dtype: str  # "numeric" | "categorical" | "boolean"
    required: bool
    categories: Optional[list[str]] = None
    # Validated range observed in the training data (numeric features only).
    # Used to detect out-of-distribution inputs (requirement #73) — NOT a
    # hard medical bound, just "outside what this model was ever shown."
    min_value: Optional[float] = None
    max_value: Optional[float] = None


@dataclass(frozen=True)
class ModelMetadata:
    model_name: str
    model_version: str
    feature_schema_version: str
    preprocessing_version: str
    threshold_version: str
    decision_threshold: float
    training_date: str
    dataset_reference: str
    limitations: str
    evaluation_metrics: dict[str, Any]
    features: list[FeatureSpec]
    # Added for requirement #12 ("store calibration_method, dataset_version").
    # Optional with a None default so an OLDER artifact saved before this
    # field existed still loads (never a hard KeyError on a pre-existing,
    # otherwise-valid model directory) — see _parse_metadata's .get() below.
    calibration_method: Optional[str] = None
    dataset_version: Optional[str] = None

    @property
    def required_feature_names(self) -> list[str]:
        return [f.name for f in self.features if f.required]

    @property
    def all_feature_names(self) -> list[str]:
        return [f.name for f in self.features]


@dataclass(frozen=True)
class LoadedModel:
    pipeline: Any  # sklearn Pipeline — typed Any to avoid a hard sklearn import here
    metadata: ModelMetadata


def _parse_metadata(raw: dict) -> ModelMetadata:
    return ModelMetadata(
        model_name=raw["model_name"],
        model_version=raw["model_version"],
        feature_schema_version=raw["feature_schema_version"],
        preprocessing_version=raw["preprocessing_version"],
        threshold_version=raw["threshold_version"],
        decision_threshold=raw["decision_threshold"],
        training_date=raw["training_date"],
        dataset_reference=raw["dataset_reference"],
        limitations=raw["limitations"],
        evaluation_metrics=raw["evaluation_metrics"],
        features=[FeatureSpec(**f) for f in raw["features"]],
        calibration_method=raw.get("calibration_method"),
        dataset_version=raw.get("dataset_version"),
    )


@lru_cache
def load_production_model() -> Optional[LoadedModel]:
    """Cached for process lifetime. Call `load_production_model.cache_clear()`
    in tests/after a redeploy to force a reload."""
    settings = get_settings()
    model_dir = Path(settings.MODEL_PATH)

    metadata_path = model_dir / "model_metadata.json"
    artifact_path = model_dir / "model_pipeline.joblib"

    if not metadata_path.exists() or not artifact_path.exists():
        return None

    import joblib  # imported lazily: keeps import cost off the hot path when no model is present

    with open(metadata_path, "r", encoding="utf-8") as f:
        metadata = _parse_metadata(json.load(f))

    pipeline = joblib.load(artifact_path)
    return LoadedModel(pipeline=pipeline, metadata=metadata)
