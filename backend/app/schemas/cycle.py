from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, model_validator

from app.database.models.cycle import FlowLevel


class CycleCreateRequest(BaseModel):
    start_date: date
    end_date: date | None = None
    flow_level: FlowLevel | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def check_dates(self) -> "CycleCreateRequest":
        if self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date cannot be before start_date.")
        return self


class CycleUpdateRequest(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    flow_level: FlowLevel | None = None
    notes: str | None = Field(default=None, max_length=2000)


class CycleResponse(BaseModel):
    id: str
    start_date: date
    end_date: date | None
    flow_level: FlowLevel | None
    cycle_length_days: int | None
    period_duration_days: int | None
    notes: str | None

    class Config:
        from_attributes = True


class CycleSummaryResponse(BaseModel):
    sufficient_data: bool
    message: str | None
    average_cycle_length_days: float | None
    average_period_duration_days: float | None
    cycle_variability_stdev_days: float | None
    is_high_variability: bool
    history: list[CycleResponse]


class CycleEstimateResponse(BaseModel):
    sufficient_data: bool
    message: str | None
    estimated_start_date: date | None
    based_on_cycle_count: int
    label: str = "Estimated next period"
