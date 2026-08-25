"""
Notification/Device endpoint'lari uchun sxemalar.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.device import DevicePlatform


class DeviceRegisterSchema(BaseModel):
    fcm_token: str
    platform: DevicePlatform


class DeviceResponseSchema(BaseModel):
    id: uuid.UUID
    platform: DevicePlatform
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
