"""
End-to-end proof of requirement #54's central rule ("never fabricate an ML
prediction"), exercised against a REAL, actually-trained scikit-learn
pipeline artifact — not a mock. The pipeline is trained here on a small,
explicitly-synthetic fixture (see SYNTHETIC_NOTE) purely so this test can
run without the real PCOS dataset (see docs/ml_documentation.md for why
that file isn't in this repository). Nothing in this file makes any claim
about clinical accuracy — it proves the CONTRACT: no model -> refuse; a
model present but missing/out-of-range required input -> refuse; a model
present with complete input -> a real number actually comes out of a real
classifier, with a real (non-SHAP-fallback, since shap isn't installed in
this environment either) explanation attached.

Run with: python3 -m unittest backend.tests.test_predictor_never_fabricates -v
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import joblib  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.compose import ColumnTransformer  # noqa: E402
from sklearn.impute import SimpleImputer  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.pipeline import Pipeline  # noqa: E402
from sklearn.preprocessing import OneHotEncoder, StandardScaler  # noqa: E402

SYNTHETIC_NOTE = "SYNTHETIC TEST FIXTURE — randomly generated, not real patient data."

NUMERIC_FEATURES = ["age", "average_cycle_length_days"]
CATEGORICAL_FEATURES = ["cycle_regularity"]
ALL_FEATURES_METADATA = [
    {"name": "age", "dtype": "numeric", "required": True, "categories": None, "min_value": 10, "max_value": 60},
    {
        "name": "average_cycle_length_days",
        "dtype": "numeric",
        "required": True,
        "categories": None,
        "min_value": 15,
        "max_value": 90,
    },
    {
        "name": "cycle_regularity",
        "dtype": "categorical",
        "required": True,
        "categories": ["regular", "irregular"],
        "min_value": None,
        "max_value": None,
    },
    {
        "name": "amh",
        "dtype": "numeric",
        "required": False,
        "categories": None,
        "min_value": 0,
        "max_value": 30,
    },
]


def _build_and_save_fixture_model(model_dir: Path) -> None:
    """Trains a REAL (tiny, synthetic-data) sklearn pipeline and writes it +
    its metadata in exactly the shape app.ml.model_loader expects."""
    rng = np.random.default_rng(11)
    n = 200
    age = rng.integers(18, 40, size=n)
    cycle_len = rng.integers(21, 45, size=n)
    regularity = rng.choice(["regular", "irregular"], size=n)
    amh = np.where(rng.random(n) < 0.3, np.nan, rng.uniform(1, 10, size=n))  # some missing, on purpose

    # A real (if synthetic) signal: irregular + longer cycles skew positive,
    # so the trained classifier has SOMETHING non-random to learn — this is
    # what lets the "complete valid input" test assert a probability that
    # isn't just noise.
    logit = -3 + 2.5 * (regularity == "irregular") + 0.05 * (cycle_len - 28)
    prob = 1 / (1 + np.exp(-logit))
    label = (rng.random(n) < prob).astype(int)

    df = pd.DataFrame(
        {"age": age, "average_cycle_length_days": cycle_len, "cycle_regularity": regularity, "amh": amh}
    )

    preprocessor = ColumnTransformer(
        [
            (
                "num",
                Pipeline([("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())]),
                NUMERIC_FEATURES + ["amh"],
            ),
            (
                "cat",
                Pipeline(
                    [("imputer", SimpleImputer(strategy="most_frequent")), ("onehot", OneHotEncoder(handle_unknown="ignore"))]
                ),
                CATEGORICAL_FEATURES,
            ),
        ]
    )
    pipeline = Pipeline([("preprocessor", preprocessor), ("classifier", LogisticRegression(max_iter=500))])
    pipeline.fit(df, label)

    model_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, model_dir / "model_pipeline.joblib")
    joblib.dump(df.sample(n=50, random_state=1), model_dir / "background_sample.joblib")

    metadata = {
        "model_name": "fixture_logistic_regression",
        "model_version": "test-fixture-0.0.1",
        "feature_schema_version": "test-1.0.0",
        "preprocessing_version": "test-1.0.0",
        "threshold_version": "test-1.0.0",
        "decision_threshold": 0.5,
        "training_date": datetime.now(timezone.utc).isoformat(),
        "dataset_reference": SYNTHETIC_NOTE,
        "limitations": SYNTHETIC_NOTE + " Used only to test the prediction contract, never for real screening.",
        "evaluation_metrics": {"note": SYNTHETIC_NOTE},
        "features": ALL_FEATURES_METADATA,
    }
    with open(model_dir / "model_metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f)


class TestPredictorNeverFabricates(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="ovacare_model_fixture_"))
        self.model_dir = self.tmp_dir / "model"

        import os

        os.environ["MODEL_PATH"] = str(self.model_dir)
        os.environ["JWT_SECRET"] = "test-secret-not-for-production"

        from app.config import get_settings
        from app.ml import model_loader

        get_settings.cache_clear()
        model_loader.load_production_model.cache_clear()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)
        from app.config import get_settings
        from app.ml import model_loader

        get_settings.cache_clear()
        model_loader.load_production_model.cache_clear()

    def _run_prediction(self, raw_responses: dict):
        from app.ml.predictor import run_prediction

        return run_prediction(raw_responses)

    # --- Path 1: no model artifact present at all ---
    def test_no_model_present_returns_insufficient_data_not_a_guess(self):
        result = self._run_prediction({"age": 25, "average_cycle_length_days": 30, "cycle_regularity": "regular"})
        self.assertFalse(result.available)
        self.assertEqual(result.outcome, "insufficient_data")
        self.assertIsNone(result.probability)
        self.assertIn("No validated production screening model", result.insufficient_data_reason)

    # --- Path 2: model present, required field missing ---
    def test_missing_required_field_refuses_rather_than_imputes(self):
        _build_and_save_fixture_model(self.model_dir)
        from app.ml.model_loader import load_production_model

        load_production_model.cache_clear()

        result = self._run_prediction({"average_cycle_length_days": 30, "cycle_regularity": "regular"})  # no age
        self.assertTrue(result.available)  # model WAS loaded
        self.assertEqual(result.outcome, "insufficient_data")
        self.assertIsNone(result.probability)
        self.assertIn("Age", result.insufficient_data_reason)

    # --- Path 3: model present, required field out of the validated range ---
    def test_out_of_range_required_field_refuses(self):
        _build_and_save_fixture_model(self.model_dir)
        from app.ml.model_loader import load_production_model

        load_production_model.cache_clear()

        result = self._run_prediction(
            {"age": 250, "average_cycle_length_days": 30, "cycle_regularity": "regular"}  # age way out of range
        )
        self.assertEqual(result.outcome, "insufficient_data")
        self.assertIsNone(result.probability)
        self.assertIn("validated input range", result.insufficient_data_reason)

    # --- Path 4: model present, complete input -> a REAL prediction, with traceability ---
    def test_complete_input_returns_real_probability_and_explanation(self):
        _build_and_save_fixture_model(self.model_dir)
        from app.ml.model_loader import load_production_model

        load_production_model.cache_clear()

        result = self._run_prediction(
            {"age": 29, "average_cycle_length_days": 45, "cycle_regularity": "irregular", "amh": 6.2}
        )
        self.assertTrue(result.available)
        self.assertIn(result.outcome, ("higher_indication", "lower_indication"))
        self.assertIsInstance(result.probability, float)
        self.assertTrue(0.0 <= result.probability <= 1.0)

        # Full traceability, unfaked — these came from the metadata file
        # written alongside the real artifact, not hardcoded.
        self.assertEqual(result.model_version, "test-fixture-0.0.1")
        self.assertEqual(result.feature_schema_version, "test-1.0.0")

        # Explanation came from a real method (SHAP unavailable in this
        # environment, so it must be the documented fallback, not silently
        # empty).
        self.assertIn(result.explanation["method"], ("coefficient_fallback", "shap"))
        self.assertGreater(len(result.explanation["factors"]), 0)

    # --- Path 5: optional field left out does NOT block a prediction ---
    def test_missing_optional_field_still_predicts(self):
        _build_and_save_fixture_model(self.model_dir)
        from app.ml.model_loader import load_production_model

        load_production_model.cache_clear()

        result = self._run_prediction(
            {"age": 29, "average_cycle_length_days": 30, "cycle_regularity": "regular"}  # no amh — optional
        )
        self.assertTrue(result.available)
        self.assertIn(result.outcome, ("higher_indication", "lower_indication"))
        self.assertIsNotNone(result.probability)


if __name__ == "__main__":
    unittest.main()
