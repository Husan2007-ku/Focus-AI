"""
Moliyaviy javobgarlik endpoint'lari uchun sxemalar.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.models.finance import CommitmentStatus

MIN_COMMITMENT_AMOUNT = Decimal("10000")  # 10 000 so'm
MAX_COMMITMENT_AMOUNT = Decimal("5000000")  # 5 000 000 so'm — ehtiyot chorasi


class CreateCommitmentSchema(BaseModel):
    goal_description: str = Field(..., min_length=1, max_length=1000)
    amount: Decimal = Field(..., description="So'mda, masalan 50000")
    target_focus_minutes: int = Field(
        ..., ge=1, le=10080, description="Maqsad davomida jami fokus daqiqasi"
    )
    deadline: datetime
    beneficiary_note: str | None = Field(default=None, max_length=255)

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, value: Decimal) -> Decimal:
        if value < MIN_COMMITMENT_AMOUNT:
            raise ValueError(f"Minimal summa {MIN_COMMITMENT_AMOUNT} so'm.")
        if value > MAX_COMMITMENT_AMOUNT:
            raise ValueError(f"Maksimal summa {MAX_COMMITMENT_AMOUNT} so'm.")
        return value


class CommitmentResponseSchema(BaseModel):
    id: uuid.UUID
    goal_description: str
    amount: Decimal
    target_focus_minutes: int
    deadline: datetime
    beneficiary_note: str | None
    status: CommitmentStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class CommitmentWithPaymentSchema(CommitmentResponseSchema):
    payme_checkout_url: str
    click_checkout_url: str


class LedgerEntryResponseSchema(BaseModel):
    id: uuid.UUID
    entry_type: str
    amount: Decimal
    commitment_id: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}
