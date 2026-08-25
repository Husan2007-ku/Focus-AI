"""
Tashkilot (B2B) biznes logikasi.
"""

import secrets

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.models.focus_session import FocusSession, FocusSessionStatus
from app.models.gamification import UserStreak
from app.models.organization import Organization, OrganizationStatus
from app.models.user import User

logger = get_logger(__name__)


def _generate_invite_code() -> str:
    return secrets.token_urlsafe(6).replace("_", "").replace("-", "")[:8].upper()


class OrganizationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_organization(self, admin_user: User, name: str, seat_limit: int) -> Organization:
        if admin_user.organization_id is not None:
            raise ConflictError("Siz allaqachon bir tashkilotga tegishlisiz.")

        organization = Organization(
            name=name,
            invite_code=_generate_invite_code(),
            seat_limit=seat_limit,
            status=OrganizationStatus.ACTIVE,
            admin_user_id=admin_user.id,
        )
        self.db.add(organization)
        await self.db.commit()
        await self.db.refresh(organization)

        admin_user.organization_id = organization.id
        await self.db.commit()

        logger.info("organization_created", organization_id=str(organization.id), admin_id=str(admin_user.id))
        return organization

    async def join_organization(self, user: User, invite_code: str) -> Organization:
        if user.organization_id is not None:
            raise ConflictError("Siz allaqachon bir tashkilotga tegishlisiz. Avval undan chiqing.")

        result = await self.db.execute(
            select(Organization).where(Organization.invite_code == invite_code.upper())
        )
        organization = result.scalar_one_or_none()

        if organization is None:
            raise NotFoundError("Taklif kodi noto'g'ri.")
        if organization.status != OrganizationStatus.ACTIVE:
            raise ConflictError("Bu tashkilot hozircha faol emas.")

        member_count = await self._count_members(organization.id)
        if member_count >= organization.seat_limit:
            raise ConflictError("Tashkilotda bo'sh o'rin qolmagan.")

        user.organization_id = organization.id
        await self.db.commit()

        logger.info("user_joined_organization", user_id=str(user.id), organization_id=str(organization.id))
        return organization

    async def leave_organization(self, user: User) -> None:
        if user.organization_id is None:
            raise ConflictError("Siz hech qanday tashkilotga tegishli emassiz.")

        user.organization_id = None
        await self.db.commit()
        logger.info("user_left_organization", user_id=str(user.id))

    async def get_my_organization(self, user: User) -> Organization | None:
        if user.organization_id is None:
            return None
        result = await self.db.execute(select(Organization).where(Organization.id == user.organization_id))
        return result.scalar_one_or_none()

    async def get_stats(self, user: User) -> dict:
        organization = await self.get_my_organization(user)
        if organization is None:
            raise NotFoundError("Siz hech qanday tashkilotga tegishli emassiz.")
        if organization.admin_user_id != user.id:
            raise ForbiddenError("Faqat tashkilot admini statistikani ko'ra oladi.")

        member_count = await self._count_members(organization.id)

        sessions_result = await self.db.execute(
            select(
                func.count(FocusSession.id),
                func.coalesce(func.sum(FocusSession.actual_duration_minutes), 0),
            )
            .join(User, User.id == FocusSession.user_id)
            .where(
                User.organization_id == organization.id,
                FocusSession.status == FocusSessionStatus.COMPLETED,
            )
        )
        total_sessions, total_minutes = sessions_result.one()

        streak_result = await self.db.execute(
            select(func.coalesce(func.avg(UserStreak.current_streak), 0))
            .join(User, User.id == UserStreak.user_id)
            .where(User.organization_id == organization.id)
        )
        average_streak = float(streak_result.scalar_one())

        return {
            "member_count": member_count,
            "seat_limit": organization.seat_limit,
            "total_completed_sessions": total_sessions,
            "total_focus_minutes": total_minutes,
            "average_current_streak": round(average_streak, 1),
        }

    # ── Ichki yordamchi metodlar ─────────────────────────────
    async def _count_members(self, organization_id) -> int:
        result = await self.db.execute(
            select(func.count(User.id)).where(User.organization_id == organization_id)
        )
        return result.scalar_one()
