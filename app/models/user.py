"""
Foydalanuvchi modeli.

Autentifikatsiya ikki usulda bo'ladi (TZ 7-band, pitch-dek bilan mos):
- Telefon raqami + SMS OTP
- Google OAuth

Ikkalasi ham ixtiyoriy ustunlar sifatida saqlanadi (bittasi bo'lishi shart,
biznes-logika darajasida — service qatlamida — tekshiriladi), chunki
foydalanuvchi keyinchalik ikkinchi usulni ham bog'lashi mumkin.
"""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.focus_session import FocusSession


class AuthProvider(enum.StrEnum):
    """Foydalanuvchi qaysi usul bilan ro'yxatdan o'tganini bildiradi."""

    PHONE = "phone"
    GOOGLE = "google"


class SubscriptionTier(enum.StrEnum):
    """Joriy tarif darajasi — tezkor tekshiruvlar uchun denormalizatsiya qilingan
    maydon. Haqiqiy to'lov holati Faza 3'da qo'shiladigan `subscriptions`
    jadvalida saqlanadi; bu yerdagi qiymat shundan sinxronlanadi."""

    FREE = "free"
    PREMIUM = "premium"
    YEARLY = "yearly"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # ── Autentifikatsiya ───────────────────────────────────
    phone_number: Mapped[str | None] = mapped_column(String(20), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    google_id: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    primary_auth_provider: Mapped[AuthProvider] = mapped_column(
        Enum(AuthProvider, name="auth_provider_enum"), nullable=False
    )

    # ── Profil ─────────────────────────────────────────────
    full_name: Mapped[str | None] = mapped_column(String(255))
    age: Mapped[int | None] = mapped_column(Integer)
    goal: Mapped[str | None] = mapped_column(Text)  # foydalanuvchining asosiy maqsadi
    avatar_url: Mapped[str | None] = mapped_column(String(500))

    # ── Tarif holati ───────────────────────────────────────
    subscription_tier: Mapped[SubscriptionTier] = mapped_column(
        Enum(SubscriptionTier, name="subscription_tier_enum"),
        nullable=False,
        default=SubscriptionTier.FREE,
    )
    premium_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # ── B2B (Faza 4) ───────────────────────────────────────
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL"), index=True
    )

    # ── Holat ──────────────────────────────────────────────
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # ── Vaqt belgilari ─────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        identifier = self.phone_number or self.email or str(self.id)
        return f"<User {identifier}>"

    # ── Munosabatlar ───────────────────────────────────────
    focus_sessions: Mapped[list["FocusSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
