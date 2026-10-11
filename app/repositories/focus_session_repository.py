"""
Focus Session uchun DB CRUD qatlami — Repository pattern (TZ v2.0, 3-band).
"""

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.focus_session import FocusSession, FocusSessionStatus


class FocusSessionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def add(self, session: FocusSession) -> FocusSession:
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def commit(self) -> None:
        """Chaqiruvchi tomonidan oldin o'zgartirilgan (masalan status) obyektlarni saqlaydi."""
        await self.db.commit()

    async def refresh(self, session: FocusSession) -> None:
        await self.db.refresh(session)

    async def get_active_for_user(self, user_id: uuid.UUID) -> FocusSession | None:
        result = await self.db.execute(
            select(FocusSession).where(
                FocusSession.user_id == user_id,
                FocusSession.status == FocusSessionStatus.ACTIVE,
            )
        )
        return result.scalar_one_or_none()

    async def get_owned(self, user_id: uuid.UUID, session_id: uuid.UUID) -> FocusSession | None:
        result = await self.db.execute(
            select(FocusSession).where(
                FocusSession.id == session_id, FocusSession.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    async def list_for_user(
        self, user_id: uuid.UUID, limit: int, offset: int
    ) -> tuple[list[FocusSession], int]:
        items_result = await self.db.execute(
            select(FocusSession)
            .where(FocusSession.user_id == user_id)
            .order_by(FocusSession.started_at.desc())
            .limit(limit)
            .offset(offset)
        )
        items = list(items_result.scalars().all())

        count_result = await self.db.execute(
            select(func.count(FocusSession.id)).where(FocusSession.user_id == user_id)
        )
        total = count_result.scalar_one()

        return items, total

    # ── Statistika agregatsiyalari (stats.py uchun) ────────────
    async def get_completed_stats(
        self, user_id: uuid.UUID, since: datetime | None = None
    ) -> tuple[int, int]:
        """(tugallangan seanslar soni, jami fokus daqiqasi). `since` berilmasa —
        butun tarix bo'yicha, berilsa — shu vaqtdan buyon (masalan haftalik)."""
        stmt = select(
            func.count(FocusSession.id),
            func.coalesce(func.sum(FocusSession.actual_duration_minutes), 0),
        ).where(
            FocusSession.user_id == user_id,
            FocusSession.status == FocusSessionStatus.COMPLETED,
        )
        if since is not None:
            stmt = stmt.where(FocusSession.started_at >= since)

        result = await self.db.execute(stmt)
        return result.one()
