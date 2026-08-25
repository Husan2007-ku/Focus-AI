"""
Auth endpoint'lari uchun request/response sxemalari.
"""

import re
import uuid

from pydantic import BaseModel, Field, field_validator

PHONE_REGEX = re.compile(r"^\+998\d{9}$")


class OTPRequestSchema(BaseModel):
    phone_number: str = Field(..., examples=["+998901234567"])

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        if not PHONE_REGEX.match(value):
            raise ValueError("Telefon raqami +998XXXXXXXXX formatida bo'lishi kerak.")
        return value


class OTPVerifySchema(BaseModel):
    phone_number: str
    code: str = Field(..., min_length=6, max_length=6)

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        if not PHONE_REGEX.match(value):
            raise ValueError("Telefon raqami +998XXXXXXXXX formatida bo'lishi kerak.")
        return value


class GoogleAuthSchema(BaseModel):
    id_token: str


class RefreshTokenSchema(BaseModel):
    refresh_token: str


class TokenResponseSchema(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponseSchema(BaseModel):
    id: uuid.UUID
    phone_number: str | None
    email: str | None
    full_name: str | None
    subscription_tier: str
    is_active: bool

    model_config = {"from_attributes": True}
