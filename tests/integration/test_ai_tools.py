"""AI Agent tool-dispatcher (`execute_tool`) uchun testlar.

Har bir tool haqiqiy servis orqali ishlaydi (mock yo'q) — maqsad: Claude'ga
qaytariladigan JSON natija to'g'ri shakllanganini va domen xatolari
foydalanuvchiga tushunarli matn sifatida qaytarilishini tekshirish.

Eslatma: `get_gamification_summary` tool'i uchun test ayniqsa muhim — u
avval `GamificationService.get_summary()`ning "badges" maydonini ORM
obyekti deb xato o'qib, har safar yashirin xatoga uchrardi (tuzatildi:
`b.badge_code.value` o'rniga `b["badge_code"]`).
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gamification import BadgeCode, UserBadge
from app.models.user import User
from app.schemas.routine import MorningPlanSchema
from app.services.ai_tools import execute_tool
from app.services.routine_service import RoutineService


@pytest.mark.asyncio
async def test_start_focus_session_tool_creates_session(
    db_session: AsyncSession, test_user: User
) -> None:
    result = await execute_tool(
        "start_focus_session", {"planned_duration_minutes": 25}, db_session, test_user
    )

    assert result["success"] is True
    assert result["status"] == "active"
    assert result["planned_duration_minutes"] == 25


@pytest.mark.asyncio
async def test_start_focus_session_tool_returns_domain_error_for_second_active_session(
    db_session: AsyncSession, test_user: User
) -> None:
    await execute_tool(
        "start_focus_session", {"planned_duration_minutes": 25}, db_session, test_user
    )

    result = await execute_tool(
        "start_focus_session", {"planned_duration_minutes": 10}, db_session, test_user
    )

    assert "error" in result
    assert "success" not in result


@pytest.mark.asyncio
async def test_get_active_focus_session_tool_returns_none_when_no_session(
    db_session: AsyncSession, test_user: User
) -> None:
    result = await execute_tool("get_active_focus_session", {}, db_session, test_user)

    assert result == {"active_session": None}


@pytest.mark.asyncio
async def test_get_active_focus_session_tool_returns_session_details(
    db_session: AsyncSession, test_user: User
) -> None:
    await execute_tool(
        "start_focus_session", {"planned_duration_minutes": 50}, db_session, test_user
    )

    result = await execute_tool("get_active_focus_session", {}, db_session, test_user)

    assert result["active_session"]["planned_duration_minutes"] == 50
    assert "started_at" in result["active_session"]


@pytest.mark.asyncio
async def test_get_focus_history_summary_tool_with_no_sessions(
    db_session: AsyncSession, test_user: User
) -> None:
    result = await execute_tool("get_focus_history_summary", {}, db_session, test_user)

    assert result == {"total_sessions": 0, "recent_sessions": []}


@pytest.mark.asyncio
async def test_get_gamification_summary_tool_returns_badge_codes_not_crashing(
    db_session: AsyncSession, test_user: User
) -> None:
    # Avval haqiqiy badge beramiz, keyin tool orqali qaytarilgan shakl
    # to'g'ri ekanini tekshiramiz (regressiya: tuzatilgan bug shu yerda
    # ushlangan bo'lardi — oldin bu holatda AttributeError bilan yiqilib,
    # har doim {"error": ...} qaytarardi).
    db_session.add(UserBadge(user_id=test_user.id, badge_code=BadgeCode.FIRST_SESSION))
    await db_session.commit()

    result = await execute_tool("get_gamification_summary", {}, db_session, test_user)

    assert "error" not in result
    assert result["badges"] == ["first_session"]
    assert isinstance(result["current_streak"], int)
    assert isinstance(result["total_xp"], int)


@pytest.mark.asyncio
async def test_get_gamification_summary_tool_with_no_activity(
    db_session: AsyncSession, test_user: User
) -> None:
    result = await execute_tool("get_gamification_summary", {}, db_session, test_user)

    assert result == {
        "current_streak": 0,
        "longest_streak": 0,
        "total_xp": 0,
        "badges": [],
    }


@pytest.mark.asyncio
async def test_get_today_routine_tool_returns_none_when_no_routine(
    db_session: AsyncSession, test_user: User
) -> None:
    result = await execute_tool("get_today_routine", {}, db_session, test_user)

    assert result == {"routine": None}


@pytest.mark.asyncio
async def test_get_today_routine_tool_returns_morning_plan(
    db_session: AsyncSession, test_user: User
) -> None:
    routine_service = RoutineService(db_session)
    await routine_service.submit_morning_plan(
        test_user, MorningPlanSchema(morning_plan="Bugun 3 ta fokus seansi qilaman")
    )

    result = await execute_tool("get_today_routine", {}, db_session, test_user)

    assert result["routine"]["morning_plan"] == "Bugun 3 ta fokus seansi qilaman"
    assert result["routine"]["evening_report"] is None
    assert result["routine"]["status"] == "planned"


@pytest.mark.asyncio
async def test_unknown_tool_name_returns_error(db_session: AsyncSession, test_user: User) -> None:
    result = await execute_tool("not_a_real_tool", {}, db_session, test_user)

    assert result == {"error": "Noma'lum tool: not_a_real_tool"}
