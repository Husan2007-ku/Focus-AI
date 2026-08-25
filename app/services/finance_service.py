"""
Moliyaviy javobgarlik — asosiy domen logikasi.

Bu servis pul harakatlarining "haqiqiy" ma'nosini bilgan yagona joy:
depozit qabul qilish, muvaffaqiyat/muvaffaqiyatsizlik holatida pulni
yo'naltirish. Provayderga xos protokol tafsilotlari (Payme/Click)
alohida servislarda (`payme_service.py`, `click_service.py`) qoladi va
faqat shu yerdagi metodlarni chaqiradi.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.integrations import click_client
from app.integrations.payme_client import generate_checkout_url as generate_payme_checkout_url
from app.models.finance import (
    CommitmentStatus,
    FinancialCommitment,
    LedgerEntry,
    LedgerEntryType,
    Transaction,
)
from app.models.focus_session import FocusSession, FocusSessionStatus
from app.models.user import User
from app.schemas.finance import CreateCommitmentSchema
from app.utils.payment_ref import PaymentTargetKind, build_payment_ref

logger = get_logger(__name__)


class FinanceService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Foydalanuvchi tomonidan chaqiriladigan amallar ──────
    async def create_commitment(
        self, user: User, data: CreateCommitmentSchema
    ) -> tuple[FinancialCommitment, str, str]:
        commitment = FinancialCommitment(
            user_id=user.id,
            goal_description=data.goal_description,
            amount=data.amount,
            target_focus_minutes=data.target_focus_minutes,
            deadline=data.deadline,
            beneficiary_note=data.beneficiary_note,
            status=CommitmentStatus.PENDING_PAYMENT,
        )
        self.db.add(commitment)
        await self.db.commit()
        await self.db.refresh(commitment)

        ref = build_payment_ref(PaymentTargetKind.COMMITMENT, commitment.id)
        payme_url = generate_payme_checkout_url(ref, float(commitment.amount))
        click_url = click_client.generate_checkout_url(ref, float(commitment.amount))

        logger.info(
            "commitment_created", user_id=str(user.id), commitment_id=str(commitment.id)
        )
        return commitment, payme_url, click_url

    async def get_commitment(self, user: User, commitment_id: uuid.UUID) -> FinancialCommitment:
        result = await self.db.execute(
            select(FinancialCommitment).where(
                FinancialCommitment.id == commitment_id, FinancialCommitment.user_id == user.id
            )
        )
        commitment = result.scalar_one_or_none()
        if commitment is None:
            raise NotFoundError("Moliyaviy maqsad topilmadi.")
        return commitment

    async def list_commitments(self, user: User) -> list[FinancialCommitment]:
        result = await self.db.execute(
            select(FinancialCommitment)
            .where(FinancialCommitment.user_id == user.id)
            .order_by(FinancialCommitment.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_ledger_entries(self, user: User) -> list[LedgerEntry]:
        result = await self.db.execute(
            select(LedgerEntry)
            .where(LedgerEntry.user_id == user.id)
            .order_by(LedgerEntry.created_at.desc())
        )
        return list(result.scalars().all())

    # ── Provayder servislari tomonidan chaqiriladigan ichki amallar ──
    async def get_commitment_by_id(self, commitment_id: uuid.UUID) -> FinancialCommitment | None:
        result = await self.db.execute(
            select(FinancialCommitment).where(FinancialCommitment.id == commitment_id)
        )
        return result.scalar_one_or_none()

    async def activate_commitment(self, commitment: FinancialCommitment, transaction: Transaction) -> None:
        """To'lov muvaffaqiyatli qabul qilinganda (Payme PerformTransaction) chaqiriladi."""
        if commitment.status != CommitmentStatus.PENDING_PAYMENT:
            logger.warning(
                "activate_commitment_unexpected_status",
                commitment_id=str(commitment.id),
                status=commitment.status,
            )
            return

        commitment.status = CommitmentStatus.ACTIVE

        ledger_entry = LedgerEntry(
            user_id=commitment.user_id,
            commitment_id=commitment.id,
            transaction_id=transaction.id,
            entry_type=LedgerEntryType.DEPOSIT,
            amount=transaction.amount,
        )
        self.db.add(ledger_entry)
        await self.db.commit()

        logger.info("commitment_activated", commitment_id=str(commitment.id))

    async def reverse_deposit(self, commitment: FinancialCommitment, transaction: Transaction) -> None:
        """To'lov Payme tomonidan (PERFORMED holatidan) bekor qilinganda chaqiriladi."""
        commitment.status = CommitmentStatus.CANCELLED

        ledger_entry = LedgerEntry(
            user_id=commitment.user_id,
            commitment_id=commitment.id,
            transaction_id=transaction.id,
            entry_type=LedgerEntryType.CANCELLATION_REVERSAL,
            amount=transaction.amount,
        )
        self.db.add(ledger_entry)
        await self.db.commit()

        logger.warning("commitment_deposit_reversed", commitment_id=str(commitment.id))

    async def resolve_commitment(self, commitment: FinancialCommitment) -> None:
        """
        Muddat tugaganda chaqiriladi (Celery task orqali) — maqsadga erishilgan-
        erishilmaganini tekshiradi va pulni tegishli tomonga yo'naltiradi.
        """
        if commitment.status != CommitmentStatus.ACTIVE:
            return  # to'lov qilinmagan yoki allaqachon hal qilingan

        total_minutes_result = await self.db.execute(
            select(func.coalesce(func.sum(FocusSession.actual_duration_minutes), 0)).where(
                FocusSession.user_id == commitment.user_id,
                FocusSession.status == FocusSessionStatus.COMPLETED,
                FocusSession.started_at >= commitment.created_at,
                FocusSession.started_at <= commitment.deadline,
            )
        )
        total_minutes = total_minutes_result.scalar_one()

        achieved = total_minutes >= commitment.target_focus_minutes
        commitment.status = CommitmentStatus.SUCCEEDED if achieved else CommitmentStatus.FAILED

        ledger_entry = LedgerEntry(
            user_id=commitment.user_id,
            commitment_id=commitment.id,
            entry_type=LedgerEntryType.REFUND if achieved else LedgerEntryType.DONATION,
            amount=commitment.amount,
        )
        self.db.add(ledger_entry)
        await self.db.commit()

        logger.info(
            "commitment_resolved",
            commitment_id=str(commitment.id),
            achieved=achieved,
            total_minutes=total_minutes,
            target_minutes=commitment.target_focus_minutes,
        )

    async def get_expired_active_commitments(self) -> list[FinancialCommitment]:
        """Celery task uchun: muddati o'tgan, lekin hali hal qilinmagan maqsadlar."""
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(FinancialCommitment).where(
                FinancialCommitment.status == CommitmentStatus.ACTIVE,
                FinancialCommitment.deadline <= now,
            )
        )
        return list(result.scalars().all())
