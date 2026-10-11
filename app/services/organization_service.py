"""
Tashkilot (B2B) biznes logikasi.

DB bilan ishlash `OrganizationRepository`ga o'tkazilgan (TZ v2.0, 3-band).
"""

import secrets

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.models.organization import Organization, OrganizationStatus
from app.models.user import User
from app.repositories.organization_repository import OrganizationRepository

logger = get_logger(__name__)


def _generate_invite_code() -> str:
    return secrets.token_urlsafe(6).replace("_", "").replace("-", "")[:8].upper()


class OrganizationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = OrganizationRepository(db)

    async def create_organization(
        self, admin_user: User, name: str, seat_limit: int
    ) -> Organization:
        if admin_user.organization_id is not None:
            raise ConflictError("Siz allaqachon bir tashkilotga tegishlisiz.")

        organization = Organization(
            name=name,
            invite_code=_generate_invite_code(),
            seat_limit=seat_limit,
            status=OrganizationStatus.ACTIVE,
            admin_user_id=admin_user.id,
        )
        organization = await self.repo.add(organization)

        admin_user.organization_id = organization.id
        await self.repo.commit()

        logger.info(
            "organization_created",
            organization_id=str(organization.id),
            admin_id=str(admin_user.id),
        )
        return organization

    async def join_organization(self, user: User, invite_code: str) -> Organization:
        if user.organization_id is not None:
            raise ConflictError("Siz allaqachon bir tashkilotga tegishlisiz. Avval undan chiqing.")

        organization = await self.repo.get_by_invite_code(invite_code.upper())

        if organization is None:
            raise NotFoundError("Taklif kodi noto'g'ri.")
        if organization.status != OrganizationStatus.ACTIVE:
            raise ConflictError("Bu tashkilot hozircha faol emas.")

        member_count = await self.repo.count_members(organization.id)
        if member_count >= organization.seat_limit:
            raise ConflictError("Tashkilotda bo'sh o'rin qolmagan.")

        user.organization_id = organization.id
        await self.repo.commit()

        logger.info(
            "user_joined_organization", user_id=str(user.id), organization_id=str(organization.id)
        )
        return organization

    async def leave_organization(self, user: User) -> None:
        if user.organization_id is None:
            raise ConflictError("Siz hech qanday tashkilotga tegishli emassiz.")

        user.organization_id = None
        await self.repo.commit()
        logger.info("user_left_organization", user_id=str(user.id))

    async def get_my_organization(self, user: User) -> Organization | None:
        if user.organization_id is None:
            return None
        return await self.repo.get_by_id(user.organization_id)

    async def get_stats(self, user: User) -> dict:
        organization = await self.get_my_organization(user)
        if organization is None:
            raise NotFoundError("Siz hech qanday tashkilotga tegishli emassiz.")
        if organization.admin_user_id != user.id:
            raise ForbiddenError("Faqat tashkilot admini statistikani ko'ra oladi.")

        member_count = await self.repo.count_members(organization.id)
        total_sessions, total_minutes = await self.repo.get_focus_stats(organization.id)
        average_streak = await self.repo.get_average_streak(organization.id)

        return {
            "member_count": member_count,
            "seat_limit": organization.seat_limit,
            "total_completed_sessions": total_sessions,
            "total_focus_minutes": total_minutes,
            "average_current_streak": round(average_streak, 1),
        }
