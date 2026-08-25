"""
Gamification endpoint'i — faqat o'qish uchun (yozish ichki servislar orqali bo'ladi).
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.gamification import GamificationSummarySchema
from app.services.gamification_service import GamificationService

router = APIRouter()


@router.get("/summary", response_model=GamificationSummarySchema)
async def get_gamification_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GamificationSummarySchema:
    """Foydalanuvchining joriy streak, jami XP va qo'lga kiritgan badge'lari."""
    service = GamificationService(db)
    summary = await service.get_summary(current_user.id)
    return GamificationSummarySchema.model_validate(summary)
