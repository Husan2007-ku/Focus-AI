"""
Shaxsiy statistika va haftalik AI xulosa endpoint'lari.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.stats import StatsSummarySchema, WeeklyAISummarySchema
from app.services.stats_service import StatsService

router = APIRouter()


@router.get("/summary", response_model=StatsSummarySchema)
async def get_stats_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StatsSummarySchema:
    """Foydalanuvchining jami va joriy haftalik fokus statistikasi, streak, XP."""
    service = StatsService(db)
    summary = await service.get_summary(current_user)
    return StatsSummarySchema.model_validate(summary)


@router.get("/weekly-ai-summary", response_model=WeeklyAISummarySchema)
async def get_weekly_ai_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WeeklyAISummarySchema:
    """Joriy hafta uchun AI tomonidan generatsiya qilingan qisqa xulosa va maslahat."""
    service = StatsService(db)
    summary = await service.get_weekly_ai_summary(current_user)
    return WeeklyAISummarySchema.model_validate(summary)
