"""
Admin portal API. Every route requires the ADMIN role (requirement #30:
"strict role-based authorization"). Responses are deliberately minimal —
admins see account/system metadata, never a user's raw health responses,
symptoms, or screening explanations (requirement #30/#40).
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models.assessment import Assessment, Prediction
from app.database.models.audit_log import AuditLog
from app.database.models.model_version import ModelVersion
from app.database.models.user import User
from app.ml.model_loader import load_production_model
from app.security.dependencies import require_admin
from app.services.monitoring_service import DEFAULT_WINDOW_DAYS, get_monitoring_snapshot

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users")
def list_users(
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    stmt = select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
    users = db.scalars(stmt).all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "role": u.role.value,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat(),
        }
        for u in users
    ]


@router.get("/models")
def list_models(db: Session = Depends(get_db), _admin=Depends(require_admin)):
    stmt = select(ModelVersion).order_by(ModelVersion.created_at.desc())
    versions = db.scalars(stmt).all()
    return [
        {
            "id": v.id,
            "model_name": v.model_name,
            "model_version": v.model_version,
            "stage": v.stage.value,
            "evaluation_metrics": v.evaluation_metrics,
            "calibration_method": v.calibration_method,
            "dataset_version": v.dataset_version,
            "review_status": v.review_status,
            "training_date": v.training_date.isoformat(),
            "promoted_at": v.promoted_at.isoformat() if v.promoted_at else None,
        }
        for v in versions
    ]


@router.get("/system-health")
def system_health(db: Session = Depends(get_db), _admin=Depends(require_admin)):
    db_ok = True
    try:
        db.execute(select(func.count()).select_from(User))
    except Exception:
        db_ok = False

    loaded_model = load_production_model()

    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "database_reachable": db_ok,
        "production_model_loaded": loaded_model is not None,
        "production_model_version": loaded_model.metadata.model_version if loaded_model else None,
        "total_users": db.scalar(select(func.count()).select_from(User)),
        "total_assessments": db.scalar(select(func.count()).select_from(Assessment)),
        "total_predictions": db.scalar(select(func.count()).select_from(Prediction)),
    }


@router.get("/monitoring")
def monitoring_snapshot(
    window_days: int = Query(default=DEFAULT_WINDOW_DAYS, ge=1, le=365),
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    """Prediction distribution, missing-data rate, model-version breakdown,
    inference errors/latency, and a drift signal against the loaded model's
    own training-time class balance. Admin-only (requirement: RBAC-restricted
    model monitoring). Never returns raw health responses — only aggregate
    counts/rates, same "account/system metadata only" boundary the rest of
    this router keeps (see module docstring)."""
    return get_monitoring_snapshot(db, window_days=window_days)


@router.get("/audit-logs")
def audit_logs(
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
    logs = db.scalars(stmt).all()
    return [
        {
            "id": log.id,
            "actor_user_id": log.actor_user_id,
            "actor_role": log.actor_role,
            "action": log.action,
            "target_type": log.target_type,
            "target_id": log.target_id,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]
