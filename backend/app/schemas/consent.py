from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.database.models.consent import ConsentType


class ConsentSubmitRequest(BaseModel):
    consent_type: ConsentType
    accepted: bool
    consent_version: str
    policy_version: str
    app_version: str


class ConsentResponse(BaseModel):
    id: str
    consent_type: ConsentType
    consent_version: str
    policy_version: str
    app_version: str
    accepted: bool
    accepted_at: datetime | None
    withdrawn_at: datetime | None

    class Config:
        from_attributes = True


class ConsentWithdrawRequest(BaseModel):
    consent_type: ConsentType
