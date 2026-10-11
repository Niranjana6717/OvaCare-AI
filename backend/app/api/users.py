from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models.user import User
from app.schemas.auth import MessageResponse
from app.schemas.user import ProfileResponse, ProfileUpdateRequest
from app.security.dependencies import get_current_user
from app.services import auth_service
from app.services.audit_service import log_event

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=ProfileResponse)
def get_me(user: User = Depends(get_current_user)):
    profile = user.profile
    return ProfileResponse(
        email=user.email,
        full_name=profile.full_name if profile else None,
        date_of_birth=profile.date_of_birth if profile else None,
        height_cm=profile.height_cm if profile else None,
        weight_kg=profile.weight_kg if profile else None,
        bmi=profile.bmi if profile else None,
        country=profile.country if profile else None,
        phone=profile.phone if profile else None,
        timezone=profile.timezone if profile else "UTC",
    )


@router.put("/me", response_model=ProfileResponse)
def update_me(
    payload: ProfileUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = user.profile
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)

    return ProfileResponse(
        email=user.email,
        full_name=profile.full_name,
        date_of_birth=profile.date_of_birth,
        height_cm=profile.height_cm,
        weight_kg=profile.weight_kg,
        bmi=profile.bmi,
        country=profile.country,
        phone=profile.phone,
        timezone=profile.timezone,
    )


@router.delete("/me", response_model=MessageResponse, status_code=status.HTTP_200_OK)
def delete_me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Requirement #86: account deletion, explicit and confirmable client-side
    (the client is expected to present its own "are you sure" confirmation
    before calling this — this endpoint performs the deletion itself, it
    does not ask again). Soft-deletes; see auth_service.delete_account for
    what that means and why."""
    auth_service.delete_account(db, user)
    log_event(db, action="user.delete_account", actor_user_id=user.id, actor_role=user.role.value)
    db.commit()
    return {"message": "Your account has been deactivated and your data marked for deletion."}
