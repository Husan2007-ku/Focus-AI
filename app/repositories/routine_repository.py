"""
Daily Routine uchun DB CRUD qatlami — Repository pattern (TZ v2.0, 3-band).
"""

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.routine import DailyRoutine


class RoutineRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def add(self, routine: DailyRoutine) -> DailyRoutine:
        self.db.add(routine)
        await self.db.commit()
        await self.db.refresh(routine)
        return routine

    async def save(self, routine: DailyRoutine) -> DailyRoutine:
        """Mavjud routine'ga qilingan o'zgarishlarni saqlaydi (yangi qator qo'shmaydi)."""
        await self.db.commit()
        await self.db.refresh(routine)
        return routine

    async def get_by_date(self, user_id: uuid.UUID, routine_date: date) -> DailyRoutine | None:
        result = await self.db.execute(
            select(DailyRoutine).where(
                DailyRoutine.user_id == user_id, DailyRoutine.routine_date == routine_date
            )
        )
        return result.scalar_one_or_none()

    async def list_for_user(
        self, user_id: uuid.UUID, limit: int, offset: int
    ) -> list[DailyRoutine]:
        result = await self.db.execute(
            select(DailyRoutine)
            .where(DailyRoutine.user_id == user_id)
            .order_by(DailyRoutine.routine_date.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())
