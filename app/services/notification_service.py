"""
Notification biznes logikasi: qurilmalarni ro'yxatga olish va push yuborish.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.integrations.firebase_client import firebase_client
from app.models.device import Device, DevicePlatform
from app.models.user import User

logger = get_logger(__name__)


class NotificationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def register_device(self, user: User, fcm_token: str, platform: DevicePlatform) -> Device:
        result = await self.db.execute(select(Device).where(Device.fcm_token == fcm_token))
        device = result.scalar_one_or_none()

        if device is not None:
            # Token boshqa foydalanuvchiga tegishli bo'lishi mumkin (masalan, qurilma
            # qayta sotilgan yoki eski hisobdan chiqilgan) — qayta bog'laymiz.
            device.user_id = user.id
            device.platform = platform
            device.is_active = True
        else:
            device = Device(user_id=user.id, fcm_token=fcm_token, platform=platform)
            self.db.add(device)

        await self.db.commit()
        await self.db.refresh(device)

        logger.info("device_registered", user_id=str(user.id), platform=platform.value)
        return device

    async def send_to_user(
        self, user_id: uuid.UUID, title: str, body: str, data: dict[str, str] | None = None
    ) -> None:
        result = await self.db.execute(
            select(Device).where(Device.user_id == user_id, Device.is_active.is_(True))
        )
        devices = list(result.scalars().all())

        if not devices:
            logger.info("no_active_devices", user_id=str(user_id))
            return

        tokens = [d.fcm_token for d in devices]
        invalid_tokens = await firebase_client.send_to_tokens(tokens, title, body, data)

        if invalid_tokens:
            await self._deactivate_tokens(invalid_tokens)

    async def _deactivate_tokens(self, tokens: list[str]) -> None:
        result = await self.db.execute(select(Device).where(Device.fcm_token.in_(tokens)))
        for device in result.scalars().all():
            device.is_active = False
        await self.db.commit()
        logger.info("devices_deactivated", count=len(tokens))
