"""
Promote a registered STAGING model version to PRODUCTION — the one
deliberate, human-invoked step in this codebase's model lifecycle
(Development -> Validation -> Staging -> Production -> Archived) that
actually changes which model the API serves. No code path anywhere else in
this repository does this automatically (requirement #77/#39: never
auto-replace a production model with an unvalidated one; ML monitoring's
drift signal, app/services/monitoring_service.py, only ever flags a number
for a human to look at — it never calls this script or anything like it).

Usage:
    cd backend
    python scripts/promote_model_version.py <model_name> <model_version> \\
        --reviewed-by "<real reviewer name/role>" --confirm

Both --reviewed-by and --confirm are required, on purpose: this asserts a
real review happened (the script cannot verify that itself — same trust
boundary as bootstrap_admin.py's operator-supplied credentials) and
guards against an accidental invocation without proof-of-intent.

What this does:
  1. Refuses unless the named (model_name, model_version) is currently in
     the "staging" stage — never promotes a "development"/"validation"
     row straight to production, and never re-promotes an already-archived
     one without going through staging again.
  2. If a production model already exists, demotes it to "archived" (DB
     row) and moves its artifact directory from models/production/ to
     models/archived/ — there is at most one production row at a time,
     enforced independently at the database level by
     ux_model_versions_single_production (see database/schema/schema.sql).
  3. Moves the candidate's artifact directory from models/staging/ to
     models/production/, and updates its DB row: stage=production,
     promoted_at=now, reviewed_by_role=<--reviewed-by>, reviewed_at=now,
     review_status="approved".
  4. Prints (does NOT set) the .env change the operator still has to make:
     MODEL_PATH must point at the new production directory, and the
     backend process restarted — app/ml/model_loader.py caches the loaded
     model for process lifetime from a single fixed path, by design (see
     that module's docstring), so this script cannot hot-swap it.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

REPO_ROOT = Path(__file__).resolve().parents[2]
MODELS_ROOT = REPO_ROOT / "ml-platform" / "models"


class PromotionRefusedError(Exception):
    pass


def decide_promotion_plan(candidate_stage: str, has_existing_production: bool) -> str:
    """Pure decision logic, independent of SQLAlchemy/the filesystem —
    directly unit-tested in backend/tests/test_promote_model_version_logic.py.

    Returns "promote_and_archive_existing", "promote_no_existing_production",
    or raises PromotionRefusedError if candidate_stage isn't "staging"."""
    if candidate_stage != "staging":
        raise PromotionRefusedError(
            f"Refusing to promote: model is in stage {candidate_stage!r}, not 'staging'. "
            "Only a staged, validated artifact can be promoted — register it and move it to "
            "staging first."
        )
    return "promote_and_archive_existing" if has_existing_production else "promote_no_existing_production"


def _move_artifact_dir(current_path: Path, new_parent: Path) -> Path:
    new_parent.mkdir(parents=True, exist_ok=True)
    destination = new_parent / current_path.name
    if destination.exists():
        raise PromotionRefusedError(f"Refusing to overwrite existing directory at {destination}.")
    shutil.move(str(current_path), str(destination))
    return destination


def promote(model_name: str, model_version: str, reviewed_by: str) -> dict:
    from datetime import datetime, timezone

    from sqlalchemy import select

    from app.database.database import SessionLocal
    from app.database.models.model_version import ModelStage, ModelVersion

    db = SessionLocal()
    try:
        candidate = db.scalar(
            select(ModelVersion).where(
                ModelVersion.model_name == model_name, ModelVersion.model_version == model_version
            )
        )
        if candidate is None:
            raise PromotionRefusedError(f"No registered model_versions row for {model_name} {model_version}. "
                                         "Run scripts/register_model_version.py against its staging artifact first.")

        existing_production = db.scalar(select(ModelVersion).where(ModelVersion.stage == ModelStage.PRODUCTION))
        plan = decide_promotion_plan(
            candidate_stage=candidate.stage.value,
            has_existing_production=existing_production is not None,
        )

        now = datetime.now(timezone.utc)
        archived_from: Optional[str] = None

        if plan == "promote_and_archive_existing":
            # Demote the OLD production row first — the DB's own
            # ux_model_versions_single_production partial unique index
            # would otherwise reject the candidate's promotion below.
            old_path = Path(existing_production.artifact_path)
            if old_path.exists():
                new_old_path = _move_artifact_dir(old_path, MODELS_ROOT / "archived")
                existing_production.artifact_path = str(new_old_path)
            existing_production.stage = ModelStage.ARCHIVED
            db.flush()
            archived_from = f"{existing_production.model_name} {existing_production.model_version}"

        candidate_path = Path(candidate.artifact_path)
        if candidate_path.exists():
            new_candidate_path = _move_artifact_dir(candidate_path, MODELS_ROOT / "production")
            candidate.artifact_path = str(new_candidate_path)

        candidate.stage = ModelStage.PRODUCTION
        candidate.promoted_at = now
        candidate.reviewed_by_role = reviewed_by
        candidate.reviewed_at = now
        candidate.review_status = "approved"
        db.commit()

        return {
            "promoted": f"{model_name} {model_version}",
            "archived": archived_from,
            "new_artifact_path": candidate.artifact_path,
        }
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("model_name")
    parser.add_argument("model_version")
    parser.add_argument("--reviewed-by", required=True, help="Real reviewer name/role — recorded verbatim, never inferred.")
    parser.add_argument("--confirm", action="store_true", help="Required — this makes a real, immediate change.")
    args = parser.parse_args()

    if not args.confirm:
        print("Refusing to run without --confirm — this promotes a model to production immediately.")
        return 1

    try:
        result = promote(args.model_name, args.model_version, args.reviewed_by)
    except PromotionRefusedError as exc:
        print(f"Refusing to promote: {exc}")
        return 1

    print(f"Promoted {result['promoted']} to production.")
    if result["archived"]:
        print(f"Archived previous production model: {result['archived']}")
    print(f"Artifact now at: {result['new_artifact_path']}")
    print()
    print("REMAINING MANUAL STEP: set MODEL_PATH in your .env to the path above and restart the backend "
          "process — app/ml/model_loader.py loads the production model once per process from a single fixed "
          "path (see its docstring); this script does not, and by design cannot, hot-swap a running process.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
