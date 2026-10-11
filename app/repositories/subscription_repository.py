"""
Obuna (Premium/Yillik) uchun DB CRUD qatlami — Repository pattern (TZ v2.0, 3-band).
"""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.subscription import Subscription
from app.models.user import User


class SubscriptionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def add(self, subscription: Subscription) -> Subscription:
        self.db.add(subscription)
        await self.db.commit()
        await self.db.refresh(subscription)
        return subscription

    async def commit(self) -> None:
        """Chaqiruvchi tomonidan oldin o'zgartirilgan obyektlarni saqlaydi."""
        await self.db.commit()

    async def get_by_id(self, subscription_id: uuid.UUID) -> Subscription | None:
        result = await self.db.execute(
            select(Subscription).where(Subscription.id == subscription_id)
        )
        return result.scalar_one_or_none()

    async def get_active_for_user(
        self, user_id: uuid.UUID, now: datetime, exclude_id: uuid.UUID | None = None
    ) -> Subscription | None:
        stmt = select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.is_active.is_(True),
            Subscription.expires_at > now,
        )
        if exclude_id is not None:
            stmt = stmt.where(Subscription.id != exclude_id)
        stmt = stmt.order_by(Subscription.expires_at.desc())

        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        """`_sync_user_tier` uchun — Subscription domenidan User'ga yagona murojaat."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()
