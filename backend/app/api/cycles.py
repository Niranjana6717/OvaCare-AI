from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models.cycle import CycleRecord
from app.database.models.user import User
from app.schemas.cycle import (
    CycleCreateRequest,
    CycleEstimateResponse,
    CycleResponse,
    CycleSummaryResponse,
    CycleUpdateRequest,
)
from app.security.dependencies import get_current_user
from app.services.cycle_service import estimate_next_period, get_cycle_summary, recompute_derived_fields

router = APIRouter(prefix="/cycles", tags=["cycles"])


def _get_owned_cycle(db: Session, user_id: str, cycle_id: str) -> CycleRecord:
    record = db.get(CycleRecord, cycle_id)
    if record is None or record.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cycle record not found.")
    return record


@router.post("", response_model=CycleResponse, status_code=status.HTTP_201_CREATED)
def create_cycle(
    payload: CycleCreateRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    record = CycleRecord(user_id=user.id, **payload.model_dump())
    db.add(record)
    db.flush()
    recompute_derived_fields(db, user.id)
    db.commit()
    db.refresh(record)
    return record


@router.get("", response_model=list[CycleResponse])
def list_cycles(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stmt = select(CycleRecord).where(CycleRecord.user_id == user.id).order_by(CycleRecord.start_date.desc())
    return list(db.scalars(stmt).all())


@router.get("/summary", response_model=CycleSummaryResponse)
def cycle_summary(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    summary, history = get_cycle_summary(db, user.id)
    return CycleSummaryResponse(
        sufficient_data=summary.sufficient_data,
        message=summary.message,
        average_cycle_length_days=summary.average_cycle_length_days,
        average_period_duration_days=summary.average_period_duration_days,
        cycle_variability_stdev_days=summary.cycle_variability_stdev_days,
        is_high_variability=summary.is_high_variability,
        history=history,
    )


@router.get("/estimate", response_model=CycleEstimateResponse)
def cycle_estimate(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    estimate = estimate_next_period(db, user.id)
    return CycleEstimateResponse(
        sufficient_data=estimate.sufficient_data,
        message=estimate.message,
        estimated_start_date=estimate.estimated_start_date,
        based_on_cycle_count=estimate.based_on_cycle_count,
    )


@router.get("/{cycle_id}", response_model=CycleResponse)
def get_cycle(cycle_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _get_owned_cycle(db, user.id, cycle_id)


@router.put("/{cycle_id}", response_model=CycleResponse)
def update_cycle(
    cycle_id: str,
    payload: CycleUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record = _get_owned_cycle(db, user.id, cycle_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(record, field, value)
    db.flush()
    recompute_derived_fields(db, user.id)
    db.commit()
    db.refresh(record)
    return record


@router.delete("/{cycle_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cycle(cycle_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    record = _get_owned_cycle(db, user.id, cycle_id)
    db.delete(record)
    db.flush()
    recompute_derived_fields(db, user.id)
    db.commit()
