"""
Gamification uchun DB CRUD qatlami — Repository pattern (TZ v2.0, 3-band).
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gamification import BadgeCode, UserBadge, UserStreak, XPTransaction


class GamificationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── XPTransaction ────────────────────────────────────────
    async def add_xp_transaction(self, transaction: XPTransaction) -> None:
        self.db.add(transaction)
        await self.db.commit()

    async def sum_xp_for_user(self, user_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.coalesce(func.sum(XPTransaction.amount), 0)).where(
                XPTransaction.user_id == user_id
            )
        )
        return result.scalar_one()

    # ── UserStreak ───────────────────────────────────────────
    async def get_streak(self, user_id: uuid.UUID) -> UserStreak | None:
        result = await self.db.execute(select(UserStreak).where(UserStreak.user_id == user_id))
        return result.scalar_one_or_none()

    async def add_streak(self, streak: UserStreak) -> UserStreak:
        self.db.add(streak)
        await self.db.commit()
        await self.db.refresh(streak)
        return streak

    async def save_streak(self, streak: UserStreak) -> None:
        await self.db.commit()

    # ── UserBadge ────────────────────────────────────────────
    async def get_badge(self, user_id: uuid.UUID, badge_code: BadgeCode) -> UserBadge | None:
        result = await self.db.execute(
            select(UserBadge).where(
                UserBadge.user_id == user_id, UserBadge.badge_code == badge_code
            )
        )
        return result.scalar_one_or_none()

    async def add_badge(self, badge: UserBadge) -> None:
        self.db.add(badge)
        await self.db.commit()

    async def list_badges_for_user(self, user_id: uuid.UUID) -> list[UserBadge]:
        result = await self.db.execute(
            select(UserBadge).where(UserBadge.user_id == user_id).order_by(UserBadge.earned_at)
        )
        return list(result.scalars().all())
