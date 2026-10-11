"""Model evaluation — the full metric set the product rules require
(requirement #11/#70): never optimize for accuracy alone, and always report
enough to judge false negatives specifically, since a missed screening
matters more than a false alarm in this domain."""
from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.calibration import calibration_curve
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray, y_proba: np.ndarray) -> dict[str, Any]:
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()

    frac_pos, mean_pred = calibration_curve(y_true, y_proba, n_bins=min(10, max(2, len(y_true) // 5)))

    return {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
        "recall_sensitivity": round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
        "roc_auc": round(float(roc_auc_score(y_true, y_proba)), 4) if len(set(y_true)) > 1 else None,
        "pr_auc": round(float(average_precision_score(y_true, y_proba)), 4) if len(set(y_true)) > 1 else None,
        "confusion_matrix": {
            "true_negative": int(tn),
            "false_positive": int(fp),
            "false_negative": int(fn),
            "true_positive": int(tp),
        },
        "false_negative_rate": round(float(fn / (fn + tp)), 4) if (fn + tp) > 0 else None,
        "calibration_curve": {
            "fraction_of_positives": [round(float(v), 4) for v in frac_pos],
            "mean_predicted_value": [round(float(v), 4) for v in mean_pred],
        },
        "n_samples": int(len(y_true)),
        "n_positive": int(np.sum(y_true == 1)),
        "n_negative": int(np.sum(y_true == 0)),
    }


def subgroup_metrics(y_true: np.ndarray, y_pred: np.ndarray, y_proba: np.ndarray, groups: np.ndarray) -> dict[str, Any]:
    """Per-subgroup metrics (requirement #72), computed only for groups with
    enough samples that a metric is not misleading. Returns {} (not a
    fabricated number) for any group below the minimum."""
    MIN_GROUP_SIZE = 20
    results: dict[str, Any] = {}
    for group_value in sorted(set(groups)):
        mask = groups == group_value
        if mask.sum() < MIN_GROUP_SIZE:
            results[str(group_value)] = {
                "n_samples": int(mask.sum()),
                "note": f"Below minimum group size ({MIN_GROUP_SIZE}) for a reliable subgroup metric — not computed.",
            }
            continue
        results[str(group_value)] = compute_metrics(y_true[mask], y_pred[mask], y_proba[mask])
    return results
