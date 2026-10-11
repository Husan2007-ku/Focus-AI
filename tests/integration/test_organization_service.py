"""OrganizationService uchun testlar — B2B tashkilot yaratish, qo'shilish,
chiqish va admin statistikasi.

Haqiqiy DB (`db_session`) ishlatiladi — repository qatlami to'g'ridan-to'g'ri
tekshiriladi, mock yo'q (tashqi integratsiya yo'q, faqat o'z bazamiz).
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.models.user import AuthProvider, User
from app.services.organization_service import OrganizationService


def _make_user(phone_suffix: int) -> User:
    return User(
        phone_number=f"+99891{phone_suffix:07d}",
        primary_auth_provider=AuthProvider.PHONE,
        full_name="A'zo Foydalanuvchi",
    )


@pytest.mark.asyncio
async def test_create_organization_sets_admin_and_invite_code(
    db_session: AsyncSession, test_user: User
) -> None:
    service = OrganizationService(db_session)

    organization = await service.create_organization(test_user, "Acme LLC", seat_limit=10)

    assert organization.admin_user_id == test_user.id
    assert organization.seat_limit == 10
    assert len(organization.invite_code) == 8
    assert test_user.organization_id == organization.id


@pytest.mark.asyncio
async def test_create_organization_fails_if_admin_already_has_one(
    db_session: AsyncSession, test_user: User
) -> None:
    service = OrganizationService(db_session)
    await service.create_organization(test_user, "Acme LLC", seat_limit=10)

    with pytest.raises(ConflictError):
        await service.create_organization(test_user, "Boshqa Tashkilot", seat_limit=5)


@pytest.mark.asyncio
async def test_join_organization_with_valid_code_sets_membership(
    db_session: AsyncSession, test_user: User
) -> None:
    service = OrganizationService(db_session)
    organization = await service.create_organization(test_user, "Acme LLC", seat_limit=10)

    member = _make_user(1111111)
    db_session.add(member)
    await db_session.commit()

    joined = await service.join_organization(member, organization.invite_code.lower())

    assert joined.id == organization.id
    assert member.organization_id == organization.id


@pytest.mark.asyncio
async def test_join_organization_fails_with_unknown_invite_code(
    db_session: AsyncSession, test_user: User
) -> None:
    service = OrganizationService(db_session)

    with pytest.raises(NotFoundError):
        await service.join_organization(test_user, "NOSUCHCODE")


@pytest.mark.asyncio
async def test_join_organization_fails_when_user_already_in_one(
    db_session: AsyncSession, test_user: User
) -> None:
    service = OrganizationService(db_session)
    organization = await service.create_organization(test_user, "Acme LLC", seat_limit=10)

    with pytest.raises(ConflictError):
        await service.join_organization(test_user, organization.invite_code)


@pytest.mark.asyncio
async def test_join_organization_fails_when_seat_limit_reached(
    db_session: AsyncSession, test_user: User
) -> None:
    service = OrganizationService(db_session)
    organization = await service.create_organization(test_user, "Acme LLC", seat_limit=1)

    # `seat_limit=1` admin'ning o'zi tomonidan allaqachon egallangan.
    member = _make_user(2222222)
    db_session.add(member)
    await db_session.commit()

    with pytest.raises(ConflictError):
        await service.join_organization(member, organization.invite_code)


@pytest.mark.asyncio
async def test_leave_organization_clears_membership(
    db_session: AsyncSession, test_user: User
) -> None:
    service = OrganizationService(db_session)
    await service.create_organization(test_user, "Acme LLC", seat_limit=10)

    await service.leave_organization(test_user)

    assert test_user.organization_id is None


@pytest.mark.asyncio
async def test_leave_organization_fails_when_not_a_member(
    db_session: AsyncSession, test_user: User
) -> None:
    service = OrganizationService(db_session)

    with pytest.raises(ConflictError):
        await service.leave_organization(test_user)


@pytest.mark.asyncio
async def test_get_my_organization_returns_none_when_not_a_member(
    db_session: AsyncSession, test_user: User
) -> None:
    service = OrganizationService(db_session)

    assert await service.get_my_organization(test_user) is None


@pytest.mark.asyncio
async def test_get_stats_raises_not_found_when_not_a_member(
    db_session: AsyncSession, test_user: User
) -> None:
    service = OrganizationService(db_session)

    with pytest.raises(NotFoundError):
        await service.get_stats(test_user)


@pytest.mark.asyncio
async def test_get_stats_raises_forbidden_for_non_admin_member(
    db_session: AsyncSession, test_user: User
) -> None:
    service = OrganizationService(db_session)
    organization = await service.create_organization(test_user, "Acme LLC", seat_limit=10)

    member = _make_user(3333333)
    db_session.add(member)
    await db_session.commit()
    await service.join_organization(member, organization.invite_code)

    with pytest.raises(ForbiddenError):
        await service.get_stats(member)


@pytest.mark.asyncio
async def test_get_stats_returns_zeroed_metrics_for_fresh_organization(
    db_session: AsyncSession, test_user: User
) -> None:
    service = OrganizationService(db_session)
    await service.create_organization(test_user, "Acme LLC", seat_limit=10)

    stats = await service.get_stats(test_user)

    assert stats["member_count"] == 1
    assert stats["seat_limit"] == 10
    assert stats["total_completed_sessions"] == 0
    assert stats["total_focus_minutes"] == 0
    assert stats["average_current_streak"] == 0.0


@pytest.mark.asyncio
async def test_join_organization_fails_when_organization_suspended(
    db_session: AsyncSession, test_user: User
) -> None:
    from app.models.organization import OrganizationStatus

    service = OrganizationService(db_session)
    organization = await service.create_organization(test_user, "Acme LLC", seat_limit=10)
    organization.status = OrganizationStatus.SUSPENDED
    await db_session.commit()

    member = _make_user(4444444)
    db_session.add(member)
    await db_session.commit()

    with pytest.raises(ConflictError):
        await service.join_organization(member, organization.invite_code)
