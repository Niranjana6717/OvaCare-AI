from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models.assessment import Assessment, Prediction
from app.database.models.consent import ConsentType
from app.database.models.user import User
from app.schemas.assessment import AssessmentSubmitResponse, PredictionResultResponse, SafetyCheckResponse
from app.security.dependencies import get_current_user
from app.services.assessment_service import run_safety_and_prediction
from app.services.consent_service import is_consent_active
from app.services.prediction_service import build_result_payload

router = APIRouter(prefix="/predictions", tags=["predictions"])


class PredictionRequest(BaseModel):
    assessment_id: str


@router.post("", response_model=AssessmentSubmitResponse, status_code=status.HTTP_201_CREATED)
def create_prediction(
    payload: PredictionRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    if not is_consent_active(db, user.id, ConsentType.AI_SCREENING_ACKNOWLEDGEMENT):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="AI screening acknowledgement consent is required before requesting a screening result.",
        )

    assessment = db.get(Assessment, payload.assessment_id)
    if assessment is None or assessment.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found.")
    if assessment.prediction is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A prediction already exists for this assessment. Submit a new assessment for a new screening.",
        )

    prediction, safety_result = run_safety_and_prediction(db, assessment)
    db.commit()
    db.refresh(prediction)

    return AssessmentSubmitResponse(
        assessment_id=assessment.id,
        safety=SafetyCheckResponse(
            urgent=safety_result.urgent,
            message=safety_result.message,
            triggered_rule_ids=safety_result.triggered_rule_ids,
        ),
        result=PredictionResultResponse(**build_result_payload(prediction)),
    )


@router.get("/history", response_model=list[PredictionResultResponse])
def prediction_history(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stmt = select(Prediction).where(Prediction.user_id == user.id).order_by(Prediction.created_at.desc())
    predictions = db.scalars(stmt).all()
    return [PredictionResultResponse(**build_result_payload(p)) for p in predictions]
