"""
Register a trained model artifact (written by ml-platform/src/train.py to
ml-platform/models/staging/<version>_<name>/) as a row in the `model_versions`
table, so it becomes visible to the admin portal (GET /admin/models).

This is the missing link this codebase had: train.py writes real files with
real metadata, but nothing previously connected those files to the database
table the admin portal actually reads from — so a freshly trained model was
invisible to admins until this script (or promote_model_version.py, which
calls the same logic) ran. Like bootstrap_admin.py, this is a manual,
operator-run script, not an HTTP endpoint — registering a model version is
an operational action (requirement #77: no code path auto-promotes or
auto-registers a model into the admin-visible registry on its own).

Usage:
    cd backend
    python scripts/register_model_version.py ../ml-platform/models/staging/1.0.0_logistic_regression

Idempotent: re-running against the same artifact directory updates the
existing row (matched on model_name + model_version) rather than creating a
duplicate.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

REQUIRED_METADATA_KEYS = (
    "model_name",
    "model_version",
    "feature_schema_version",
    "preprocessing_version",
    "threshold_version",
    "training_date",
    "dataset_reference",
    "limitations",
    "evaluation_metrics",
)


class InvalidArtifactError(Exception):
    pass


def load_and_validate_metadata(artifact_dir: Path) -> dict[str, Any]:
    """Pure (no DB, no SQLAlchemy) — reads and validates model_metadata.json.
    Kept separate from main() so it's directly unit-testable; see
    backend/tests/test_register_model_version_logic.py."""
    metadata_path = artifact_dir / "model_metadata.json"
    pipeline_path = artifact_dir / "model_pipeline.joblib"

    if not metadata_path.exists():
        raise InvalidArtifactError(f"No model_metadata.json found at {metadata_path}.")
    if not pipeline_path.exists():
        raise InvalidArtifactError(
            f"No model_pipeline.joblib found at {pipeline_path} — refusing to register metadata for an "
            "artifact whose actual model file is missing."
        )

    with open(metadata_path, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    missing = [k for k in REQUIRED_METADATA_KEYS if k not in metadata]
    if missing:
        raise InvalidArtifactError(f"model_metadata.json is missing required key(s): {missing}")

    return metadata


def build_model_version_fields(metadata: dict[str, Any], artifact_path: str, stage: str) -> dict[str, Any]:
    """Pure mapping from the artifact's metadata dict to ModelVersion column
    values. `stage` is passed in rather than hard-coded so this same
    function serves both register (always "staging") and re-registration
    after a promotion (promote_model_version.py passes "production")."""
    return {
        "model_name": metadata["model_name"],
        "model_version": metadata["model_version"],
        "feature_schema_version": metadata["feature_schema_version"],
        "preprocessing_version": metadata["preprocessing_version"],
        "threshold_version": metadata["threshold_version"],
        "stage": stage,
        "artifact_path": artifact_path,
        "training_date": metadata["training_date"],
        "evaluation_metrics": metadata["evaluation_metrics"],
        "dataset_reference": metadata["dataset_reference"],
        "dataset_version": metadata.get("dataset_version"),  # may be absent on an older artifact
        "calibration_method": metadata.get("calibration_method"),
        "limitations": metadata["limitations"],
    }


def register(artifact_dir: Path, stage: str = "staging") -> str:
    """Insert-or-update a ModelVersion row for this artifact. Returns
    "created" or "updated". Imports SQLAlchemy internally (not at module
    scope) so load_and_validate_metadata/build_model_version_fields above
    stay importable/testable without it, same pattern as
    scripts/bootstrap_admin.py."""
    metadata = load_and_validate_metadata(artifact_dir)
    fields = build_model_version_fields(metadata, artifact_path=str(artifact_dir), stage=stage)

    from datetime import datetime

    from sqlalchemy import select

    from app.database.database import SessionLocal
    from app.database.models.model_version import ModelStage, ModelVersion

    fields["stage"] = ModelStage(fields["stage"])
    fields["training_date"] = datetime.fromisoformat(fields["training_date"])

    db = SessionLocal()
    try:
        existing = db.scalar(
            select(ModelVersion).where(
                ModelVersion.model_name == fields["model_name"],
                ModelVersion.model_version == fields["model_version"],
            )
        )
        if existing is None:
            db.add(ModelVersion(**fields))
            db.commit()
            return "created"

        for key, value in fields.items():
            if key == "stage" and existing.stage.value == "production":
                # Never silently demote an already-promoted row by
                # re-running register against its (now-stale) staging
                # metadata — promotion/demotion is promote_model_version.py's
                # job, done deliberately, not a side effect of re-registering.
                continue
            setattr(existing, key, value)
        db.commit()
        return "updated"
    finally:
        db.close()


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python scripts/register_model_version.py <path-to-artifact-directory>")
        return 1

    artifact_dir = Path(sys.argv[1]).resolve()
    try:
        action = register(artifact_dir, stage="staging")
    except InvalidArtifactError as exc:
        print(f"Refusing to register: {exc}")
        return 1

    print(f"{action.capitalize()} model_versions row for {artifact_dir.name} (stage=staging).")
    print("This does NOT make it the production model — see scripts/promote_model_version.py for that "
          "deliberate, separate step.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
