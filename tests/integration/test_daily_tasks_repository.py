"""
DailyTasksRepository uchun testlar — `app/tasks/daily_tasks.py` Celery
vazifalari asoslanadigan so'rovlar to'g'ri ishlashini tasdiqlaydi.

Celery vazifalarining o'zi (`asyncio.run` + `AsyncSessionLocal` bilan
haqiqiy ilova sessiyasini ochadigan wrapper'lar) shu fayldagi testlar
uchun ishlatilmaydi — ular `db_session` fixture'ining tranzaksiya
izolatsiyasidan tashqarida ishlaydi (haqiqiy `commit()` qiladi). Shuning
uchun asosiy biznes-mantiq to'g'ridan-to'g'ri repository darajasida
tekshiriladi.
"""

from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.focus_session import FocusSession, FocusSessionStatus
from app.models.gamification import UserStreak
from app.models.user import User
from app.repositories.daily_tasks_repository import DailyTasksRepository
from app.utils.timezone import get_tashkent_day_start_utc


@pytest.mark.asyncio
async def test_stale_streak_with_gap_is_listed_and_reset(
    db_session: AsyncSession, test_user: User
) -> None:
    streak = UserStreak(
        user_id=test_user.id,
        current_streak=5,
        longest_streak=5,
        last_active_date=get_tashkent_day_start_utc() - timedelta(days=3),
    )
    db_session.add(streak)
    await db_session.commit()

    repo = DailyTasksRepository(db_session)
    cutoff = get_tashkent_day_start_utc() - timedelta(days=1)

    stale = await repo.list_stale_streaks(cutoff)
    assert len(stale) == 1
    assert stale[0].user_id == test_user.id

    await repo.reset_streaks(stale)
    await db_session.refresh(streak)
    assert streak.current_streak == 0
    assert streak.longest_streak == 5  # rekord saqlanib qoladi


@pytest.mark.asyncio
async def test_streak_active_yesterday_is_not_stale_yet(
    db_session: AsyncSession, test_user: User
) -> None:
    """Foydalanuvchi kecha faol bo'lgan bo'lsa, bugun hali "buzilgan" deb
    hisoblanmasligi kerak — u bugun hali seans qilishi mumkin."""
    streak = UserStreak(
        user_id=test_user.id,
        current_streak=3,
        longest_streak=3,
        last_active_date=get_tashkent_day_start_utc() - timedelta(hours=12),  # kecha kunduzi
    )
    db_session.add(streak)
    await db_session.commit()

    repo = DailyTasksRepository(db_session)
    cutoff = get_tashkent_day_start_utc() - timedelta(days=1)

    stale = await repo.list_stale_streaks(cutoff)
    assert stale == []


@pytest.mark.asyncio
async def test_user_without_completed_session_today_needs_reminder(
    db_session: AsyncSession, test_user: User
) -> None:
    repo = DailyTasksRepository(db_session)
    today_start = get_tashkent_day_start_utc()

    ids = await repo.list_active_user_ids_without_completed_session_since(today_start)
    assert test_user.id in ids


@pytest.mark.asyncio
async def test_user_with_completed_session_today_does_not_need_reminder(
    db_session: AsyncSession, test_user: User
) -> None:
    today_start = get_tashkent_day_start_utc()
    session = FocusSession(
        user_id=test_user.id,
        planned_duration_minutes=25,
        actual_duration_minutes=25,
        status=FocusSessionStatus.COMPLETED,
        started_at=today_start + timedelta(hours=1),
    )
    db_session.add(session)
    await db_session.commit()

    repo = DailyTasksRepository(db_session)
    ids = await repo.list_active_user_ids_without_completed_session_since(today_start)

    assert test_user.id not in ids


@pytest.mark.asyncio
async def test_inactive_user_is_never_reminded(db_session: AsyncSession, test_user: User) -> None:
    test_user.is_active = False
    await db_session.commit()

    repo = DailyTasksRepository(db_session)
    today_start = get_tashkent_day_start_utc()

    ids = await repo.list_active_user_ids_without_completed_session_since(today_start)
    assert test_user.id not in ids
