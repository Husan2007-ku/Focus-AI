"""
StatsService uchun testlar — jami/haftalik agregatsiya to'g'riligi va AI
xulosa generatsiyasi (Claude chaqiruvi monkeypatch bilan soxtalashtirilgan).
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations import claude_client as claude_client_module
from app.models.focus_session import FocusSession, FocusSessionStatus
from app.models.user import User
from app.services.stats_service import StatsService


@pytest.fixture(autouse=True)
def mock_claude(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_send_message(conversation_history: list[dict[str, str]]) -> str:
        return "Bu hafta yaxshi natija ko'rsatdingiz, davom eting!"

    monkeypatch.setattr(claude_client_module.claude_client, "send_message", fake_send_message)


async def _make_completed_session(
    db_session: AsyncSession, user: User, minutes: int, started_at: datetime
) -> FocusSession:
    session = FocusSession(
        user_id=user.id,
        planned_duration_minutes=minutes,
        actual_duration_minutes=minutes,
        status=FocusSessionStatus.COMPLETED,
        started_at=started_at,
    )
    db_session.add(session)
    await db_session.commit()
    return session


@pytest.mark.asyncio
async def test_summary_counts_only_completed_sessions_and_weekly_window(
    db_session: AsyncSession, test_user: User
) -> None:
    now = datetime.now(UTC)
    await _make_completed_session(db_session, test_user, 25, now)  # shu hafta
    await _make_completed_session(
        db_session, test_user, 40, now - timedelta(days=30)
    )  # eski, jamiga kiradi, haftalikka kirmaydi

    service = StatsService(db_session)
    summary = await service.get_summary(test_user)

    assert summary["total_completed_sessions"] == 2
    assert summary["total_focus_minutes"] == 65
    assert summary["weekly_completed_sessions"] == 1
    assert summary["weekly_focus_minutes"] == 25


@pytest.mark.asyncio
async def test_summary_with_no_sessions_returns_zeroes(
    db_session: AsyncSession, test_user: User
) -> None:
    service = StatsService(db_session)
    summary = await service.get_summary(test_user)

    assert summary["total_completed_sessions"] == 0
    assert summary["total_focus_minutes"] == 0
    assert summary["current_streak"] == 0


@pytest.mark.asyncio
async def test_weekly_ai_summary_uses_only_this_weeks_data(
    db_session: AsyncSession, test_user: User
) -> None:
    now = datetime.now(UTC)
    await _make_completed_session(db_session, test_user, 50, now)
    await _make_completed_session(db_session, test_user, 999, now - timedelta(days=60))

    service = StatsService(db_session)
    result = await service.get_weekly_ai_summary(test_user)

    assert result["weekly_completed_sessions"] == 1
    assert result["weekly_focus_minutes"] == 50
    assert result["summary"] == "Bu hafta yaxshi natija ko'rsatdingiz, davom eting!"
    assert result["week_start"] <= result["week_end"]
