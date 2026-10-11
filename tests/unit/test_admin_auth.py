"""
`verify_admin_key` uchun testlar — /api/v1/admin/* endpoint'larini himoya
qiluvchi header-asosli tekshiruv to'g'ri ishlashini tasdiqlaydi.

Xavfsizlik uchun eng muhim holat: `ADMIN_API_KEY` sozlanmagan (bo'sh) bo'lsa,
endpoint hech qanday kalit bilan ham ochilmasligi kerak — "sozlanmagan bo'lsa
ochiq" degan xavfli standart bo'lmasligi kerak.
"""

import pytest

from app.api.deps import verify_admin_key
from app.core.config import settings
from app.core.exceptions import UnauthorizedError


@pytest.mark.asyncio
async def test_missing_header_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ADMIN_API_KEY", "correct-key")

    with pytest.raises(UnauthorizedError):
        await verify_admin_key(None)


@pytest.mark.asyncio
async def test_wrong_key_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ADMIN_API_KEY", "correct-key")

    with pytest.raises(UnauthorizedError):
        await verify_admin_key("wrong-key")


@pytest.mark.asyncio
async def test_correct_key_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ADMIN_API_KEY", "correct-key")

    await verify_admin_key("correct-key")  # xato chiqmasligi kerak


@pytest.mark.asyncio
async def test_unconfigured_admin_key_rejects_even_with_a_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`ADMIN_API_KEY` bo'sh (sozlanmagan) bo'lsa — hech qanday header qiymati
    bilan ham kirish berilmasligi kerak."""
    monkeypatch.setattr(settings, "ADMIN_API_KEY", "")

    with pytest.raises(UnauthorizedError):
        await verify_admin_key("anything")
