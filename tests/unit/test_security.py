"""
`app.core.security` uchun testlar — JWT token yaratish, tekshirish,
refresh rotatsiyasi va bekor qilish (logout) to'g'ri ishlashini tasdiqlaydi.

Bu modul haqiqiy Redis'ga ulanadi (konteyner ichida `redis` xizmati mavjud),
shuning uchun soxtalashtirish (mock) shart emas — refresh token holati
haqiqatan Redis'da saqlanadi va o'chiriladi.
"""

import uuid

import pytest

from app.core.exceptions import UnauthorizedError
from app.core.security import (
    create_access_token,
    issue_token_pair,
    revoke_refresh_token,
    rotate_refresh_token,
    verify_access_token,
)


@pytest.mark.asyncio
async def test_access_token_roundtrip() -> None:
    user_id = str(uuid.uuid4())
    token = await create_access_token(user_id)

    resolved_user_id = await verify_access_token(token)

    assert resolved_user_id == user_id


@pytest.mark.asyncio
async def test_invalid_access_token_raises_unauthorized() -> None:
    with pytest.raises(UnauthorizedError):
        await verify_access_token("this.is.not.a.valid.jwt")


@pytest.mark.asyncio
async def test_issue_token_pair_returns_both_tokens() -> None:
    user_id = str(uuid.uuid4())
    tokens = await issue_token_pair(user_id)

    assert "access_token" in tokens
    assert "refresh_token" in tokens
    assert tokens["token_type"] == "bearer"

    resolved_user_id = await verify_access_token(tokens["access_token"])
    assert resolved_user_id == user_id


@pytest.mark.asyncio
async def test_refresh_token_type_rejected_by_verify_access_token() -> None:
    """Refresh token'ni access token sifatida ishlatishga urinish rad etilishi kerak."""
    user_id = str(uuid.uuid4())
    tokens = await issue_token_pair(user_id)

    with pytest.raises(UnauthorizedError):
        await verify_access_token(tokens["refresh_token"])


@pytest.mark.asyncio
async def test_rotate_refresh_token_issues_new_working_pair() -> None:
    user_id = str(uuid.uuid4())
    original_tokens = await issue_token_pair(user_id)

    new_tokens = await rotate_refresh_token(original_tokens["refresh_token"])

    assert new_tokens["refresh_token"] != original_tokens["refresh_token"]
    resolved_user_id = await verify_access_token(new_tokens["access_token"])
    assert resolved_user_id == user_id


@pytest.mark.asyncio
async def test_rotated_refresh_token_cannot_be_reused() -> None:
    """Xavfsizlik uchun eng muhim test: bir marta ishlatilgan refresh token
    qayta ishlatilishga urinilsa, rad etilishi SHART (token o'g'irlanishini aniqlash)."""
    user_id = str(uuid.uuid4())
    original_tokens = await issue_token_pair(user_id)

    await rotate_refresh_token(original_tokens["refresh_token"])

    with pytest.raises(UnauthorizedError):
        await rotate_refresh_token(original_tokens["refresh_token"])


@pytest.mark.asyncio
async def test_revoked_refresh_token_cannot_be_rotated() -> None:
    user_id = str(uuid.uuid4())
    tokens = await issue_token_pair(user_id)

    await revoke_refresh_token(tokens["refresh_token"])

    with pytest.raises(UnauthorizedError):
        await rotate_refresh_token(tokens["refresh_token"])


@pytest.mark.asyncio
async def test_revoke_nonexistent_token_does_not_raise() -> None:
    """Logout — token allaqachon yaroqsiz bo'lsa ham xato bermasligi kerak (idempotent)."""
    user_id = str(uuid.uuid4())
    tokens = await issue_token_pair(user_id)

    await revoke_refresh_token(tokens["refresh_token"])
    # Ikkinchi marta chaqirish xato bermasligi kerak.
    await revoke_refresh_token(tokens["refresh_token"])
