"""SubscriptionService uchun testlar — obuna yaratish, faollashtirish
(birinchi marta va uzaytirish holatlari), bekor qilish va User.subscription_tier
sinxronizatsiyasi.

Checkout URL generatsiyasi tashqi HTTP chaqiruvi qilmaydi (faqat string
formatlash), shuning uchun mock kerak emas — haqiqiy DB bilan ishlaydi.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.subscription import PLAN_TIER, Subscription, SubscriptionPlan
from app.models.user import SubscriptionTier, User
from app.services.subscription_service import SubscriptionService


@pytest.mark.asyncio
async def test_create_subscription_order_creates_inactive_subscription(
    db_session: AsyncSession, test_user: User
) -> None:
    subscription, payme_url, click_url = await SubscriptionService(
        db_session
    ).create_subscription_order(test_user, SubscriptionPlan.MONTHLY)

    assert subscription.is_active is False
    assert subscription.user_id == test_user.id
    assert "checkout.paycom.uz" in payme_url
    assert "my.click.uz" in click_url


@pytest.mark.asyncio
async def test_get_subscription_by_id_returns_none_for_unknown(
    db_session: AsyncSession, test_user: User
) -> None:
    result = await SubscriptionService(db_session).get_subscription_by_id(uuid.uuid4())

    assert result is None


@pytest.mark.asyncio
async def test_get_active_subscription_returns_none_when_user_has_no_subscription(
    db_session: AsyncSession, test_user: User
) -> None:
    result = await SubscriptionService(db_session).get_active_subscription(test_user)

    assert result is None


@pytest.mark.asyncio
async def test_activate_subscription_sets_active_and_expiry_from_now(
    db_session: AsyncSession, test_user: User
) -> None:
    service = SubscriptionService(db_session)
    subscription, _, _ = await service.create_subscription_order(
        test_user, SubscriptionPlan.MONTHLY
    )

    await service.activate_subscription(subscription, test_user.id)

    assert subscription.is_active is True
    assert (subscription.expires_at - subscription.starts_at).days == 30


@pytest.mark.asyncio
async def test_activate_subscription_syncs_user_tier(
    db_session: AsyncSession, test_user: User
) -> None:
    service = SubscriptionService(db_session)
    subscription, _, _ = await service.create_subscription_order(test_user, SubscriptionPlan.YEARLY)

    await service.activate_subscription(subscription, test_user.id)

    await db_session.refresh(test_user)
    assert test_user.subscription_tier == PLAN_TIER[SubscriptionPlan.YEARLY]
    assert test_user.premium_expires_at == subscription.expires_at


@pytest.mark.asyncio
async def test_activate_subscription_extends_from_existing_active_subscriptions_expiry(
    db_session: AsyncSession, test_user: User
) -> None:
    now = datetime.now(UTC)
    existing_active = Subscription(
        user_id=test_user.id,
        plan=SubscriptionPlan.MONTHLY,
        starts_at=now - timedelta(days=10),
        expires_at=now + timedelta(days=20),
        is_active=True,
    )
    db_session.add(existing_active)
    await db_session.commit()

    service = SubscriptionService(db_session)
    new_subscription, _, _ = await service.create_subscription_order(
        test_user, SubscriptionPlan.MONTHLY
    )

    await service.activate_subscription(new_subscription, test_user.id)

    assert new_subscription.starts_at == existing_active.expires_at
    assert new_subscription.expires_at == existing_active.expires_at + timedelta(days=30)


@pytest.mark.asyncio
async def test_get_active_subscription_finds_the_active_one(
    db_session: AsyncSession, test_user: User
) -> None:
    service = SubscriptionService(db_session)
    subscription, _, _ = await service.create_subscription_order(
        test_user, SubscriptionPlan.MONTHLY
    )
    await service.activate_subscription(subscription, test_user.id)

    active = await service.get_active_subscription(test_user)

    assert active is not None
    assert active.id == subscription.id


@pytest.mark.asyncio
async def test_deactivate_subscription_resets_user_tier_to_free(
    db_session: AsyncSession, test_user: User
) -> None:
    service = SubscriptionService(db_session)
    subscription, _, _ = await service.create_subscription_order(
        test_user, SubscriptionPlan.MONTHLY
    )
    await service.activate_subscription(subscription, test_user.id)

    await service.deactivate_subscription(subscription)

    assert subscription.is_active is False
    await db_session.refresh(test_user)
    assert test_user.subscription_tier == SubscriptionTier.FREE
    assert test_user.premium_expires_at is None
