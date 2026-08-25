"""
Daily Routine endpoint'lari.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.routine import EveningReportSchema, MorningPlanSchema, RoutineResponseSchema
from app.services.routine_service import RoutineService

router = APIRouter()


@router.post("/morning-plan", response_model=RoutineResponseSchema)
async def submit_morning_plan(
    payload: MorningPlanSchema,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RoutineResponseSchema:
    """Bugungi kun uchun ertalabki rejani kiritadi (yoki yangilaydi)."""
    service = RoutineService(db)
    routine = await service.submit_morning_plan(current_user, payload)
    return RoutineResponseSchema.model_validate(routine)


@router.post("/evening-report", response_model=RoutineResponseSchema)
async def submit_evening_report(
    payload: EveningReportSchema,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RoutineResponseSchema:
    """
    Bugungi kun uchun kechqurungi hisobotni kiritadi va AI fikrini generatsiya qiladi.
    Avval shu kunga ertalabki reja kiritilgan bo'lishi shart.
    """
    service = RoutineService(db)
    routine = await service.submit_evening_report(current_user, payload)
    return RoutineResponseSchema.model_validate(routine)


@router.get("/today", response_model=RoutineResponseSchema | None)
async def get_today_routine(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RoutineResponseSchema | None:
    """Bugungi kunlik yozuvni qaytaradi, agar hali kiritilmagan bo'lsa — `null`."""
    service = RoutineService(db)
    routine = await service.get_today(current_user)
    return RoutineResponseSchema.model_validate(routine) if routine else None


@router.get("/history", response_model=list[RoutineResponseSchema])
async def get_routine_history(
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[RoutineResponseSchema]:
    """Foydalanuvchining kunlik yozuvlar tarixi (eng yangisidan boshlab)."""
    service = RoutineService(db)
    routines = await service.get_history(current_user, limit, offset)
    return [RoutineResponseSchema.model_validate(r) for r in routines]
