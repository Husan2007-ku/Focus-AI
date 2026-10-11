"""
Obuna (Premium/Yillik) biznes logikasi.

DB bilan ishlash `SubscriptionRepository`ga o'tkazilgan (TZ v2.0, 3-band).
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.integrations import click_client
from app.integrations.payme_client import generate_checkout_url as generate_payme_checkout_url
from app.models.subscription import (
    PLAN_DURATION_DAYS,
    PLAN_PRICES_SOM,
    PLAN_TIER,
    Subscription,
    SubscriptionPlan,
)
from app.models.user import SubscriptionTier, User
from app.repositories.subscription_repository import SubscriptionRepository
from app.utils.payment_ref import PaymentTargetKind, build_payment_ref

logger = get_logger(__name__)


class SubscriptionService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = SubscriptionRepository(db)

    async def create_subscription_order(
        self, user: User, plan: SubscriptionPlan
    ) -> tuple[Subscription, str, str]:
        price = PLAN_PRICES_SOM[plan]
        now = datetime.now(UTC)

        subscription = Subscription(
            user_id=user.id,
            plan=plan,
            starts_at=now,
            expires_at=now + timedelta(days=PLAN_DURATION_DAYS[plan]),
            is_active=False,
        )
        subscription = await self.repo.add(subscription)

        ref = build_payment_ref(PaymentTargetKind.SUBSCRIPTION, subscription.id)
        payme_url = generate_payme_checkout_url(ref, price)
        click_url = click_client.generate_checkout_url(ref, price)

        logger.info(
            "subscription_order_created",
            user_id=str(user.id),
            subscription_id=str(subscription.id),
            plan=plan.value,
        )
        return subscription, payme_url, click_url

    async def get_subscription_by_id(self, subscription_id: uuid.UUID) -> Subscription | None:
        return await self.repo.get_by_id(subscription_id)

    async def get_active_subscription(self, user: User) -> Subscription | None:
        now = datetime.now(UTC)
        return await self.repo.get_active_for_user(user.id, now)

    async def activate_subscription(self, subscription: Subscription, user_id: uuid.UUID) -> None:
        """To'lov muvaffaqiyatli qabul qilinganda chaqiriladi."""
        now = datetime.now(UTC)

        # Agar foydalanuvchida hali amal qiluvchi obuna bo'lsa, yangisini shu
        # muddat tugagandan keyin boshlaymiz (uzaytirish), tugagan bo'lsa — hozirdan.
        current_active = await self.repo.get_active_for_user(
            user_id, now, exclude_id=subscription.id
        )

        duration = PLAN_DURATION_DAYS[subscription.plan]
        if current_active is not None:
            subscription.starts_at = current_active.expires_at
            subscription.expires_at = current_active.expires_at + timedelta(days=duration)
        else:
            subscription.starts_at = now
            subscription.expires_at = now + timedelta(days=duration)

        subscription.is_active = True
        await self.repo.commit()

        await self._sync_user_tier(user_id)

        logger.info("subscription_activated", subscription_id=str(subscription.id))

    async def deactivate_subscription(self, subscription: Subscription) -> None:
        """To'lov bekor qilinganda (Payme CancelTransaction) chaqiriladi."""
        subscription.is_active = False
        await self.repo.commit()
        await self._sync_user_tier(subscription.user_id)

        logger.warning("subscription_deactivated", subscription_id=str(subscription.id))

    # ── Ichki yordamchi metodlar ─────────────────────────────
    async def _sync_user_tier(self, user_id: uuid.UUID) -> None:
        user = await self.repo.get_user_by_id(user_id)
        if user is None:
            return

        now = datetime.now(UTC)
        active_subscription = await self.repo.get_active_for_user(user_id, now)

        if active_subscription is not None:
            user.subscription_tier = PLAN_TIER[active_subscription.plan]
            user.premium_expires_at = active_subscription.expires_at
        else:
            user.subscription_tier = SubscriptionTier.FREE
            user.premium_expires_at = None

        await self.repo.commit()
