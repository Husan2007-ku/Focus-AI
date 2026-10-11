"""
Moliyaviy javobgarlik uchun DB CRUD qatlami — Repository pattern
(TZ v2.0, 3-band "Layered Architecture": API -> Services -> Repositories -> Models).

MUHIM: bu qatlam FAQAT SQLAlchemy so'rovlari bilan shug'ullanadi. Biznes
qarorlari (masalan "maqsadga erishildimi" mezoni, checkout URL generatsiya,
qaysi holatda qaysi LedgerEntryType yozilishi) `FinanceService`da qoladi —
repository ularni bilmaydi, faqat saqlaydi/o'qiydi.
"""

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.finance import CommitmentStatus, FinancialCommitment, LedgerEntry
from app.models.focus_session import FocusSession, FocusSessionStatus


class FinanceRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── FinancialCommitment ─────────────────────────────────
    async def add_commitment(self, commitment: FinancialCommitment) -> FinancialCommitment:
        self.db.add(commitment)
        await self.db.commit()
        await self.db.refresh(commitment)
        return commitment

    async def get_commitment_by_id(
        self, commitment_id: uuid.UUID, user_id: uuid.UUID | None = None
    ) -> FinancialCommitment | None:
        """`user_id` berilsa — faqat shu foydalanuvchiga tegishli bo'lsa qaytaradi
        (auth endpoint'lar uchun); berilmasa — istalgan commitment (webhook/Celery
        kabi ichki chaqiruvlar uchun, TZ'dagi "provayder servislari" izohiga mos)."""
        stmt = select(FinancialCommitment).where(FinancialCommitment.id == commitment_id)
        if user_id is not None:
            stmt = stmt.where(FinancialCommitment.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_commitments_for_user(self, user_id: uuid.UUID) -> list[FinancialCommitment]:
        result = await self.db.execute(
            select(FinancialCommitment)
            .where(FinancialCommitment.user_id == user_id)
            .order_by(FinancialCommitment.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_expired_active_commitments(self, now: datetime) -> list[FinancialCommitment]:
        result = await self.db.execute(
            select(FinancialCommitment).where(
                FinancialCommitment.status == CommitmentStatus.ACTIVE,
                FinancialCommitment.deadline <= now,
            )
        )
        return list(result.scalars().all())

    async def sum_completed_focus_minutes(
        self, user_id: uuid.UUID, window_start: datetime, window_end: datetime
    ) -> int:
        """Berilgan oraliqda tugallangan fokus seanslarining jami daqiqasi."""
        result = await self.db.execute(
            select(func.coalesce(func.sum(FocusSession.actual_duration_minutes), 0)).where(
                FocusSession.user_id == user_id,
                FocusSession.status == FocusSessionStatus.COMPLETED,
                FocusSession.started_at >= window_start,
                FocusSession.started_at <= window_end,
            )
        )
        return result.scalar_one()

    # ── LedgerEntry ──────────────────────────────────────────
    async def add_ledger_entry(self, entry: LedgerEntry) -> LedgerEntry:
        """Yozuvni qo'shadi va commit qiladi — chaqiruvchi tomonidan shu session
        ichida oldin o'zgartirilgan boshqa obyektlar (masalan commitment.status)
        ham shu commit bilan birga saqlanadi."""
        self.db.add(entry)
        await self.db.commit()
        return entry

    async def list_ledger_entries_for_user(self, user_id: uuid.UUID) -> list[LedgerEntry]:
        result = await self.db.execute(
            select(LedgerEntry)
            .where(LedgerEntry.user_id == user_id)
            .order_by(LedgerEntry.created_at.desc())
        )
        return list(result.scalars().all())
