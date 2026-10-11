"""Probability calibration (requirement #12).

Wraps scikit-learn's `CalibratedClassifierCV` so `train.py` doesn't need to
know the calibration method's details, and so this is the one place that
decides/records which method was used.
"""
from __future__ import annotations

from sklearn.base import BaseEstimator
from sklearn.calibration import CalibratedClassifierCV

CALIBRATION_METHOD = "sigmoid"  # Platt scaling — a reasonable default for small/medium datasets;
# "isotonic" is more flexible but needs more data than this dataset's ~541
# rows reliably support without overfitting the calibration itself.
CALIBRATION_CV_FOLDS = 5


def calibrate_classifier(estimator: BaseEstimator) -> CalibratedClassifierCV:
    return CalibratedClassifierCV(estimator, method=CALIBRATION_METHOD, cv=CALIBRATION_CV_FOLDS)
