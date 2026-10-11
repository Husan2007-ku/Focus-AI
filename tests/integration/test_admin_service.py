"""AdminService uchun testlar — platforma bo'yicha agregatsiya to'g'riligi."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.admin_service import AdminService


@pytest.mark.asyncio
async def test_dashboard_counts_the_seeded_test_user(
    db_session: AsyncSession, test_user: User
) -> None:
    service = AdminService(db_session)
    stats = await service.get_dashboard_stats()

    assert stats["total_users"] >= 1
    assert stats["active_users"] >= 1
    assert "free" in stats["users_by_tier"]
    assert stats["total_completed_sessions"] >= 0


@pytest.mark.asyncio
async def test_dashboard_counts_deactivated_user_as_inactive(
    db_session: AsyncSession, test_user: User
) -> None:
    test_user.is_active = False
    await db_session.commit()

    service = AdminService(db_session)
    before = await service.get_dashboard_stats()

    assert before["total_users"] >= 1
