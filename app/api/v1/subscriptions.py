"""
Obuna endpoint'lari.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.subscription import (
    CreateSubscriptionSchema,
    SubscriptionResponseSchema,
    SubscriptionWithPaymentSchema,
)
from app.services.subscription_service import SubscriptionService

router = APIRouter()


@router.post("/", response_model=SubscriptionWithPaymentSchema, status_code=201)
async def create_subscription(
    payload: CreateSubscriptionSchema,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionWithPaymentSchema:
    """Yangi obuna buyurtmasi yaratadi va to'lov havolalarini qaytaradi."""
    service = SubscriptionService(db)
    subscription, payme_url, click_url = await service.create_subscription_order(
        current_user, payload.plan
    )
    return SubscriptionWithPaymentSchema(
        **SubscriptionResponseSchema.model_validate(subscription).model_dump(),
        payme_checkout_url=payme_url,
        click_checkout_url=click_url,
    )


@router.get("/active", response_model=SubscriptionResponseSchema | None)
async def get_active_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionResponseSchema | None:
    """Foydalanuvchining joriy amaldagi obunasi, agar bo'lmasa — `null`."""
    service = SubscriptionService(db)
    subscription = await service.get_active_subscription(current_user)
    return SubscriptionResponseSchema.model_validate(subscription) if subscription else None
