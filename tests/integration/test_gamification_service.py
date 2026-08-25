"""
GamificationService uchun testlar — streak hisoblash mantig'i eng nozik
qism, chunki u sana chegaralariga (kecha/bugun/uzilish) bog'liq.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gamification import BadgeCode, XPReason
from app.models.user import User
from app.services.gamification_service import GamificationService


@pytest.mark.asyncio
async def test_first_session_creates_streak_of_one(db_session: AsyncSession, test_user: User) -> None:
    service = GamificationService(db_session)
    await service.register_focus_session_completed(test_user.id, uuid.uuid4())

    streak = await service._get_or_create_streak(test_user.id)
    assert streak.current_streak == 1
    assert streak.longest_streak == 1


@pytest.mark.asyncio
async def test_first_session_awards_first_session_badge(db_session: AsyncSession, test_user: User) -> None:
    service = GamificationService(db_session)
    await service.register_focus_session_completed(test_user.id, uuid.uuid4())

    summary = await service.get_summary(test_user.id)
    badge_codes = {b["badge_code"] for b in summary["badges"]}
    assert BadgeCode.FIRST_SESSION.value in badge_codes


@pytest.mark.asyncio
async def test_same_day_second_session_does_not_increment_streak(
    db_session: AsyncSession, test_user: User
) -> None:
    service = GamificationService(db_session)
    await service.register_focus_session_completed(test_user.id, uuid.uuid4())
    await service.register_focus_session_completed(test_user.id, uuid.uuid4())

    streak = await service._get_or_create_streak(test_user.id)
    assert streak.current_streak == 1


@pytest.mark.asyncio
async def test_consecutive_day_increments_streak(db_session: AsyncSession, test_user: User) -> None:
    service = GamificationService(db_session)
    streak = await service._get_or_create_streak(test_user.id)

    # "Kecha faol bo'lgan" holatini qo'lda simulyatsiya qilamiz.
    streak.current_streak = 1
    streak.longest_streak = 1
    streak.last_active_date = datetime.now(timezone.utc) - timedelta(days=1)
    await db_session.commit()

    await service.register_focus_session_completed(test_user.id, uuid.uuid4())

    updated = await service._get_or_create_streak(test_user.id)
    assert updated.current_streak == 2


@pytest.mark.asyncio
async def test_gap_resets_streak_to_one(db_session: AsyncSession, test_user: User) -> None:
    service = GamificationService(db_session)
    streak = await service._get_or_create_streak(test_user.id)

    # 3 kun oldin faol bo'lgan — orada kun(lar) o'tkazib yuborilgan.
    streak.current_streak = 5
    streak.longest_streak = 5
    streak.last_active_date = datetime.now(timezone.utc) - timedelta(days=3)
    await db_session.commit()

    await service.register_focus_session_completed(test_user.id, uuid.uuid4())

    updated = await service._get_or_create_streak(test_user.id)
    assert updated.current_streak == 1
    assert updated.longest_streak == 5  # eng yuqori rekord saqlanib qolishi kerak


@pytest.mark.asyncio
async def test_xp_accumulates_across_transactions(db_session: AsyncSession, test_user: User) -> None:
    service = GamificationService(db_session)
    await service.award_xp(test_user.id, XPReason.FOCUS_SESSION_COMPLETED, uuid.uuid4())
    await service.award_xp(test_user.id, XPReason.DAILY_ROUTINE_COMPLETED, uuid.uuid4())

    summary = await service.get_summary(test_user.id)
    assert summary["total_xp"] == 10 + 5
