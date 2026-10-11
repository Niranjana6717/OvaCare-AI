from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models.notification import NotificationPreference
from app.database.models.user import User
from app.schemas.notification import NotificationPreferenceRequest, NotificationPreferenceResponse
from app.security.dependencies import get_current_user

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/preferences", response_model=NotificationPreferenceResponse)
def get_preferences(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    pref = user.notification_preference
    if pref is None:
        pref = NotificationPreference(user_id=user.id)
        db.add(pref)
        db.commit()
        db.refresh(pref)
    return pref


@router.put("/preferences", response_model=NotificationPreferenceResponse)
def update_preferences(
    payload: NotificationPreferenceRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    pref = user.notification_preference
    if pref is None:
        pref = NotificationPreference(user_id=user.id)
        db.add(pref)

    for field, value in payload.model_dump().items():
        setattr(pref, field, value)

    db.commit()
    db.refresh(pref)
    return pref
