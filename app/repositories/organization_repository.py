"""
Tashkilot (B2B) uchun DB CRUD qatlami — Repository pattern (TZ v2.0, 3-band).
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.focus_session import FocusSession, FocusSessionStatus
from app.models.gamification import UserStreak
from app.models.organization import Organization
from app.models.user import User


class OrganizationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def add(self, organization: Organization) -> Organization:
        self.db.add(organization)
        await self.db.commit()
        await self.db.refresh(organization)
        return organization

    async def commit(self) -> None:
        """Chaqiruvchi tomonidan oldin o'zgartirilgan obyektlarni (masalan
        `user.organization_id`) saqlaydi."""
        await self.db.commit()

    async def get_by_id(self, organization_id: uuid.UUID) -> Organization | None:
        result = await self.db.execute(
            select(Organization).where(Organization.id == organization_id)
        )
        return result.scalar_one_or_none()

    async def get_by_invite_code(self, invite_code: str) -> Organization | None:
        result = await self.db.execute(
            select(Organization).where(Organization.invite_code == invite_code)
        )
        return result.scalar_one_or_none()

    async def count_members(self, organization_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count(User.id)).where(User.organization_id == organization_id)
        )
        return result.scalar_one()

    async def get_focus_stats(self, organization_id: uuid.UUID) -> tuple[int, int]:
        """(tugallangan seanslar soni, jami fokus daqiqasi) — tashkilot a'zolari bo'yicha."""
        result = await self.db.execute(
            select(
                func.count(FocusSession.id),
                func.coalesce(func.sum(FocusSession.actual_duration_minutes), 0),
            )
            .join(User, User.id == FocusSession.user_id)
            .where(
                User.organization_id == organization_id,
                FocusSession.status == FocusSessionStatus.COMPLETED,
            )
        )
        return result.one()

    async def get_average_streak(self, organization_id: uuid.UUID) -> float:
        result = await self.db.execute(
            select(func.coalesce(func.avg(UserStreak.current_streak), 0))
            .join(User, User.id == UserStreak.user_id)
            .where(User.organization_id == organization_id)
        )
        return float(result.scalar_one())
