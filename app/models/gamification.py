"""
Gamification modellari: streak, XP va badge'lar.

Dizayn qarori: XP ham ledger pattern bilan saqlanadi (`xp_transactions`) —
oddiy `user.xp` maydonini o'zgartirib qo'yish o'rniga har bir XP
o'zgarishi alohida yozuv sifatida saqlanadi. Bu ikkita narsani beradi:
1. Audit — "nega foydalanuvchida shuncha XP bor" degan savolga har doim
   javob topish mumkin.
2. Xatoni tuzatish osonligi — noto'g'ri hisoblangan XP'ni butun jadvalni
   qayta yozmasdan, faqat tegishli tranzaksiyani bekor qilib tuzatish mumkin.
"""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base

if TYPE_CHECKING:
    pass


class XPReason(enum.StrEnum):
    FOCUS_SESSION_COMPLETED = "focus_session_completed"
    DAILY_ROUTINE_COMPLETED = "daily_routine_completed"
    STREAK_MILESTONE = "streak_milestone"
    BADGE_EARNED = "badge_earned"


class BadgeCode(enum.StrEnum):
    FIRST_SESSION = "first_session"
    STREAK_3 = "streak_3"
    STREAK_7 = "streak_7"
    STREAK_30 = "streak_30"
    EARLY_BIRD = "early_bird"  # ertalab 7:00 dan oldin seans boshlagan


class UserStreak(Base):
    """Har bir foydalanuvchi uchun bitta yozuv — joriy va eng yuqori streak."""

    __tablename__ = "user_streaks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    current_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    longest_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_active_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<UserStreak user={self.user_id} current={self.current_streak}>"


class XPTransaction(Base):
    __tablename__ = "xp_transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[XPReason] = mapped_column(Enum(XPReason, name="xp_reason_enum"), nullable=False)
    reference_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True)
    )  # masalan, focus_session.id

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<XPTransaction {self.user_id} +{self.amount} ({self.reason})>"


class UserBadge(Base):
    __tablename__ = "user_badges"
    __table_args__ = (UniqueConstraint("user_id", "badge_code", name="uq_user_badge"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    badge_code: Mapped[BadgeCode] = mapped_column(
        Enum(BadgeCode, name="badge_code_enum"), nullable=False
    )

    earned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<UserBadge {self.user_id} {self.badge_code}>"
