"""
Tashkilot (B2B) endpoint'lari.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.organization import (
    CreateOrganizationSchema,
    JoinOrganizationSchema,
    OrganizationResponseSchema,
    OrganizationStatsSchema,
)
from app.services.organization_service import OrganizationService

router = APIRouter()


@router.post("/", response_model=OrganizationResponseSchema, status_code=201)
async def create_organization(
    payload: CreateOrganizationSchema,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrganizationResponseSchema:
    """Yangi tashkilot yaratadi — joriy foydalanuvchi uning admini bo'ladi."""
    service = OrganizationService(db)
    organization = await service.create_organization(current_user, payload.name, payload.seat_limit)
    return OrganizationResponseSchema.model_validate(organization)


@router.post("/join", response_model=OrganizationResponseSchema)
async def join_organization(
    payload: JoinOrganizationSchema,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrganizationResponseSchema:
    """Taklif kodi orqali mavjud tashkilotga qo'shiladi."""
    service = OrganizationService(db)
    organization = await service.join_organization(current_user, payload.invite_code)
    return OrganizationResponseSchema.model_validate(organization)


@router.post("/leave", status_code=204)
async def leave_organization(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Joriy tashkilotdan chiqadi."""
    service = OrganizationService(db)
    await service.leave_organization(current_user)


@router.get("/me", response_model=OrganizationResponseSchema | None)
async def get_my_organization(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrganizationResponseSchema | None:
    """Joriy foydalanuvchi tegishli tashkilot ma'lumoti, agar bo'lmasa — `null`."""
    service = OrganizationService(db)
    organization = await service.get_my_organization(current_user)
    return OrganizationResponseSchema.model_validate(organization) if organization else None


@router.get("/stats", response_model=OrganizationStatsSchema)
async def get_organization_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrganizationStatsSchema:
    """Tashkilot statistikasi — faqat tashkilot admini uchun."""
    service = OrganizationService(db)
    stats = await service.get_stats(current_user)
    return OrganizationStatsSchema.model_validate(stats)
