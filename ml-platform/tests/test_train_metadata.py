"""
Real, executed test that ml-platform/src/train.py's saved artifact metadata
includes the fields requirement #12 asks for — calibration_method and
dataset_version — without needing the real (Kaggle-only, not present in
this sandbox) dataset. train.py's DatasetNotFoundError guard means
train.run() itself can't be exercised here (see data_loader.py's
docstring), but `_save_artifact()` — the function that actually writes
model_metadata.json — takes no dataset argument at all, so it CAN be
called directly with a tiny fitted pipeline built from synthetic data.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

import train as train_module  # noqa: E402
from calibrate import CALIBRATION_METHOD  # noqa: E402


class TestSavedArtifactMetadata(unittest.TestCase):
    def test_metadata_json_includes_calibration_method_and_dataset_version(self):
        rng = np.random.default_rng(0)
        X_train = pd.DataFrame({"age": rng.integers(18, 40, size=10)})
        pipeline = Pipeline([("classifier", LogisticRegression())])
        # Not actually fit against the real feature schema — this test only
        # exercises _save_artifact()'s metadata-writing logic, not a real
        # training run (which needs the real dataset — see module docstring).

        with tempfile.TemporaryDirectory() as tmp:
            original_staging_dir = train_module.MODELS_STAGING_DIR
            original_reports_dir = train_module.REPORTS_DIR
            train_module.MODELS_STAGING_DIR = Path(tmp) / "staging"
            train_module.REPORTS_DIR = Path(tmp) / "reports"
            try:
                train_module._save_artifact(
                    winner_name="logistic_regression",
                    pipeline=pipeline,
                    metrics={"pr_auc": 0.5, "n_samples": 10, "n_positive": 3, "n_negative": 7},
                    model_version="test-0.0.1",
                    X_train=X_train,
                )
                out_dir = train_module.MODELS_STAGING_DIR / "test-0.0.1_logistic_regression"
                with open(out_dir / "model_metadata.json", encoding="utf-8") as f:
                    metadata = json.load(f)
            finally:
                train_module.MODELS_STAGING_DIR = original_staging_dir
                train_module.REPORTS_DIR = original_reports_dir

        self.assertEqual(metadata["calibration_method"], CALIBRATION_METHOD)
        self.assertEqual(metadata["dataset_version"], train_module.DATASET_VERSION)
        self.assertIn("dataset_reference", metadata)  # pre-existing field, must still be present
        self.assertEqual(metadata["model_version"], "test-0.0.1")


if __name__ == "__main__":
    unittest.main()
