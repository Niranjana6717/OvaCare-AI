"""
Real, executed tests for requirement #90 test 7: "historical predictions
must retain their original model version."

`app/services/prediction_service.py` imports SQLAlchemy (`Session`, the
`Prediction` ORM model), so it cannot be imported directly in this
sandbox (see docs/deployment.md — no SQLAlchemy installed here). That
module's full behavior is covered by the written-but-unexecuted pytest
suite instead. What CAN be verified for real, with only the standard
library plus the already-dependency-free `app.ml.predictor`, is the
actual mechanism that guarantees test 7, split into two real checks:

  1. A static-analysis check on prediction_service.py's source: the
     function that builds the API-facing payload from an already-stored
     Prediction (`build_result_payload`) never calls back into the model
     layer (`run_prediction` / `load_production_model`). If it did, a
     historical prediction's version fields could silently be
     recalculated against whatever model happens to be loaded NOW — the
     exact bug this requirement forbids. This is an architecture test:
     it can't execute the function, but it CAN prove the function's body
     contains no call that would let this bug exist.

  2. A behavioral check proving `model_version` really is tied to WHICH
     model produced a result: run the same (dependency-free, already
     covered by test_predictor_never_fabricates.py) `run_prediction()`
     against two differently-versioned model artifacts and confirm the
     two PredictionResult objects report different model_version values.
     Combined with (1) — nothing re-derives an old prediction's version
     from a newer model — this is what makes "keeps its original version"
     true rather than incidental.
"""
import ast
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

PREDICTION_SERVICE_PATH = BACKEND_ROOT / "app" / "services" / "prediction_service.py"


def _find_function(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"Function {name!r} not found in {PREDICTION_SERVICE_PATH}")


def _called_names(func: ast.FunctionDef) -> set[str]:
    names = set()
    for node in ast.walk(func):
        if isinstance(node, ast.Call):
            target = node.func
            if isinstance(target, ast.Name):
                names.add(target.id)
            elif isinstance(target, ast.Attribute):
                names.add(target.attr)
    return names


class TestBuildResultPayloadNeverRecalculates(unittest.TestCase):
    """Static-analysis half of test 7 — see module docstring."""

    @classmethod
    def setUpClass(cls):
        source = PREDICTION_SERVICE_PATH.read_text()
        cls.tree = ast.parse(source)

    def test_build_result_payload_does_not_call_run_prediction(self):
        func = _find_function(self.tree, "build_result_payload")
        called = _called_names(func)
        self.assertNotIn(
            "run_prediction",
            called,
            "build_result_payload() must read fields already stored on the Prediction row, "
            "never re-run the model — doing so would silently recalculate a historical result.",
        )

    def test_build_result_payload_does_not_call_load_production_model(self):
        func = _find_function(self.tree, "build_result_payload")
        called = _called_names(func)
        self.assertNotIn("load_production_model", called)

    def test_build_result_payload_reads_version_fields_from_its_argument(self):
        func = _find_function(self.tree, "build_result_payload")
        source = ast.get_source_segment(PREDICTION_SERVICE_PATH.read_text(), func)
        for field in ("model_version", "feature_schema_version", "preprocessing_version", "threshold_version"):
            self.assertIn(
                f"prediction.{field}",
                source,
                f"Expected build_result_payload to read {field} from the stored `prediction` argument.",
            )

    def test_run_prediction_is_only_called_once_in_the_module_at_creation_time(self):
        # generate_prediction_for_assessment is the ONLY place allowed to
        # call the model — it writes the result onto a new Prediction row
        # exactly once. If any other function in this module called
        # run_prediction, a later read could get a different answer than
        # an earlier one for the same historical row.
        callers = []
        for node in ast.walk(self.tree):
            if isinstance(node, ast.FunctionDef):
                if "run_prediction" in _called_names(node):
                    callers.append(node.name)
        self.assertEqual(callers, ["generate_prediction_for_assessment"])


