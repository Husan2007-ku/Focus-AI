"""
FinanceService uchun testlar — bu TZ'dagi eng nozik va muhim qism, chunki
haqiqiy pul harakati bilan bog'liq. Asosiy e'tibor: maqsadga erishilgan-
erishilmaganini to'g'ri aniqlash va tegishli LedgerEntry yozuvini yaratish.
"""

import base64
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.finance import CommitmentStatus, LedgerEntry, LedgerEntryType
from app.models.focus_session import FocusSession, FocusSessionStatus
from app.models.user import User
from app.schemas.finance import CreateCommitmentSchema
from app.services.finance_service import FinanceService


def _make_commitment_schema(target_minutes: int = 60) -> CreateCommitmentSchema:
    return CreateCommitmentSchema(
        goal_description="Har kuni 1 soat kitob o'qish",
        amount=Decimal("50000"),
        target_focus_minutes=target_minutes,
        deadline=datetime.now(timezone.utc) + timedelta(days=7),
        beneficiary_note="Mehr-Nur xayriya jamg'armasi",
    )


@pytest.mark.asyncio
async def test_create_commitment_generates_both_checkout_urls(
    db_session: AsyncSession, test_user: User
) -> None:
    service = FinanceService(db_session)
    commitment, payme_url, click_url = await service.create_commitment(
        test_user, _make_commitment_schema()
    )

    assert commitment.status == CommitmentStatus.PENDING_PAYMENT
    assert payme_url.startswith("https://checkout.paycom.uz/")
    assert "my.click.uz" in click_url
    assert str(commitment.id) in click_url  # Click'da ref ochiq matnda (query param)

    # Payme'da parametrlar base64'ga kodlangan — dekodlab tekshiramiz.
    encoded_part = payme_url.removeprefix("https://checkout.paycom.uz/")
    decoded_params = base64.b64decode(encoded_part).decode()
    assert f"commitment:{commitment.id}" in decoded_params


@pytest.mark.asyncio
async def test_resolve_commitment_succeeds_when_target_met(
    db_session: AsyncSession, test_user: User
) -> None:
    service = FinanceService(db_session)
    commitment, _, _ = await service.create_commitment(test_user, _make_commitment_schema(target_minutes=60))

    # To'lov qilingandek simulyatsiya qilamiz. Deadline'ni o'zgartirmaymiz —
    # `resolve_commitment` o'zi deadline'ni tekshirmaydi (buni faqat Celery
    # task uchun `get_expired_active_commitments` tekshiradi), shuning uchun
    # deadline kelajakda qolishi mumkin va bu testga xalaqit bermaydi.
    commitment.status = CommitmentStatus.ACTIVE
    await db_session.commit()

    # Maqsad talab qilgan 60 daqiqadan ko'proq fokus vaqti "bajarilgan" holda.
    session = FocusSession(
        user_id=test_user.id,
        planned_duration_minutes=90,
        actual_duration_minutes=90,
        status=FocusSessionStatus.COMPLETED,
        started_at=commitment.created_at,
    )
    db_session.add(session)
    await db_session.commit()

    await service.resolve_commitment(commitment)

    assert commitment.status == CommitmentStatus.SUCCEEDED

    result = await db_session.execute(
        select(LedgerEntry).where(LedgerEntry.commitment_id == commitment.id)
    )
    entry = result.scalar_one()
    assert entry.entry_type == LedgerEntryType.REFUND
    assert entry.amount == commitment.amount


@pytest.mark.asyncio
async def test_resolve_commitment_fails_when_target_not_met(
    db_session: AsyncSession, test_user: User
) -> None:
    service = FinanceService(db_session)
    commitment, _, _ = await service.create_commitment(
        test_user, _make_commitment_schema(target_minutes=120)
    )

    commitment.status = CommitmentStatus.ACTIVE
    await db_session.commit()

    # Talab 120 daqiqa, lekin foydalanuvchi faqat 20 daqiqa bajargan.
    session = FocusSession(
        user_id=test_user.id,
        planned_duration_minutes=20,
        actual_duration_minutes=20,
        status=FocusSessionStatus.COMPLETED,
        started_at=commitment.created_at,
    )
    db_session.add(session)
    await db_session.commit()

    await service.resolve_commitment(commitment)

    assert commitment.status == CommitmentStatus.FAILED

    result = await db_session.execute(
        select(LedgerEntry).where(LedgerEntry.commitment_id == commitment.id)
    )
    entry = result.scalar_one()
    assert entry.entry_type == LedgerEntryType.DONATION
    assert entry.amount == commitment.amount


@pytest.mark.asyncio
async def test_resolve_commitment_ignores_sessions_outside_window(
    db_session: AsyncSession, test_user: User
) -> None:
    """Commitment yaratilishidan OLDIN bajarilgan seanslar hisobga olinmasligi kerak."""
    service = FinanceService(db_session)
    commitment, _, _ = await service.create_commitment(test_user, _make_commitment_schema(target_minutes=30))

    old_session = FocusSession(
        user_id=test_user.id,
        planned_duration_minutes=90,
        actual_duration_minutes=90,
        status=FocusSessionStatus.COMPLETED,
        started_at=commitment.created_at - timedelta(days=10),
    )
    db_session.add(old_session)

    commitment.status = CommitmentStatus.ACTIVE
    await db_session.commit()

    await service.resolve_commitment(commitment)

    assert commitment.status == CommitmentStatus.FAILED


@pytest.mark.asyncio
async def test_resolve_commitment_skips_non_active_commitments(
    db_session: AsyncSession, test_user: User
) -> None:
    """PENDING_PAYMENT holatidagi (hali to'lanmagan) maqsad hal qilinmasligi kerak."""
    service = FinanceService(db_session)
    commitment, _, _ = await service.create_commitment(test_user, _make_commitment_schema())

    await service.resolve_commitment(commitment)

    assert commitment.status == CommitmentStatus.PENDING_PAYMENT

    result = await db_session.execute(
        select(LedgerEntry).where(LedgerEntry.commitment_id == commitment.id)
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_get_expired_active_commitments_finds_only_relevant(
    db_session: AsyncSession, test_user: User
) -> None:
    service = FinanceService(db_session)

    expired_commitment, _, _ = await service.create_commitment(test_user, _make_commitment_schema())
    expired_commitment.status = CommitmentStatus.ACTIVE
    expired_commitment.deadline = datetime.now(timezone.utc) - timedelta(days=1)

    future_commitment, _, _ = await service.create_commitment(test_user, _make_commitment_schema())
    future_commitment.status = CommitmentStatus.ACTIVE
    future_commitment.deadline = datetime.now(timezone.utc) + timedelta(days=1)

    pending_commitment, _, _ = await service.create_commitment(test_user, _make_commitment_schema())
    pending_commitment.deadline = datetime.now(timezone.utc) - timedelta(days=1)
    # status hamon PENDING_PAYMENT — bu ro'yxatga kirmasligi kerak

    await db_session.commit()

    expired = await service.get_expired_active_commitments()
    expired_ids = {c.id for c in expired}

    assert expired_commitment.id in expired_ids
    assert future_commitment.id not in expired_ids
    assert pending_commitment.id not in expired_ids
