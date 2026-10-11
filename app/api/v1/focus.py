"""
Focus Session endpoint'lari.
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.focus import (
    FocusSessionHistorySchema,
    FocusSessionResponseSchema,
    FocusSessionStartSchema,
)
from app.services.focus_service import FocusSessionService

router = APIRouter()


@router.post("/start", response_model=FocusSessionResponseSchema, status_code=201)
async def start_focus_session(
    payload: FocusSessionStartSchema,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FocusSessionResponseSchema:
    """Yangi fokus seansini boshlaydi. Foydalanuvchida faol seans bo'lmasligi kerak."""
    service = FocusSessionService(db)
    session = await service.start_session(current_user, payload)
    return FocusSessionResponseSchema.model_validate(session)


@router.post("/{session_id}/complete", response_model=FocusSessionResponseSchema)
async def complete_focus_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FocusSessionResponseSchema:
    """Faol seansni muvaffaqiyatli yakunlangan deb belgilaydi."""
    service = FocusSessionService(db)
    session = await service.complete_session(current_user, session_id)
    return FocusSessionResponseSchema.model_validate(session)


@router.post("/{session_id}/cancel", response_model=FocusSessionResponseSchema)
async def cancel_focus_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FocusSessionResponseSchema:
    """Faol seansni foydalanuvchi tomonidan bekor qilingan deb belgilaydi."""
    service = FocusSessionService(db)
    session = await service.cancel_session(current_user, session_id)
    return FocusSessionResponseSchema.model_validate(session)


@router.post("/{session_id}/fail", response_model=FocusSessionResponseSchema)
async def fail_focus_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FocusSessionResponseSchema:
    """
    Mobil ilova bloklangan ilovaga kirishga urinishni aniqlaganda chaqiradi —
    seans "buzilgan" deb belgilanadi.
    """
    service = FocusSessionService(db)
    session = await service.fail_session(current_user, session_id)
    return FocusSessionResponseSchema.model_validate(session)


@router.get("/active", response_model=FocusSessionResponseSchema | None)
async def get_active_focus_session(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FocusSessionResponseSchema | None:
    """Joriy faol seansni qaytaradi, agar mavjud bo'lmasa — `null`."""
    service = FocusSessionService(db)
    session = await service.get_active_session(current_user)
    return FocusSessionResponseSchema.model_validate(session) if session else None


@router.get("/history", response_model=FocusSessionHistorySchema)
async def get_focus_session_history(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FocusSessionHistorySchema:
    """Foydalanuvchining o'tgan fokus seanslari tarixi (sahifalangan)."""
    service = FocusSessionService(db)
    items, total = await service.get_history(current_user, limit, offset)
    return FocusSessionHistorySchema(
        items=[FocusSessionResponseSchema.model_validate(item) for item in items],
        total=total,
    )
