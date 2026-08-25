"""
Focus Session endpoint'lari uchun request/response sxemalari.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.focus_session import FocusSessionStatus


class FocusSessionStartSchema(BaseModel):
    planned_duration_minutes: int = Field(..., ge=1, le=480, description="1 daqiqadan 8 soatgacha")
    blocked_apps: list[str] | None = Field(
        default=None, description="Bloklanadigan ilovalar paket nomlari"
    )


class FocusSessionResponseSchema(BaseModel):
    id: uuid.UUID
    planned_duration_minutes: int
    actual_duration_minutes: int | None
    status: FocusSessionStatus
    blocked_apps: list[str] | None
    started_at: datetime
    ended_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class FocusSessionHistorySchema(BaseModel):
    items: list[FocusSessionResponseSchema]
    total: int
