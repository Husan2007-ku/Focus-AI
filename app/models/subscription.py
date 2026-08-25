"""
Obuna modeli — Premium/Yillik tariflarni boshqarish uchun.

`User.subscription_tier` — tezkor tekshiruv uchun denormalizatsiya qilingan
maydon (masalan, AI kunlik limitini aniqlashda). `Subscription` esa haqiqiy
to'lov tarixi va amal qilish muddatini saqlaydigan manba — ikkalasi
`SubscriptionService` orqali sinxronlanadi.
"""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base
from app.models.user import SubscriptionTier

if TYPE_CHECKING:
    from app.models.user import User


class SubscriptionPlan(str, enum.Enum):
    MONTHLY = "monthly"  # 19 900 so'm/oy
    YEARLY = "yearly"  # 149 900 so'm/yil


PLAN_PRICES_SOM: dict[SubscriptionPlan, int] = {
    SubscriptionPlan.MONTHLY: 19_900,
    SubscriptionPlan.YEARLY: 149_900,
}

PLAN_DURATION_DAYS: dict[SubscriptionPlan, int] = {
    SubscriptionPlan.MONTHLY: 30,
    SubscriptionPlan.YEARLY: 365,
}

PLAN_TIER: dict[SubscriptionPlan, SubscriptionTier] = {
    SubscriptionPlan.MONTHLY: SubscriptionTier.PREMIUM,
    SubscriptionPlan.YEARLY: SubscriptionTier.YEARLY,
}


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    plan: Mapped[SubscriptionPlan] = mapped_column(
        Enum(SubscriptionPlan, name="subscription_plan_enum"), nullable=False
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # to'lov qabul qilingach True

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Subscription {self.user_id} {self.plan} active={self.is_active}>"
