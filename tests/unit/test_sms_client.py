"""
`EskizSMSClient.send_otp` uchun testlar.

Eng muhim holat: SMS provider sozlanmagan bo'lsa (lokal/dev muhit),
haqiqiy Eskiz'ga so'rov yubormasdan kodni log'ga yozib, xatosiz qaytishi
kerak — aks holda `SMS_PROVIDER_*` bo'sh bo'lgan har qanday dev/test
muhitida OTP so'rash butunlay ishlamay qoladi.
"""

from unittest.mock import AsyncMock

import pytest

from app.integrations.sms_client import EskizSMSClient


@pytest.mark.asyncio
async def test_send_otp_dev_fallback_when_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    client = EskizSMSClient()
    client.base_url = ""
    client.email = ""
    client._http.post = AsyncMock(
        side_effect=AssertionError("Eskiz'ga so'rov yuborilmasligi kerak")
    )

    # Xatosiz qaytishi kerak — haqiqiy HTTP so'rov yuborilmaydi.
    await client.send_otp("+998901234567", "123456")


@pytest.mark.asyncio
async def test_send_otp_calls_real_api_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    client = EskizSMSClient()
    client.base_url = "https://notify.eskiz.uz/api"
    client.email = "test@example.com"

    monkeypatch.setattr(client, "_get_token", AsyncMock(return_value="fake-token"))
    mock_response = AsyncMock()
    mock_response.raise_for_status = lambda: None
    client._http.post = AsyncMock(return_value=mock_response)

    await client.send_otp("+998901234567", "123456")

    client._http.post.assert_awaited_once()
    _, kwargs = client._http.post.call_args
    assert kwargs["data"]["mobile_phone"] == "998901234567"
