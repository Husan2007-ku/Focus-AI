"""
Obuna (Premium/Yillik) biznes logikasi.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
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
from app.utils.payment_ref import PaymentTargetKind, build_payment_ref

logger = get_logger(__name__)


class SubscriptionService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_subscription_order(
        self, user: User, plan: SubscriptionPlan
    ) -> tuple[Subscription, str, str]:
        price = PLAN_PRICES_SOM[plan]
        now = datetime.now(timezone.utc)

        subscription = Subscription(
            user_id=user.id,
            plan=plan,
            starts_at=now,
            expires_at=now + timedelta(days=PLAN_DURATION_DAYS[plan]),
            is_active=False,
        )
        self.db.add(subscription)
        await self.db.commit()
        await self.db.refresh(subscription)

        ref = build_payment_ref(PaymentTargetKind.SUBSCRIPTION, subscription.id)
        payme_url = generate_payme_checkout_url(ref, price)
        click_url = click_client.generate_checkout_url(ref, price)

        logger.info(
            "subscription_order_created", user_id=str(user.id), subscription_id=str(subscription.id), plan=plan.value
        )
        return subscription, payme_url, click_url

    async def get_subscription_by_id(self, subscription_id: uuid.UUID) -> Subscription | None:
        result = await self.db.execute(select(Subscription).where(Subscription.id == subscription_id))
        return result.scalar_one_or_none()

    async def get_active_subscription(self, user: User) -> Subscription | None:
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(Subscription)
            .where(
                Subscription.user_id == user.id,
                Subscription.is_active.is_(True),
                Subscription.expires_at > now,
            )
            .order_by(Subscription.expires_at.desc())
        )
        return result.scalars().first()

    async def activate_subscription(self, subscription: Subscription, user_id: uuid.UUID) -> None:
        """To'lov muvaffaqiyatli qabul qilinganda chaqiriladi."""
        now = datetime.now(timezone.utc)

        # Agar foydalanuvchida hali amal qiluvchi obuna bo'lsa, yangisini shu
        # muddat tugagandan keyin boshlaymiz (uzaytirish), tugagan bo'lsa — hozirdan.
        result = await self.db.execute(
            select(Subscription).where(
                Subscription.user_id == user_id,
                Subscription.is_active.is_(True),
                Subscription.expires_at > now,
                Subscription.id != subscription.id,
            )
        )
        current_active = result.scalars().first()

        duration = PLAN_DURATION_DAYS[subscription.plan]
        if current_active is not None:
            subscription.starts_at = current_active.expires_at
            subscription.expires_at = current_active.expires_at + timedelta(days=duration)
        else:
            subscription.starts_at = now
            subscription.expires_at = now + timedelta(days=duration)

        subscription.is_active = True
        await self.db.commit()

        await self._sync_user_tier(user_id)

        logger.info("subscription_activated", subscription_id=str(subscription.id))

    async def deactivate_subscription(self, subscription: Subscription) -> None:
        """To'lov bekor qilinganda (Payme CancelTransaction) chaqiriladi."""
        subscription.is_active = False
        await self.db.commit()
        await self._sync_user_tier(subscription.user_id)

        logger.warning("subscription_deactivated", subscription_id=str(subscription.id))

    # ── Ichki yordamchi metodlar ─────────────────────────────
    async def _sync_user_tier(self, user_id: uuid.UUID) -> None:
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            return

        now = datetime.now(timezone.utc)
        active_result = await self.db.execute(
            select(Subscription)
            .where(
                Subscription.user_id == user_id,
                Subscription.is_active.is_(True),
                Subscription.expires_at > now,
            )
            .order_by(Subscription.expires_at.desc())
        )
        active_subscription = active_result.scalars().first()

        if active_subscription is not None:
            user.subscription_tier = PLAN_TIER[active_subscription.plan]
            user.premium_expires_at = active_subscription.expires_at
        else:
            user.subscription_tier = SubscriptionTier.FREE
            user.premium_expires_at = None

        await self.db.commit()
