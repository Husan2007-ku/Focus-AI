"""
RoutineService uchun testlar — muhim ketma-ketlik qoidasi: kechqurungi
hisobot faqat ertalabki reja kiritilgandan keyin qabul qilinadi.

Claude API chaqiruvi (`claude_client.send_message`) haqiqiy tarmoq so'rovi
yubormasligi uchun monkeypatch orqali soxtalashtiriladi — bu testlarni
tezkor va `ANTHROPIC_API_KEY`siz ham ishlaydigan qiladi.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.integrations import claude_client as claude_client_module
from app.models.routine import RoutineStatus
from app.models.user import User
from app.schemas.routine import EveningReportSchema, MorningPlanSchema
from app.services.routine_service import RoutineService


@pytest.fixture(autouse=True)
def mock_claude(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_send_message(conversation_history: list[dict[str, str]]) -> str:
        return "Ajoyib ish! Ertaga ham davom ettiring."

    monkeypatch.setattr(claude_client_module.claude_client, "send_message", fake_send_message)


@pytest.mark.asyncio
async def test_morning_plan_creates_routine(db_session: AsyncSession, test_user: User) -> None:
    service = RoutineService(db_session)
    routine = await service.submit_morning_plan(
        test_user, MorningPlanSchema(morning_plan="Kitob o'qish", planned_focus_minutes=60)
    )

    assert routine.morning_plan == "Kitob o'qish"
    assert routine.status == RoutineStatus.PLANNED


@pytest.mark.asyncio
async def test_evening_report_without_morning_plan_raises_conflict(
    db_session: AsyncSession, test_user: User
) -> None:
    service = RoutineService(db_session)

    with pytest.raises(ConflictError):
        await service.submit_evening_report(
            test_user, EveningReportSchema(evening_report="Bajardim", self_rating=5)
        )


@pytest.mark.asyncio
async def test_evening_report_after_morning_plan_succeeds(
    db_session: AsyncSession, test_user: User
) -> None:
    service = RoutineService(db_session)
    await service.submit_morning_plan(
        test_user, MorningPlanSchema(morning_plan="Kitob o'qish", planned_focus_minutes=60)
    )

    routine = await service.submit_evening_report(
        test_user, EveningReportSchema(evening_report="Bajardim", self_rating=5)
    )

    assert routine.status == RoutineStatus.REPORTED
    assert routine.ai_feedback == "Ajoyib ish! Ertaga ham davom ettiring."


@pytest.mark.asyncio
async def test_same_day_morning_plan_is_idempotent(db_session: AsyncSession, test_user: User) -> None:
    """Bir kunda ikkinchi marta ertalabki reja kiritilsa, yangi yozuv emas, mavjudi yangilanishi kerak."""
    service = RoutineService(db_session)
    first = await service.submit_morning_plan(
        test_user, MorningPlanSchema(morning_plan="Birinchi reja", planned_focus_minutes=30)
    )
    second = await service.submit_morning_plan(
        test_user, MorningPlanSchema(morning_plan="Yangilangan reja", planned_focus_minutes=45)
    )

    assert first.id == second.id
    assert second.morning_plan == "Yangilangan reja"
