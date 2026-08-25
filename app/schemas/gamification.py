"""
Gamification endpoint'lari uchun sxemalar.
"""

from datetime import datetime

from pydantic import BaseModel

from app.models.gamification import BadgeCode


class BadgeSchema(BaseModel):
    badge_code: BadgeCode
    earned_at: datetime

    model_config = {"from_attributes": True}


class GamificationSummarySchema(BaseModel):
    current_streak: int
    longest_streak: int
    total_xp: int
    badges: list[BadgeSchema]
