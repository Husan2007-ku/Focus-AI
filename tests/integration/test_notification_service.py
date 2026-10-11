"""NotificationService uchun testlar — qurilma ro'yxatga olish va push yuborish.

`firebase_client.send_to_tokens` tashqi FCM chaqiruvi qiladi — shuning uchun
monkeypatch bilan almashtiriladi (haqiqiy Firebase kerak emas, faqat
NotificationService'ning o'z logikasi — token tanlash, is_active filtri,
yaroqsiz token'larni o'chirish — tekshiriladi).
"""

from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device, DevicePlatform
from app.models.user import User
from app.services.notification_service import NotificationService


@pytest.mark.asyncio
async def test_register_device_creates_new_device(
    db_session: AsyncSession, test_user: User
) -> None:
    service = NotificationService(db_session)

    device = await service.register_device(test_user, "fcm-token-1", DevicePlatform.ANDROID)

    assert device.user_id == test_user.id
    assert device.fcm_token == "fcm-token-1"
    assert device.is_active is True


@pytest.mark.asyncio
async def test_register_device_relinks_existing_token_to_new_user(
    db_session: AsyncSession, test_user: User
) -> None:
    """Token boshqa foydalanuvchiga tegishli bo'lsa (masalan qurilma qayta
    sotilgan), qayta ro'yxatga olinganda yangi foydalanuvchiga bog'lanishi kerak —
    yangi qator yaratilmasligi kerak."""
    other_user = User(
        phone_number="+998901112233", primary_auth_provider=test_user.primary_auth_provider
    )
    db_session.add(other_user)
    await db_session.commit()

    service = NotificationService(db_session)
    first = await service.register_device(other_user, "shared-token", DevicePlatform.IOS)
    relinked = await service.register_device(test_user, "shared-token", DevicePlatform.ANDROID)

    assert first.id == relinked.id
    assert relinked.user_id == test_user.id
    assert relinked.platform == DevicePlatform.ANDROID

    result = await db_session.execute(select(Device).where(Device.fcm_token == "shared-token"))
    assert len(result.scalars().all()) == 1


@pytest.mark.asyncio
async def test_send_to_user_with_no_devices_does_not_call_firebase(
    db_session: AsyncSession, test_user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_send = AsyncMock(side_effect=AssertionError("Firebase chaqirilmasligi kerak"))
    monkeypatch.setattr(
        "app.services.notification_service.firebase_client.send_to_tokens", mock_send
    )

    service = NotificationService(db_session)
    await service.send_to_user(test_user.id, "Sarlavha", "Matn")

    mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_send_to_user_sends_only_to_active_devices(
    db_session: AsyncSession, test_user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = NotificationService(db_session)
    await service.register_device(test_user, "active-token", DevicePlatform.ANDROID)
    inactive = await service.register_device(test_user, "inactive-token", DevicePlatform.IOS)
    inactive.is_active = False
    await db_session.commit()

    mock_send = AsyncMock(return_value=[])
    monkeypatch.setattr(
        "app.services.notification_service.firebase_client.send_to_tokens", mock_send
    )

    await service.send_to_user(test_user.id, "Sarlavha", "Matn")

    mock_send.assert_awaited_once()
    args, _ = mock_send.call_args
    assert args[0] == ["active-token"]


@pytest.mark.asyncio
async def test_send_to_user_deactivates_invalid_tokens(
    db_session: AsyncSession, test_user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = NotificationService(db_session)
    device = await service.register_device(test_user, "stale-token", DevicePlatform.ANDROID)

    mock_send = AsyncMock(return_value=["stale-token"])
    monkeypatch.setattr(
        "app.services.notification_service.firebase_client.send_to_tokens", mock_send
    )

    await service.send_to_user(test_user.id, "Sarlavha", "Matn")

    await db_session.refresh(device)
    assert device.is_active is False
