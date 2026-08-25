"""
Tashkilot (B2B) endpoint'lari uchun sxemalar.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.organization import OrganizationStatus


class CreateOrganizationSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    seat_limit: int = Field(default=50, ge=1, le=10000)


class JoinOrganizationSchema(BaseModel):
    invite_code: str = Field(..., min_length=1, max_length=32)


class OrganizationResponseSchema(BaseModel):
    id: uuid.UUID
    name: str
    invite_code: str
    seat_limit: int
    status: OrganizationStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class OrganizationStatsSchema(BaseModel):
    member_count: int
    seat_limit: int
    total_completed_sessions: int
    total_focus_minutes: int
    average_current_streak: float
