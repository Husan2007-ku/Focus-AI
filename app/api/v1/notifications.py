"""
Notification/Device endpoint'lari.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.notification import DeviceRegisterSchema, DeviceResponseSchema
from app.services.notification_service import NotificationService

router = APIRouter()


@router.post("/devices", response_model=DeviceResponseSchema, status_code=status.HTTP_201_CREATED)
async def register_device(
    payload: DeviceRegisterSchema,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DeviceResponseSchema:
    """
    Mobil qurilmaning FCM push token'ini ro'yxatga oladi. Ilova har ochilganda
    (yoki token yangilanganda) shu endpoint chaqirilishi kerak.
    """
    service = NotificationService(db)
    device = await service.register_device(current_user, payload.fcm_token, payload.platform)
    return DeviceResponseSchema.model_validate(device)
