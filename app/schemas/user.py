"""
Foydalanuvchi profili (users.py) uchun sxemalar.

`UserResponseSchema` (`app/schemas/auth.py`) — autentifikatsiya konteksti
uchun qisqa shakl (`/auth/me`). Bu yerdagi `UserProfileSchema` — to'liq
profil ma'lumotlari (`/users/me`).
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class UserProfileSchema(BaseModel):
    id: uuid.UUID
    phone_number: str | None
    email: str | None
    full_name: str | None
    age: int | None
    goal: str | None
    avatar_url: str | None
    subscription_tier: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserProfileUpdateSchema(BaseModel):
    """PATCH so'rovi uchun — barcha maydonlar ixtiyoriy, faqat yuborilganlari
    yangilanadi (`exclude_unset=True` bilan servis qatlamida qo'llaniladi)."""

    full_name: str | None = Field(default=None, max_length=255)
    age: int | None = Field(default=None, ge=1, le=120)
    goal: str | None = Field(default=None, max_length=2000)
    avatar_url: str | None = Field(default=None, max_length=500)
