"""
Daily Routine endpoint'lari uchun sxemalar.
"""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.routine import RoutineStatus


class MorningPlanSchema(BaseModel):
    morning_plan: str = Field(..., min_length=1, max_length=2000)
    planned_focus_minutes: int | None = Field(default=None, ge=0, le=1440)


class EveningReportSchema(BaseModel):
    evening_report: str = Field(..., min_length=1, max_length=2000)
    self_rating: int = Field(..., ge=1, le=5)


class RoutineResponseSchema(BaseModel):
    id: uuid.UUID
    routine_date: date
    morning_plan: str | None
    planned_focus_minutes: int | None
    evening_report: str | None
    self_rating: int | None
    ai_feedback: str | None
    status: RoutineStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
