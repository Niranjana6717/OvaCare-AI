"""
Training entrypoint (requirement #11/#12/#13/#39).

    python3 train.py [--model-version 1.0.0]

Pipeline: load -> clean -> engineer -> drop-rows-missing-required ->
stratified split -> train + compare {LogisticRegression, RandomForest,
XGBoost if installed} -> calibrate the winner -> evaluate -> explain ->
save to ml-platform/models/staging/ with full metadata.

Design choices this script deliberately does NOT make on its own:
  * It never writes to models/production/ — promotion is a separate,
    reviewed step (requirement #39/#77: never auto-replace a production
    model with an unvalidated one).
  * It does not pick XGBoost "because it's usually best" — every candidate
    is scored on the same held-out test set with the same metric, and the
    comparison table is saved to reports/ so the choice is auditable
    (requirement #11: "Do not automatically declare XGBoost the winner").
  * If XGBoost isn't installed, it's left out of the comparison and the run
    log says so explicitly — it is not silently skipped.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent))
from calibrate import CALIBRATION_METHOD, calibrate_classifier  # noqa: E402
from data_loader import load_raw_primary  # noqa: E402
from evaluate import compute_metrics, subgroup_metrics  # noqa: E402
from feature_engineering import apply_feature_engineering  # noqa: E402
from feature_schema import (  # noqa: E402
    ALL_FEATURE_NAMES,
    CATEGORICAL_FEATURE_NAMES,
    FEATURE_SCHEMA_VERSION,
    NUMERIC_FEATURE_NAMES,
    REQUIRED_FEATURE_NAMES,
    TARGET_COLUMN,
    feature_specs_as_dicts,
)
from preprocessing import PREPROCESSING_VERSION, clean_and_rename, drop_rows_missing_required

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("train")

REPO_ROOT = Path(__file__).resolve().parents[2]
MODELS_STAGING_DIR = REPO_ROOT / "ml-platform" / "models" / "staging"
REPORTS_DIR = REPO_ROOT / "ml-platform" / "reports"

THRESHOLD_VERSION = "1.0.0"
DECISION_THRESHOLD = 0.5  # starting point — see docs/ml_documentation.md "Threshold selection rationale"
TEST_SIZE = 0.25
RANDOM_STATE = 42
CV_FOLDS = 5

DATASET_REFERENCE = (
    "Kottarathil, P. 'Polycystic ovary syndrome (PCOS)' dataset, Kaggle. "
    "https://www.kaggle.com/datasets/prasoonkottarathil/polycystic-ovary-syndrome-pcos "
    "(541 patients, 10 hospitals across Kerala, India; ~33% PCOS-positive / "
    "67% PCOS-negative). See docs/ml_documentation.md for full sourcing, "
    "license status, and known limitations."
)

# A stable identifier for WHICH snapshot of the dataset trained this model —
# distinct from DATASET_REFERENCE above (the citation/description). Kaggle
# does not version this specific dataset, so this is a project-assigned tag,
# not a value pulled from the dataset's own metadata; bump it if a
# meaningfully different download (different row count, corrected values,
# etc.) is ever used.
DATASET_VERSION = "kaggle-kottarathil-pcos-541-v1"

LIMITATIONS_TEXT = (
    "Single-country (India), single-region (Kerala) clinical sample of 541 "
    "patients — performance on other populations, ethnicities, age "
    "distributions, or clinical settings is not established. Diagnostic "
    "label reflects the source clinics' contemporaneous diagnostic criteria, "
    "not a standardized re-adjudication (label-quality/measurement bias). "
    "Subgroup performance (e.g. by age band) is reported where the test set "
    "has enough samples per group, and treated as unestablished otherwise. "
    "Selection bias possible: patients came from ovarian-health specialty "
    "clinics rather than a general population sample, which likely raises "
    "the observed PCOS prevalence and symptom severity above the general "
    "population, and would be expected to make this model MORE prone to "
    "false positives (over-flagging) if applied to a general screening "
    "population rather than a clinic-referred one."
)


def build_preprocessor() -> ColumnTransformer:
    numeric_pipeline = Pipeline(
        [("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())]
    )
    categorical_pipeline = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ]
    )
    return ColumnTransformer(
        [
            ("num", numeric_pipeline, NUMERIC_FEATURE_NAMES),
            ("cat", categorical_pipeline, CATEGORICAL_FEATURE_NAMES),
        ]
    )


def candidate_models() -> dict[str, object]:
    candidates: dict[str, object] = {
        "logistic_regression": LogisticRegression(max_iter=1000, class_weight="balanced"),
        "random_forest": RandomForestClassifier(
            n_estimators=300, max_depth=8, class_weight="balanced", random_state=RANDOM_STATE
        ),
    }
    try:
        from xgboost import XGBClassifier

        candidates["xgboost"] = XGBClassifier(
            n_estimators=300,
            max_depth=4,
            eval_metric="logloss",
            random_state=RANDOM_STATE,
        )
    except ImportError:
        log.warning("xgboost is not installed — excluded from this run's model comparison. "
                    "Install ml-platform/requirements.txt to include it.")
    return candidates


def run(model_version: str) -> None:
    log.info("Loading raw dataset...")
    raw_df = load_raw_primary()

    log.info("Cleaning and renaming columns...")
    df = clean_and_rename(raw_df)
    df = apply_feature_engineering(df)

    df, n_dropped = drop_rows_missing_required(df, REQUIRED_FEATURE_NAMES)
    log.info("Dropped %d/%d rows missing a required field.", n_dropped, len(df) + n_dropped)

    X = df[ALL_FEATURE_NAMES]
    y = df[TARGET_COLUMN].astype(int)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y
    )
    log.info("Train: %d rows (%.1f%% positive) | Test: %d rows (%.1f%% positive)",
              len(X_train), 100 * y_train.mean(), len(X_test), 100 * y_test.mean())

    comparison_report: dict[str, dict] = {}
    fitted_pipelines: dict[str, Pipeline] = {}
    cv = StratifiedKFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_STATE)

    for name, estimator in candidate_models().items():
        log.info("Training candidate: %s", name)
        pipeline = Pipeline(
            [("preprocessor", build_preprocessor()), ("classifier", calibrate_classifier(estimator))]
        )

        cv_scores = cross_val_score(pipeline, X_train, y_train, cv=cv, scoring="average_precision")
        pipeline.fit(X_train, y_train)

        y_proba = pipeline.predict_proba(X_test)[:, 1]
        y_pred = (y_proba >= DECISION_THRESHOLD).astype(int)

        metrics = compute_metrics(y_test.to_numpy(), y_pred, y_proba)
        metrics["cv_pr_auc_mean"] = round(float(cv_scores.mean()), 4)
        metrics["cv_pr_auc_std"] = round(float(cv_scores.std()), 4)

        comparison_report[name] = metrics
        fitted_pipelines[name] = pipeline
        log.info("%s: PR-AUC=%.3f ROC-AUC=%s F1=%.3f recall=%.3f",
                  name, metrics["pr_auc"] or -1, metrics["roc_auc"], metrics["f1"], metrics["recall_sensitivity"])

    # Selection rule, stated explicitly rather than implied: highest PR-AUC
    # on the held-out test set. PR-AUC (not accuracy or ROC-AUC alone) is
    # chosen as primary because the classes are imbalanced (~33%/67%) and
    # PR-AUC is more sensitive to performance on the minority (positive)
    # class, which matters most given #70's directive to weight false
    # negatives heavily.
    winner_name = max(comparison_report, key=lambda k: comparison_report[k]["pr_auc"] or -1)
    log.info("Selected model: %s (highest test PR-AUC)", winner_name)

    winner_pipeline = fitted_pipelines[winner_name]
    winner_metrics = dict(comparison_report[winner_name])
    winner_metrics["model_comparison_report"] = f"See ml-platform/reports/training_report_{model_version}.json"

    if len(X_test) >= 20:
        age_band = pd.cut(X_test["age"], bins=[0, 25, 35, 100], labels=["<=25", "26-35", "36+"])
        winner_metrics["subgroup_by_age_band"] = subgroup_metrics(
            y_test.to_numpy(),
            (winner_pipeline.predict_proba(X_test)[:, 1] >= DECISION_THRESHOLD).astype(int),
            winner_pipeline.predict_proba(X_test)[:, 1],
            age_band.to_numpy(),
        )

    _save_artifact(winner_name, winner_pipeline, winner_metrics, model_version, X_train)
    _save_report(comparison_report, model_version)


def _save_artifact(
    winner_name: str, pipeline: Pipeline, metrics: dict, model_version: str, X_train: pd.DataFrame
) -> None:
    out_dir = MODELS_STAGING_DIR / f"{model_version}_{winner_name}"
    out_dir.mkdir(parents=True, exist_ok=True)

    joblib.dump(pipeline, out_dir / "model_pipeline.joblib")

    background_sample = X_train.sample(n=min(100, len(X_train)), random_state=RANDOM_STATE)
    joblib.dump(background_sample, out_dir / "background_sample.joblib")

    metadata = {
        "model_name": winner_name,
        "model_version": model_version,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "preprocessing_version": PREPROCESSING_VERSION,
        "threshold_version": THRESHOLD_VERSION,
        "decision_threshold": DECISION_THRESHOLD,
        "training_date": datetime.now(timezone.utc).isoformat(),
        "dataset_reference": DATASET_REFERENCE,
        "dataset_version": DATASET_VERSION,
        "calibration_method": CALIBRATION_METHOD,
        "limitations": LIMITATIONS_TEXT,
        "evaluation_metrics": metrics,
        "features": feature_specs_as_dicts(),
    }
    with open(out_dir / "model_metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, default=str)

    log.info("Saved staged artifact to %s", out_dir)
    log.info(
        "This is a STAGING artifact, not production. Promotion to "
        "ml-platform/models/production/ is a separate, reviewed step — see "
        "docs/ml_documentation.md 'Model lifecycle and promotion'."
    )


def _save_report(comparison_report: dict, model_version: str) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"training_report_{model_version}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(comparison_report, f, indent=2, default=str)
    log.info("Saved model comparison report to %s", path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-version", default="1.0.0")
    args = parser.parse_args()
    run(args.model_version)
