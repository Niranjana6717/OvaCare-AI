"""
Real, executed tests for scripts/register_model_version.py's dependency-free
logic (metadata loading/validation + field mapping) — the SQLAlchemy-using
`register()` function itself is written-but-not-executed in this sandbox,
same disclosed category as the rest of the backend (see
backend/tests/test_bootstrap_admin_logic.py's docstring for the pattern
this follows).
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(BACKEND_ROOT / "scripts"))

from register_model_version import (  # noqa: E402
    InvalidArtifactError,
    build_model_version_fields,
    load_and_validate_metadata,
)

VALID_METADATA = {
    "model_name": "logistic_regression",
    "model_version": "1.0.0",
    "feature_schema_version": "1.0.0",
    "preprocessing_version": "1.0.0",
    "threshold_version": "1.0.0",
    "decision_threshold": 0.5,
    "training_date": "2026-01-01T00:00:00+00:00",
    "dataset_reference": "some dataset",
    "dataset_version": "kaggle-x-v1",
    "calibration_method": "sigmoid",
    "limitations": "some limitations",
    "evaluation_metrics": {"pr_auc": 0.7},
    "features": [],
}


class TestLoadAndValidateMetadata(unittest.TestCase):
    def test_raises_when_metadata_file_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(InvalidArtifactError):
                load_and_validate_metadata(Path(tmp))

    def test_raises_when_pipeline_file_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "model_metadata.json").write_text(json.dumps(VALID_METADATA))
            with self.assertRaises(InvalidArtifactError):
                load_and_validate_metadata(Path(tmp))

    def test_raises_on_missing_required_key(self):
        incomplete = dict(VALID_METADATA)
        del incomplete["dataset_reference"]
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "model_metadata.json").write_text(json.dumps(incomplete))
            (Path(tmp) / "model_pipeline.joblib").write_bytes(b"fake")
            with self.assertRaises(InvalidArtifactError):
                load_and_validate_metadata(Path(tmp))

    def test_loads_valid_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "model_metadata.json").write_text(json.dumps(VALID_METADATA))
            (Path(tmp) / "model_pipeline.joblib").write_bytes(b"fake")
            metadata = load_and_validate_metadata(Path(tmp))
        self.assertEqual(metadata["model_version"], "1.0.0")


class TestBuildModelVersionFields(unittest.TestCase):
    def test_maps_all_fields_including_calibration_and_dataset_version(self):
        fields = build_model_version_fields(VALID_METADATA, artifact_path="/some/path", stage="staging")
        self.assertEqual(fields["model_name"], "logistic_regression")
        self.assertEqual(fields["calibration_method"], "sigmoid")
        self.assertEqual(fields["dataset_version"], "kaggle-x-v1")
        self.assertEqual(fields["stage"], "staging")
        self.assertEqual(fields["artifact_path"], "/some/path")

    def test_tolerates_older_artifact_missing_new_fields(self):
        older = dict(VALID_METADATA)
        del older["dataset_version"]
        del older["calibration_method"]
        fields = build_model_version_fields(older, artifact_path="/x", stage="staging")
        self.assertIsNone(fields["dataset_version"])
        self.assertIsNone(fields["calibration_method"])


if __name__ == "__main__":
    unittest.main()
