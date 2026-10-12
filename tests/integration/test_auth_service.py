"""AuthService uchun testlar — OTP orqali telefon autentifikatsiyasi va
Google OAuth oqimi.

`sms_client.send_otp` va Google'ning `verify_oauth2_token` tashqi tarmoq
chaqiruvi qiladi — shuning uchun monkeypatch bilan almashtiriladi. Redis
(OTP kod/urinish hisoblagichi) va Postgres esa haqiqiy ulanish bilan
ishlaydi (loyihaning umumiy test konvensiyasiga mos).
"""

import uuid
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ExternalServiceError, RateLimitError, UnauthorizedError
from app.core.redis_client import redis_client
from app.models.user import AuthProvider
from app.services.auth_service import AuthService, _hash_otp


def _random_phone() -> str:
    return f"+99890{uuid.uuid4().int % 10_000_000:07d}"


@pytest.mark.asyncio
async def test_request_otp_sends_sms_and_stores_hashed_code(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_send = AsyncMock()
    monkeypatch.setattr("app.services.auth_service.sms_client.send_otp", mock_send)
    phone = _random_phone()

    await AuthService(db_session).request_otp(phone)

    mock_send.assert_awaited_once()
    sent_phone, sent_code = mock_send.call_args[0]
    assert sent_phone == phone
    stored_hash = await redis_client.get(f"otp:code:{phone}")
    assert stored_hash == _hash_otp(sent_code)


@pytest.mark.asyncio
async def test_request_otp_respects_resend_cooldown(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.services.auth_service.sms_client.send_otp", AsyncMock())
    phone = _random_phone()
    service = AuthService(db_session)
    await service.request_otp(phone)

    with pytest.raises(RateLimitError):
        await service.request_otp(phone)


@pytest.mark.asyncio
async def test_verify_otp_with_correct_code_creates_new_user_and_returns_tokens(
    db_session: AsyncSession,
) -> None:
    phone = _random_phone()
    code = "123456"
    await redis_client.setex(f"otp:code:{phone}", 300, _hash_otp(code))

    tokens = await AuthService(db_session).verify_otp(phone, code)

    assert "access_token" in tokens
    assert "refresh_token" in tokens
    assert tokens["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_verify_otp_consumes_code_so_it_cannot_be_reused(
    db_session: AsyncSession,
) -> None:
    phone = _random_phone()
    code = "123456"
    await redis_client.setex(f"otp:code:{phone}", 300, _hash_otp(code))
    service = AuthService(db_session)
    await service.verify_otp(phone, code)

    with pytest.raises(UnauthorizedError):
        await service.verify_otp(phone, code)


@pytest.mark.asyncio
async def test_verify_otp_reuses_existing_user_on_second_login(
    db_session: AsyncSession,
) -> None:
    phone = _random_phone()
    service = AuthService(db_session)

    await redis_client.setex(f"otp:code:{phone}", 300, _hash_otp("111111"))
    first_user = await service._get_or_create_user_by_phone(phone)

    await redis_client.setex(f"otp:code:{phone}", 300, _hash_otp("222222"))
    await service.verify_otp(phone, "222222")

    second_user = await service._get_or_create_user_by_phone(phone)
    assert second_user.id == first_user.id


@pytest.mark.asyncio
async def test_verify_otp_rejects_wrong_code_and_counts_attempt(
    db_session: AsyncSession,
) -> None:
    phone = _random_phone()
    await redis_client.setex(f"otp:code:{phone}", 300, _hash_otp("123456"))

    with pytest.raises(UnauthorizedError):
        await AuthService(db_session).verify_otp(phone, "000000")

    attempts = await redis_client.get(f"otp:attempts:{phone}")
    assert int(attempts) == 1


@pytest.mark.asyncio
async def test_verify_otp_rejects_when_no_code_was_requested(
    db_session: AsyncSession,
) -> None:
    phone = _random_phone()

    with pytest.raises(UnauthorizedError):
        await AuthService(db_session).verify_otp(phone, "123456")


@pytest.mark.asyncio
async def test_verify_otp_blocks_after_max_attempts(
    db_session: AsyncSession,
) -> None:
    phone = _random_phone()
    await redis_client.setex(f"otp:code:{phone}", 300, _hash_otp("123456"))
    service = AuthService(db_session)

    for _ in range(5):
        with pytest.raises(UnauthorizedError):
            await service.verify_otp(phone, "000000")

    with pytest.raises(RateLimitError):
        await service.verify_otp(phone, "123456")


@pytest.mark.asyncio
async def test_google_login_creates_new_user_and_returns_tokens(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    google_sub = str(uuid.uuid4())
    monkeypatch.setattr(
        "app.services.auth_service.google_id_token.verify_oauth2_token",
        lambda *args, **kwargs: {
            "sub": google_sub,
            "email": f"{google_sub}@example.com",
            "name": "Google Foydalanuvchi",
            "picture": "https://example.com/avatar.png",
        },
    )

    tokens = await AuthService(db_session).google_login("fake-id-token")

    assert "access_token" in tokens
    user = await AuthService(db_session).users.get_by_google_id(google_sub)
    assert user is not None
    assert user.primary_auth_provider == AuthProvider.GOOGLE
    assert user.email == f"{google_sub}@example.com"


@pytest.mark.asyncio
async def test_google_login_reuses_existing_user_by_google_id(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    google_sub = str(uuid.uuid4())
    monkeypatch.setattr(
        "app.services.auth_service.google_id_token.verify_oauth2_token",
        lambda *args, **kwargs: {"sub": google_sub, "email": None, "name": None, "picture": None},
    )
    service = AuthService(db_session)

    await service.google_login("fake-id-token-1")
    first_user = await service.users.get_by_google_id(google_sub)

    await service.google_login("fake-id-token-2")
    second_user = await service.users.get_by_google_id(google_sub)

    assert first_user.id == second_user.id


@pytest.mark.asyncio
async def test_google_login_rejects_invalid_token(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _raise_invalid(*args: object, **kwargs: object) -> None:
        raise ValueError("Token imzosi noto'g'ri")

    monkeypatch.setattr(
        "app.services.auth_service.google_id_token.verify_oauth2_token", _raise_invalid
    )

    with pytest.raises(UnauthorizedError):
        await AuthService(db_session).google_login("bad-token")


@pytest.mark.asyncio
async def test_google_login_wraps_network_errors_as_external_service_error(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _raise_network_error(*args: object, **kwargs: object) -> None:
        raise ConnectionError("Google'ga ulanib bo'lmadi")

    monkeypatch.setattr(
        "app.services.auth_service.google_id_token.verify_oauth2_token", _raise_network_error
    )

    with pytest.raises(ExternalServiceError):
        await AuthService(db_session).google_login("any-token")