def _build_fixture_model(model_dir: Path, model_version: str) -> None:
    """Same shape app.ml.model_loader AND app.ml.explainability expect —
    a ColumnTransformer named "preprocessor" feeding a classifier named
    "classifier" (explainability.py's coefficient-fallback path looks
    both up by those exact names) — mirrors
    test_predictor_never_fabricates.py's _build_and_save_fixture_model
    shape, since that file already proves this exact structure loads and
    explains correctly, rather than a reinvented approximation."""
    import numpy as np
    import pandas as pd
    from sklearn.compose import ColumnTransformer
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    rng = np.random.default_rng(7)
    n = 60
    df = pd.DataFrame({"age": rng.integers(18, 40, size=n), "bmi": rng.uniform(18, 35, size=n)})
    label = (df["bmi"] > 27).astype(int)

    preprocessor = ColumnTransformer(
        [("num", Pipeline([("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())]), ["age", "bmi"])]
    )
    pipeline = Pipeline([("preprocessor", preprocessor), ("classifier", LogisticRegression())])
    pipeline.fit(df, label)

    import joblib

    model_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, model_dir / "model_pipeline.joblib")

    metadata = {
        "model_name": "fixture_logistic_regression",
        "model_version": model_version,
        "feature_schema_version": "test-1.0.0",
        "preprocessing_version": "test-1.0.0",
        "threshold_version": "test-1.0.0",
        "decision_threshold": 0.5,
        "training_date": "2026-01-01T00:00:00+00:00",
        "dataset_reference": "SYNTHETIC TEST FIXTURE — not real patient data.",
        "limitations": "SYNTHETIC TEST FIXTURE — used only to test version traceability, never for real screening.",
        "evaluation_metrics": {"note": "synthetic fixture"},
        "features": [
            {"name": "age", "dtype": "numeric", "required": True, "categories": None, "min_value": 10, "max_value": 60},
            {"name": "bmi", "dtype": "numeric", "required": True, "categories": None, "min_value": 10, "max_value": 60},
        ],
    }
    (model_dir / "model_metadata.json").write_text(json.dumps(metadata))


class TestModelVersionReflectsWhichModelRan(unittest.TestCase):
    """Behavioral half of test 7 — see module docstring. Reuses the same
    real train->save->load->predict pipeline as
    test_predictor_never_fabricates.py, with two DIFFERENTLY versioned
    artifacts instead of one, swapped via the same MODEL_PATH env var +
    cache_clear() pattern that file already proves works."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="ovacare_version_test_"))
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)

        import os

        self._original_model_path = os.environ.get("MODEL_PATH")
        os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")

    def tearDown(self):
        import os

        from app.config import get_settings
        from app.ml import model_loader

        if self._original_model_path is None:
            os.environ.pop("MODEL_PATH", None)
        else:
            os.environ["MODEL_PATH"] = self._original_model_path
        get_settings.cache_clear()
        model_loader.load_production_model.cache_clear()

    def _run_against(self, model_dir: Path):
        import os

        from app.config import get_settings
        from app.ml import model_loader, predictor

        os.environ["MODEL_PATH"] = str(model_dir)
        get_settings.cache_clear()
        model_loader.load_production_model.cache_clear()
        return predictor.run_prediction({"age": 28, "bmi": 30})

    def test_two_differently_versioned_artifacts_produce_different_model_versions(self):
        dir_v1 = self.tmp_dir / "v1"
        dir_v2 = self.tmp_dir / "v2"
        _build_fixture_model(dir_v1, "1.0.0")
        _build_fixture_model(dir_v2, "2.0.0")

        result_v1 = self._run_against(dir_v1)
        result_v2 = self._run_against(dir_v2)

        self.assertEqual(result_v1.model_version, "1.0.0")
        self.assertEqual(result_v2.model_version, "2.0.0")
        self.assertNotEqual(
            result_v1.model_version,
            result_v2.model_version,
            "Two different model artifacts must produce two different recorded model_versions — this is "
            "what makes 'keep the ORIGINAL version' a meaningful guarantee once a result is stored, since "
            "prediction_service.generate_prediction_for_assessment copies this value onto the Prediction row "
            "exactly once, at creation time (see TestBuildResultPayloadNeverRecalculates above).",
        )


if __name__ == "__main__":
    unittest.main()
