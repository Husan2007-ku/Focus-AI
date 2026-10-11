"""
Ichki monitoring (admin.py) uchun DB CRUD qatlami — Repository pattern
(TZ v2.0, 3-band).

Bu repository ataylab bir necha domenni (User, FocusSession, Organization)
birlashtiradi — chunki uning yagona vazifasi platforma bo'yicha umumiy
statistika yig'ish, alohida domenlarga tegishli biznes-qoidalarsiz. Bunday
maqsadli "faqat o'qish" agregatorlar boshqa repository'larda ham bor
(masalan `OrganizationRepository.get_focus_stats`).
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.focus_session import FocusSession, FocusSessionStatus
from app.models.organization import Organization
from app.models.user import User


class AdminRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def count_users(self) -> int:
        result = await self.db.execute(select(func.count(User.id)))
        return result.scalar_one()

    async def count_active_users(self) -> int:
        result = await self.db.execute(select(func.count(User.id)).where(User.is_active.is_(True)))
        return result.scalar_one()

    async def count_users_by_tier(self) -> dict[str, int]:
        result = await self.db.execute(
            select(User.subscription_tier, func.count(User.id)).group_by(User.subscription_tier)
        )
        return {tier.value: count for tier, count in result.all()}

    async def count_organizations(self) -> int:
        result = await self.db.execute(select(func.count(Organization.id)))
        return result.scalar_one()

    async def get_platform_focus_stats(self) -> tuple[int, int]:
        """(barcha foydalanuvchilar bo'yicha tugallangan seanslar soni, jami fokus daqiqasi)."""
        result = await self.db.execute(
            select(
                func.count(FocusSession.id),
                func.coalesce(func.sum(FocusSession.actual_duration_minutes), 0),
            ).where(FocusSession.status == FocusSessionStatus.COMPLETED)
        )
        return result.one()
