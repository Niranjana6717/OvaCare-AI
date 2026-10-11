from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models.assessment import Assessment
from app.database.models.consent import ConsentType
from app.database.models.user import User
from app.schemas.assessment import AssessmentSubmitRequest
from app.security.dependencies import get_current_user
from app.services.assessment_service import create_assessment
from app.services.consent_service import is_consent_active

router = APIRouter(prefix="/assessments", tags=["assessments"])


@router.post("", status_code=status.HTTP_201_CREATED)
def submit_assessment_answers(
    payload: AssessmentSubmitRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not is_consent_active(db, user.id, ConsentType.HEALTH_DATA_PROCESSING):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Health data processing consent is required before submitting an assessment.",
        )

    assessment = create_assessment(
        db, user.id, payload.to_raw_responses(), payload.unanswered_fields
    )
    db.commit()
    return {
        "assessment_id": assessment.id,
        "submitted_at": assessment.submitted_at.isoformat(),
        "responses": assessment.raw_responses,
        "unanswered_fields": assessment.unanswered_fields,
    }


@router.get("")
def list_assessments(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stmt = select(Assessment).where(Assessment.user_id == user.id).order_by(Assessment.submitted_at.desc())
    assessments = db.scalars(stmt).all()
    return [
        {
            "assessment_id": a.id,
            "submitted_at": a.submitted_at.isoformat(),
            "has_prediction": a.prediction is not None,
        }
        for a in assessments
    ]


@router.get("/{assessment_id}")
def get_assessment(assessment_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    assessment = db.get(Assessment, assessment_id)
    if assessment is None or assessment.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found.")
    return {
        "assessment_id": assessment.id,
        "submitted_at": assessment.submitted_at.isoformat(),
        "responses": assessment.raw_responses,
        "unanswered_fields": assessment.unanswered_fields,
        "has_prediction": assessment.prediction is not None,
    }
