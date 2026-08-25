"""
Kunlik Routine modeli — foydalanuvchining ertalabki rejasi va
kechqurungi hisoboti, shuningdek AI'ning shu kunga oid fikri.

Bitta foydalanuvchi uchun bir kunda faqat bitta yozuv bo'ladi
(`user_id` + `routine_date` unique juftlik).
"""

import enum
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class RoutineStatus(str, enum.Enum):
    PLANNED = "planned"  # faqat ertalabki reja kiritilgan
    REPORTED = "reported"  # kechqurungi hisobot ham kiritilgan
    MISSED = "missed"  # kun tugagan, lekin hisobot kiritilmagan


class DailyRoutine(Base):
    __tablename__ = "daily_routines"
    __table_args__ = (UniqueConstraint("user_id", "routine_date", name="uq_user_routine_date"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    routine_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # ── Ertalabki reja ─────────────────────────────────────
    morning_plan: Mapped[str | None] = mapped_column(Text)
    planned_focus_minutes: Mapped[int | None] = mapped_column(Integer)

    # ── Kechqurungi hisobot ────────────────────────────────
    evening_report: Mapped[str | None] = mapped_column(Text)
    self_rating: Mapped[int | None] = mapped_column(Integer)  # 1-5 shkala bo'yicha o'z bahosi

    # ── AI fikri ───────────────────────────────────────────
    ai_feedback: Mapped[str | None] = mapped_column(Text)

    status: Mapped[RoutineStatus] = mapped_column(
        Enum(RoutineStatus, name="routine_status_enum"),
        nullable=False,
        default=RoutineStatus.PLANNED,
    )

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
        return f"<DailyRoutine {self.user_id} {self.routine_date}>"
