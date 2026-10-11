"""
Global explainability report for a trained pipeline (model-card material —
distinct from `backend/app/ml/explainability.py`, which explains one
person's individual prediction at serving time). Tries SHAP first; falls
back to a documented alternative if SHAP isn't installed, and labels the
report with whichever method actually ran (requirement #13: "SHAP or
another suitable explainability method").
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline


def global_feature_importance(pipeline: Pipeline, X_background: pd.DataFrame) -> dict[str, Any]:
    preprocessor = pipeline.named_steps["preprocessor"]
    classifier = pipeline.named_steps["classifier"]
    feature_names_out = list(preprocessor.get_feature_names_out())

    try:
        import shap

        transformed = preprocessor.transform(X_background)
        explainer = shap.Explainer(classifier, transformed, feature_names=feature_names_out)
        shap_values = explainer(transformed)
        values = np.asarray(shap_values.values)
        if values.ndim == 3:
            values = values[:, :, -1]
        importance = np.abs(values).mean(axis=0)
        method = "shap_mean_abs"
    except ImportError:
        importance = _fallback_importance(classifier, preprocessor, X_background, feature_names_out)
        method = "fallback_importance"

    ranked = sorted(zip(feature_names_out, importance), key=lambda kv: kv[1], reverse=True)
    return {
        "method": method,
        "global_feature_importance": [{"feature": name, "importance": round(float(v), 5)} for name, v in ranked],
    }


def _fallback_importance(classifier, preprocessor, X_background: pd.DataFrame, feature_names_out: list[str]) -> np.ndarray:
    base_estimator = getattr(classifier, "estimator", classifier)  # unwrap CalibratedClassifierCV if present
    if hasattr(base_estimator, "feature_importances_"):
        return base_estimator.feature_importances_
    if hasattr(base_estimator, "coef_"):
        return np.abs(base_estimator.coef_[0])
    # Last resort: permutation importance, computed directly here rather
    # than left unavailable.
    from sklearn.inspection import permutation_importance

    transformed = preprocessor.transform(X_background)
    result = permutation_importance(classifier, transformed, classifier.predict(transformed), n_repeats=5)
    return result.importances_mean
