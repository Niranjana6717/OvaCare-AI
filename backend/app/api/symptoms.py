from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models.symptom import Symptom
from app.database.models.user import User
from app.schemas.symptom import SymptomCreateRequest, SymptomResponse, SymptomUpdateRequest
from app.security.dependencies import get_current_user
from app.services.symptom_service import list_symptoms

router = APIRouter(prefix="/symptoms", tags=["symptoms"])


def _get_owned_symptom(db: Session, user_id: str, symptom_id: str) -> Symptom:
    record = db.get(Symptom, symptom_id)
    if record is None or record.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Symptom entry not found.")
    return record


@router.post("", response_model=SymptomResponse, status_code=status.HTTP_201_CREATED)
def create_symptom(
    payload: SymptomCreateRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    record = Symptom(user_id=user.id, **payload.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get("", response_model=list[SymptomResponse])
def get_symptoms(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return list_symptoms(db, user.id)


@router.put("/{symptom_id}", response_model=SymptomResponse)
def update_symptom(
    symptom_id: str,
    payload: SymptomUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record = _get_owned_symptom(db, user.id, symptom_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(record, field, value)
    db.commit()
    db.refresh(record)
    return record


@router.delete("/{symptom_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_symptom(symptom_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    record = _get_owned_symptom(db, user.id, symptom_id)
    db.delete(record)
    db.commit()
