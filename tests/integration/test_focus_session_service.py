"""
FocusSessionService uchun testlar — eng muhim biznes qoidasi: bir vaqtning
o'zida foydalanuvchida faqat BITTA faol seans bo'lishi mumkin.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.focus_session import FocusSessionStatus
from app.models.user import User
from app.schemas.focus import FocusSessionStartSchema
from app.services.focus_service import FocusSessionService


@pytest.mark.asyncio
async def test_start_session_creates_active_session(
    db_session: AsyncSession, test_user: User
) -> None:
    service = FocusSessionService(db_session)
    session = await service.start_session(
        test_user, FocusSessionStartSchema(planned_duration_minutes=25)
    )

    assert session.status == FocusSessionStatus.ACTIVE
    assert session.planned_duration_minutes == 25
    assert session.user_id == test_user.id


@pytest.mark.asyncio
async def test_cannot_start_second_active_session(
    db_session: AsyncSession, test_user: User
) -> None:
    service = FocusSessionService(db_session)
    await service.start_session(test_user, FocusSessionStartSchema(planned_duration_minutes=25))

    with pytest.raises(ConflictError):
        await service.start_session(test_user, FocusSessionStartSchema(planned_duration_minutes=10))


@pytest.mark.asyncio
async def test_complete_session_calculates_duration(
    db_session: AsyncSession, test_user: User
) -> None:
    service = FocusSessionService(db_session)
    session = await service.start_session(
        test_user, FocusSessionStartSchema(planned_duration_minutes=25)
    )

    completed = await service.complete_session(test_user, session.id)

    assert completed.status == FocusSessionStatus.COMPLETED
    assert completed.actual_duration_minutes is not None
    assert completed.actual_duration_minutes >= 0
    assert completed.ended_at is not None


@pytest.mark.asyncio
async def test_complete_nonexistent_session_raises_not_found(
    db_session: AsyncSession, test_user: User
) -> None:
    import uuid

    service = FocusSessionService(db_session)
    with pytest.raises(NotFoundError):
        await service.complete_session(test_user, uuid.uuid4())


@pytest.mark.asyncio
async def test_after_completion_new_session_can_start(
    db_session: AsyncSession, test_user: User
) -> None:
    """Bitta seans yakunlangach, yangisini boshlash mumkin bo'lishi kerak.

    Qoida faqat FAOL seansga tegishli.
    """
    service = FocusSessionService(db_session)
    first = await service.start_session(
        test_user, FocusSessionStartSchema(planned_duration_minutes=25)
    )
    await service.complete_session(test_user, first.id)

    second = await service.start_session(
        test_user, FocusSessionStartSchema(planned_duration_minutes=15)
    )
    assert second.status == FocusSessionStatus.ACTIVE
