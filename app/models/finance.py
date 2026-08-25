"""
Moliyaviy javobgarlik modellari.

Dizayn qarori — LEDGER PATTERN (TZ 3-band, "Fail-safe pul tizimi"):
Foydalanuvchining balansi hech qachon to'g'ridan-to'g'ri bitta ustunda
saqlanmaydi va o'zgartirilmaydi. Buning o'rniga har bir pul harakati
(`LedgerEntry`) alohida, o'zgarmas yozuv sifatida saqlanadi. Joriy holatni
bilish uchun shu yozuvlar yig'indisi hisoblanadi. Bu quyidagilarni beradi:
  1. To'liq audit — har doim "nega bunday" degan savolga javob bor.
  2. Xatoni tuzatish xavfsizligi — noto'g'ri operatsiya ustidan yozilmaydi,
     balki tuzatuvchi (kompensatsion) yozuv qo'shiladi.

`Transaction` — Payme/Click kabi tashqi to'lov tizimlaridan kelgan xom
ma'lumot (ularning protokoliga mos holda). `LedgerEntry` — bizning ichki,
provayderdan mustaqil pul kitobimiz. Bittasi ikkinchisiga asos bo'ladi,
lekin ular alohida narsalar.
"""

import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class CommitmentStatus(str, enum.Enum):
    PENDING_PAYMENT = "pending_payment"  # yaratilgan, lekin hali to'lov qilinmagan
    ACTIVE = "active"  # to'lov qabul qilingan, maqsad davom etmoqda
    SUCCEEDED = "succeeded"  # maqsadga erishildi — pul qaytariladi
    FAILED = "failed"  # maqsadga erishilmadi — pul xayriyaga o'tkaziladi
    CANCELLED = "cancelled"  # to'lovdan oldin bekor qilingan


class PaymentProvider(str, enum.Enum):
    PAYME = "payme"
    CLICK = "click"


class TransactionState(str, enum.Enum):
    CREATED = "created"
    PERFORMED = "performed"
    CANCELLED = "cancelled"


class LedgerEntryType(str, enum.Enum):
    DEPOSIT = "deposit"  # foydalanuvchi pul qo'ydi
    REFUND = "refund"  # maqsad bajarildi, pul qaytarildi
    DONATION = "donation"  # maqsad bajarilmadi, pul xayriyaga ketdi
    CANCELLATION_REVERSAL = "cancellation_reversal"  # to'lov bekor qilinganda depozitni bekor qilish


class FinancialCommitment(Base):
    """Foydalanuvchining moliyaviy javobgarlik bilan qo'ygan maqsadi."""

    __tablename__ = "financial_commitments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    goal_description: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)  # so'mda

    # Muvaffaqiyat mezoni: shu davrda kamida shuncha daqiqa fokus qilingan bo'lishi kerak.
    target_focus_minutes: Mapped[int] = mapped_column(Integer, nullable=False)

    deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    beneficiary_note: Mapped[str | None] = mapped_column(
        String(255), doc="Agar maqsad bajarilmasa, pul yo'naltiriladigan xayriya nomi"
    )

    status: Mapped[CommitmentStatus] = mapped_column(
        Enum(CommitmentStatus, name="commitment_status_enum"),
        nullable=False,
        default=CommitmentStatus.PENDING_PAYMENT,
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
        return f"<FinancialCommitment {self.id} {self.status} {self.amount}>"


class TransactionPurpose(str, enum.Enum):
    COMMITMENT = "commitment"  # moliyaviy javobgarlik depoziti
    SUBSCRIPTION = "subscription"  # Premium/Yillik obuna to'lovi


class Transaction(Base):
    """Payme/Click'dan kelgan xom tranzaksiya ma'lumoti.

    Bitta Transaction faqat BITTA maqsadga xizmat qiladi — yo moliyaviy
    javobgarlik depozitiga, yo obuna to'loviga (`purpose` shuni bildiradi,
    tegishli `*_id` ustuni to'ldiriladi, ikkinchisi bo'sh qoladi).
    """

    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    purpose: Mapped[TransactionPurpose] = mapped_column(
        Enum(TransactionPurpose, name="transaction_purpose_enum"), nullable=False
    )
    commitment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("financial_commitments.id", ondelete="SET NULL"),
        index=True,
    )
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subscriptions.id", ondelete="SET NULL"),
        index=True,
    )
    provider: Mapped[PaymentProvider] = mapped_column(
        Enum(PaymentProvider, name="payment_provider_enum"), nullable=False
    )
    # Provayderning o'z tranzaksiya ID'si — bir xil provayder ichida noyob.
    provider_transaction_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)  # so'mda (provayder tiyin/so'm yuborsa ham shu yerda normalizatsiya qilinadi)
    state: Mapped[TransactionState] = mapped_column(
        Enum(TransactionState, name="transaction_state_enum"),
        nullable=False,
        default=TransactionState.CREATED,
    )
    raw_payload: Mapped[dict | None] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    performed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        return f"<Transaction {self.provider}:{self.provider_transaction_id} {self.state}>"


class LedgerEntry(Base):
    """O'zgarmas pul harakati yozuvi — audit uchun asosiy manba."""

    __tablename__ = "ledger_entries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    commitment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("financial_commitments.id", ondelete="SET NULL"), index=True
    )
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transactions.id", ondelete="SET NULL")
    )

    entry_type: Mapped[LedgerEntryType] = mapped_column(
        Enum(LedgerEntryType, name="ledger_entry_type_enum"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)  # har doim musbat

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<LedgerEntry {self.entry_type} {self.amount} user={self.user_id}>"
