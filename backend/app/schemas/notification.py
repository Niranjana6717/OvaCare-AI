from __future__ import annotations

from datetime import time
from typing import Literal

from pydantic import BaseModel, Field


class NotificationPreferenceRequest(BaseModel):
    period_reminders_enabled: bool = False
    days_before_period: Literal[1, 2, 3, 5] = 2
    notification_time: time = time(8, 0)
    cycle_reminders_enabled: bool = False
    symptom_reminders_enabled: bool = False
    privacy_mode: bool = True
    timezone: str = "UTC"


class NotificationPreferenceResponse(NotificationPreferenceRequest):
    class Config:
        from_attributes = True
