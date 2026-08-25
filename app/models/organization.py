"""
Tashkilot (Organization) modeli — B2B mijozlar (universitetlar, kompaniyalar)
uchun. Faza 1-3'da `User.organization_id` ustuni oldindan tayyorlab qo'yilgan
edi — endi shu tashkilotning o'zini ifodalovchi jadval qo'shiladi.

Dizayn tamoyili: bitta `User` bitta (yoki hech qanday) tashkilotga tegishli
bo'lishi mumkin — ko'p-ko'pga (many-to-many) emas, oddiy ko'p-birga
(many-to-one) munosabat. Bu B2B uchun eng keng tarqalgan holat (xodim bitta
kompaniyaga tegishli) va kelajakda kengaytirish mumkin bo'lgan sodda asos.
"""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class OrganizationStatus(str, enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"  # to'lov muammosi yoki shartnoma tugagan


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Taklif havolasi/kodi orqali xodimlar o'z-o'zini tashkilotga qo'shishi uchun.
    invite_code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    seat_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    status: Mapped[OrganizationStatus] = mapped_column(
        Enum(OrganizationStatus, name="organization_status_enum"),
        nullable=False,
        default=OrganizationStatus.ACTIVE,
    )

    # Tashkilotni boshqaruvchi admin foydalanuvchi (User jadvalidagi oddiy foydalanuvchi).
    admin_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Organization {self.name} ({self.status})>"
