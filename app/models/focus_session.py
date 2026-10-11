"""
Fokus seansi modeli — foydalanuvchining har bir "fokus vaqti" yozuvi.

Bitta seans: foydalanuvchi timer boshlaydi -> muayyan ilovalar bloklanadi
(mobil tomonda) -> seans tugaydi (muvaffaqiyatli yoki bekor qilingan holda).
"""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class FocusSessionStatus(enum.StrEnum):
    ACTIVE = "active"  # hozir davom etmoqda
    COMPLETED = "completed"  # to'liq bajarilgan
    CANCELLED = "cancelled"  # foydalanuvchi tugatmasdan to'xtatgan
    FAILED = "failed"  # bloklangan ilovaga kirishga urinish tufayli buzilgan


class FocusSession(Base):
    __tablename__ = "focus_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # ── Rejalashtirilgan va haqiqiy davomiylik ─────────────
    planned_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_duration_minutes: Mapped[int | None] = mapped_column(Integer)

    status: Mapped[FocusSessionStatus] = mapped_column(
        Enum(FocusSessionStatus, name="focus_session_status_enum"),
        nullable=False,
        default=FocusSessionStatus.ACTIVE,
    )

    # ── Bloklangan ilovalar ro'yxati (paket nomlari) ───────
    # Masalan: ["com.instagram.android", "com.zhiliaoapp.musically"]
    blocked_apps: Mapped[list[str] | None] = mapped_column(ARRAY(String(255)))

    # ── Vaqt belgilari ─────────────────────────────────────
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ── Munosabatlar ───────────────────────────────────────
    user: Mapped["User"] = relationship(back_populates="focus_sessions")  # noqa: F821

    def __repr__(self) -> str:
        return f"<FocusSession {self.id} status={self.status}>"
