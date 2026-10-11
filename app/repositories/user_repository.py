"""
User uchun DB CRUD qatlami — Repository pattern (TZ v2.0, 3-band).

`AuthService` va `get_current_user` dependency shu orqali ishlaydi — DB
so'rovi bir joyda, ikki marta yozilmagan.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_phone(self, phone_number: str) -> User | None:
        result = await self.db.execute(select(User).where(User.phone_number == phone_number))
        return result.scalar_one_or_none()

    async def get_by_google_id(self, google_id: str) -> User | None:
        result = await self.db.execute(select(User).where(User.google_id == google_id))
        return result.scalar_one_or_none()

    async def create(self, user: User) -> User:
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def save(self, user: User) -> User:
        """Chaqiruvchi tomonidan oldin o'zgartirilgan (masalan profil maydonlari)
        obyektni saqlaydi."""
        await self.db.commit()
        await self.db.refresh(user)
        return user

    # ── Admin monitoring uchun agregatsiyalar ──────────────────
    async def count_all(self) -> int:
        result = await self.db.execute(select(func.count(User.id)))
        return result.scalar_one()

    async def count_active(self) -> int:
        result = await self.db.execute(select(func.count(User.id)).where(User.is_active.is_(True)))
        return result.scalar_one()

    async def list_active_ids(self) -> list[uuid.UUID]:
        """Kunlik/haftalik fon vazifalari (`daily_tasks.py`, `ai_tasks.py`)
        uchun — barcha faol foydalanuvchi ID'lari."""
        result = await self.db.execute(select(User.id).where(User.is_active.is_(True)))
        return list(result.scalars().all())

    async def count_by_tier(self) -> dict[str, int]:
        result = await self.db.execute(
            select(User.subscription_tier, func.count(User.id)).group_by(User.subscription_tier)
        )
        return {tier.value: count for tier, count in result.all()}
