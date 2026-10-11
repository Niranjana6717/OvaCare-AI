from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, model_validator

from app.database.models.symptom import SymptomType


class SymptomCreateRequest(BaseModel):
    symptom_type: SymptomType
    custom_label: str | None = Field(default=None, max_length=120)
    severity: int = Field(ge=1, le=5)
    logged_date: date
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def check_custom_label(self) -> "SymptomCreateRequest":
        if self.symptom_type == SymptomType.OTHER and not self.custom_label:
            raise ValueError("custom_label is required when symptom_type is 'other'.")
        return self


class SymptomUpdateRequest(BaseModel):
    severity: int | None = Field(default=None, ge=1, le=5)
    notes: str | None = Field(default=None, max_length=2000)


class SymptomResponse(BaseModel):
    id: str
    symptom_type: SymptomType
    custom_label: str | None
    severity: int
    logged_date: date
    notes: str | None

    class Config:
        from_attributes = True
