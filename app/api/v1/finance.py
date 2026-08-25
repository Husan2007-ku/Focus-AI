"""
Foydalanuvchi tomonidan chaqiriladigan moliyaviy javobgarlik endpoint'lari.
To'lov webhook'lari uchun `payments.py`ga qarang.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.finance import (
    CommitmentResponseSchema,
    CommitmentWithPaymentSchema,
    CreateCommitmentSchema,
    LedgerEntryResponseSchema,
)
from app.services.finance_service import FinanceService

router = APIRouter()


@router.post("/commitments", response_model=CommitmentWithPaymentSchema, status_code=201)
async def create_commitment(
    payload: CreateCommitmentSchema,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CommitmentWithPaymentSchema:
    """
    Yangi moliyaviy maqsad yaratadi va Payme checkout URL'ini qaytaradi.
    Maqsad to'lov qabul qilinmaguncha `pending_payment` holatida qoladi.
    """
    service = FinanceService(db)
    commitment, payme_url, click_url = await service.create_commitment(current_user, payload)
    return CommitmentWithPaymentSchema(
        **CommitmentResponseSchema.model_validate(commitment).model_dump(),
        payme_checkout_url=payme_url,
        click_checkout_url=click_url,
    )


@router.get("/commitments", response_model=list[CommitmentResponseSchema])
async def list_commitments(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CommitmentResponseSchema]:
    """Foydalanuvchining barcha moliyaviy maqsadlari."""
    service = FinanceService(db)
    commitments = await service.list_commitments(current_user)
    return [CommitmentResponseSchema.model_validate(c) for c in commitments]


@router.get("/commitments/{commitment_id}", response_model=CommitmentResponseSchema)
async def get_commitment(
    commitment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CommitmentResponseSchema:
    """Bitta moliyaviy maqsad tafsilotlari."""
    service = FinanceService(db)
    commitment = await service.get_commitment(current_user, commitment_id)
    return CommitmentResponseSchema.model_validate(commitment)


@router.get("/ledger", response_model=list[LedgerEntryResponseSchema])
async def list_ledger(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[LedgerEntryResponseSchema]:
    """Foydalanuvchining to'liq pul harakati tarixi (audit)."""
    service = FinanceService(db)
    entries = await service.list_ledger_entries(current_user)
    return [LedgerEntryResponseSchema.model_validate(e) for e in entries]
