"""
Kunlik fon vazifalari (`app/tasks/daily_tasks.py`) uchun DB CRUD qatlami —
Repository pattern (TZ v2.0, 3-band).

Bu ham (`AdminRepository` kabi) ataylab bir necha domenni birlashtiruvchi
maqsadli agregator — kunlik Celery vazifalari uchun.
"""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.focus_session import FocusSession, FocusSessionStatus
from app.models.gamification import UserStreak
from app.models.user import User


class DailyTasksRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Streak reset ─────────────────────────────────────────
    async def list_stale_streaks(self, cutoff_date: datetime) -> list[UserStreak]:
        """`current_streak > 0` bo'lgan, lekin `cutoff_date`dan beri faol
        bo'lmagan (ya'ni kechagi kun o'tkazib yuborilgan) streak'lar."""
        result = await self.db.execute(
            select(UserStreak).where(
                UserStreak.current_streak > 0,
                UserStreak.last_active_date < cutoff_date,
            )
        )
        return list(result.scalars().all())

    async def reset_streaks(self, streaks: list[UserStreak]) -> None:
        for streak in streaks:
            streak.current_streak = 0
        if streaks:
            await self.db.commit()

    # ── Kunlik eslatma ───────────────────────────────────────
    async def list_active_user_ids_without_completed_session_since(
        self, day_start: datetime
    ) -> list[uuid.UUID]:
        """Faol (`is_active`) foydalanuvchilardan `day_start`dan beri hech qanday
        tugallangan fokus seansi yo'qlari — kunlik eslatma yuboriladigan ro'yxat."""
        completed_today = (
            select(FocusSession.user_id)
            .where(
                FocusSession.status == FocusSessionStatus.COMPLETED,
                FocusSession.started_at >= day_start,
            )
            .distinct()
        )
        result = await self.db.execute(
            select(User.id).where(
                User.is_active.is_(True),
                User.id.not_in(completed_today),
            )
        )
        return list(result.scalars().all())
