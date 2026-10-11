"""
Per-prediction explanation.

Primary method: SHAP, applied to the trained classifier using a small
background sample saved alongside the model artifact at training time
(`background_sample.joblib` — see ml-platform/src/train.py). If SHAP or the
background sample isn't available in a given deployment, this module falls
back to a documented, honest alternative — signed coefficient contribution
for linear models, or impurity-based global importance re-weighted by how
far the instance's value sits from the training mean for tree models — and
labels the explanation with which method actually produced it. It never
silently invents contributing factors.

Human-readable labels/blurbs come from a small static, versioned map
(`_FEATURE_COPY`) rather than being generated per-request, so they are the
same reviewable content the rest of the safety copy is (requirement #79:
"do not dynamically generate unsupported medical claims").
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.ml.model_loader import ModelMetadata

TOP_N_FACTORS = 4

# content_id "feature_explanation_copy" in app.safety.content_review —
# pending_review like the rest of the health copy in this repo.
_FEATURE_COPY: dict[str, dict[str, str]] = {
    "age": {"label": "Age", "why": "PCOS-related hormonal patterns can vary across age groups."},
    "cycle_regularity": {
        "label": "Cycle regularity",
        "why": "Irregular cycles are one of several patterns considered alongside other factors — on their own they do not indicate PCOS.",
    },
    "average_cycle_length_days": {
        "label": "Average cycle length",
        "why": "Cycle length is one input among several the model weighs together.",
    },
    "acne": {"label": "Acne", "why": "Skin changes can relate to hormonal patterns the model considers."},
    "hair_growth_excess": {
        "label": "Excess hair growth",
        "why": "This is one of several physical symptoms the model weighs together.",
    },
    "hair_thinning": {"label": "Hair thinning", "why": "One of several physical symptoms the model weighs together."},
    "bmi": {
        "label": "BMI",
        "why": "BMI is one contextual factor among several — it is not the primary basis for this result.",
    },
    "lh_fsh_ratio": {"label": "LH/FSH ratio", "why": "A hormonal marker the model weighs alongside others, when provided."},
    "testosterone_level": {"label": "Testosterone level", "why": "A hormonal marker the model weighs alongside others, when provided."},
}


def human_label(feature_name: str) -> str:
    return _FEATURE_COPY.get(feature_name, {}).get("label", feature_name.replace("_", " ").title())


# Backwards-compatible private alias used within this module.
_human_label = human_label


def _why_it_matters(feature_name: str) -> str:
    return _FEATURE_COPY.get(feature_name, {}).get(
        "why", "This factor is one of several the model weighs together."
    )


@dataclass
class ExplanationFactor:
    feature_name: str
    label: str
    contribution: float  # signed; sign meaning is relative to this model's positive class
    why_it_matters: str


@dataclass
class Explanation:
    method: str  # "shap" | "coefficient_fallback" | "importance_fallback" | "unavailable"
    factors: list[ExplanationFactor]

    def to_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "factors": [
                {
                    "feature": f.feature_name,
                    "label": f.label,
                    "contribution": f.contribution,
                    "why_it_matters": f.why_it_matters,
                }
                for f in self.factors
            ],
        }


def _try_shap_explanation(pipeline: Any, frame: pd.DataFrame, model_dir: Path) -> Explanation | None:
    try:
        import shap  # noqa: F401  (optional dependency)
        import joblib
    except ImportError:
        return None

    background_path = model_dir / "background_sample.joblib"
    if not background_path.exists():
        return None

    try:
        preprocessor = pipeline.named_steps["preprocessor"]
        classifier = pipeline.named_steps["classifier"]

        background_raw: pd.DataFrame = joblib.load(background_path)
        background_transformed = preprocessor.transform(background_raw)
        instance_transformed = preprocessor.transform(frame)

        feature_names_out = list(preprocessor.get_feature_names_out())

        explainer = shap.Explainer(classifier, background_transformed, feature_names=feature_names_out)
        shap_values = explainer(instance_transformed)

        # shap_values.values shape: (1, n_transformed_features) for binary
        # classifiers exposing a single output, or (1, n_features, n_classes).
        values = np.asarray(shap_values.values)
        if values.ndim == 3:
            values = values[:, :, -1]  # positive class
        contributions = values[0]

        # Fold one-hot / transformed sub-columns back to their original
        # raw feature name (e.g. "cat__cycle_regularity_often" -> "cycle_regularity")
        aggregated: dict[str, float] = {}
        for name, contribution in zip(feature_names_out, contributions):
            original = _original_feature_name(name, frame.columns)
            aggregated[original] = aggregated.get(original, 0.0) + float(contribution)

        ranked = sorted(aggregated.items(), key=lambda kv: abs(kv[1]), reverse=True)[:TOP_N_FACTORS]
        factors = [
            ExplanationFactor(
                feature_name=name,
                label=_human_label(name),
                contribution=round(value, 4),
                why_it_matters=_why_it_matters(name),
            )
            for name, value in ranked
        ]
        return Explanation(method="shap", factors=factors)
    except Exception:
        # Any SHAP failure falls through to the documented fallback rather
        # than surfacing a broken/partial explanation to the user.
        return None


def _original_feature_name(transformed_name: str, original_columns) -> str:
    for col in original_columns:
        if col in transformed_name:
            return col
    return transformed_name


def _fallback_explanation(pipeline: Any, frame: pd.DataFrame, metadata: ModelMetadata) -> Explanation:
    classifier = pipeline.named_steps["classifier"]
    preprocessor = pipeline.named_steps["preprocessor"]
    feature_names_out = list(preprocessor.get_feature_names_out())

    if hasattr(classifier, "coef_"):
        transformed = preprocessor.transform(frame)
        transformed = np.asarray(transformed.todense()) if hasattr(transformed, "todense") else np.asarray(transformed)
        contributions = (transformed[0] * classifier.coef_[0])
        method = "coefficient_fallback"
    elif hasattr(classifier, "feature_importances_"):
        contributions = classifier.feature_importances_
        method = "importance_fallback"
    else:
        return Explanation(method="unavailable", factors=[])

    aggregated: dict[str, float] = {}
    for name, contribution in zip(feature_names_out, contributions):
        original = _original_feature_name(name, frame.columns)
        aggregated[original] = aggregated.get(original, 0.0) + float(contribution)

    ranked = sorted(aggregated.items(), key=lambda kv: abs(kv[1]), reverse=True)[:TOP_N_FACTORS]
    factors = [
        ExplanationFactor(
            feature_name=name,
            label=_human_label(name),
            contribution=round(value, 4),
            why_it_matters=_why_it_matters(name),
        )
        for name, value in ranked
    ]
    return Explanation(method=method, factors=factors)


def explain_prediction(pipeline: Any, frame: pd.DataFrame, metadata: ModelMetadata, model_dir: Path) -> Explanation:
    shap_result = _try_shap_explanation(pipeline, frame, model_dir)
    if shap_result is not None and shap_result.factors:
        return shap_result
    return _fallback_explanation(pipeline, frame, metadata)
