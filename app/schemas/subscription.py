"""
Obuna endpoint'lari uchun sxemalar.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.subscription import SubscriptionPlan


class CreateSubscriptionSchema(BaseModel):
    plan: SubscriptionPlan


class SubscriptionResponseSchema(BaseModel):
    id: uuid.UUID
    plan: SubscriptionPlan
    starts_at: datetime
    expires_at: datetime
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class SubscriptionWithPaymentSchema(SubscriptionResponseSchema):
    payme_checkout_url: str
    click_checkout_url: str
