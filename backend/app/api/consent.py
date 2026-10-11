from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models.user import User
from app.schemas.consent import ConsentResponse, ConsentSubmitRequest, ConsentWithdrawRequest
from app.security.dependencies import get_current_user
from app.services import consent_service

router = APIRouter(prefix="/consent", tags=["consent"])


@router.get("", response_model=list[ConsentResponse])
def get_consents(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return consent_service.get_active_consents(db, user.id)


@router.post("", response_model=ConsentResponse, status_code=status.HTTP_201_CREATED)
def submit_consent(
    payload: ConsentSubmitRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    record = consent_service.record_consent(
        db,
        user_id=user.id,
        consent_type=payload.consent_type,
        accepted=payload.accepted,
        consent_version=payload.consent_version,
        policy_version=payload.policy_version,
        app_version=payload.app_version,
    )
    db.commit()
    return record


@router.put("/{consent_type}", response_model=ConsentResponse)
def withdraw_consent(
    consent_type: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    from app.database.models.consent import ConsentType

    try:
        ct = ConsentType(consent_type)
        record = consent_service.withdraw_consent(db, user.id, ct)
    except consent_service.RequiredConsentWithdrawalError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    db.commit()
    return record
