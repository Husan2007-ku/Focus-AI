"""UserService uchun testlar — profil qisman yangilanishi va faolsizlantirish."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.user import UserProfileUpdateSchema
from app.services.user_service import UserService


@pytest.mark.asyncio
async def test_update_profile_only_changes_sent_fields(
    db_session: AsyncSession, test_user: User
) -> None:
    service = UserService(db_session)
    original_full_name = test_user.full_name

    updated = await service.update_profile(
        test_user, UserProfileUpdateSchema(goal="Har kuni 2 soat kitob o'qish")
    )

    assert updated.goal == "Har kuni 2 soat kitob o'qish"
    assert updated.full_name == original_full_name  # yuborilmagan maydon o'zgarmadi


@pytest.mark.asyncio
async def test_update_profile_can_clear_a_field_with_explicit_none(
    db_session: AsyncSession, test_user: User
) -> None:
    service = UserService(db_session)
    await service.update_profile(test_user, UserProfileUpdateSchema(age=25))

    cleared = await service.update_profile(test_user, UserProfileUpdateSchema(age=None))

    assert cleared.age is None


@pytest.mark.asyncio
async def test_deactivate_sets_user_inactive(db_session: AsyncSession, test_user: User) -> None:
    service = UserService(db_session)
    await service.deactivate(test_user)

    assert test_user.is_active is False
