from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models.user import User
from app.security.dependencies import get_current_user
from app.services.recommendation_service import get_insights

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("")
def read_insights(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return get_insights(db, user.id)
