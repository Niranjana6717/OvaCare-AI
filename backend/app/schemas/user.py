from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class ProfileUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)
    date_of_birth: date | None = None
    height_cm: float | None = Field(default=None, gt=0, lt=272)
    weight_kg: float | None = Field(default=None, gt=0, lt=500)
    country: str | None = Field(default=None, max_length=100)
    phone: str | None = Field(default=None, max_length=30)
    timezone: str | None = None


class ProfileResponse(BaseModel):
    email: str
    full_name: str | None
    date_of_birth: date | None
    height_cm: float | None
    weight_kg: float | None
    bmi: float | None
    country: str | None
    phone: str | None
    timezone: str

    class Config:
        from_attributes = True
