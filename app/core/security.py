"""
JWT token yaratish va tekshirish.

Xavfsizlik dizayni:
- Access token — stateless, qisqa muddatli (30 daqiqa), server tomonida
  saqlanmaydi.
- Refresh token — har birining `jti` (unique ID) qiymati Redis'da saqlanadi.
  Bu ikkita narsani ta'minlaydi:
    1. Logout qilinganda refresh token'ni darhol bekor qilish mumkin
       (stateless JWT'da bu imkonsiz bo'lardi).
    2. Har safar yangilanganda eski refresh token o'chiriladi (rotatsiya) —
       o'g'irlangan tokendan foydalanishga urinish aniqlanadi.
"""

import uuid
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from jose import JWTError, jwt

from app.core.config import settings
from app.core.exceptions import UnauthorizedError
from app.core.logging import get_logger
from app.core.redis_client import redis_client

logger = get_logger(__name__)


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


def _create_token(subject: str, token_type: TokenType, expires_delta: timedelta) -> tuple[str, str]:
    now = datetime.now(UTC)
    jti = str(uuid.uuid4())
    payload = {
        "sub": subject,
        "type": token_type.value,
        "jti": jti,
        "iat": now,
        "exp": now + expires_delta,
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, jti


async def create_access_token(user_id: str) -> str:
    token, _ = _create_token(
        user_id, TokenType.ACCESS, timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return token


async def create_refresh_token(user_id: str) -> str:
    expires_delta = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    token, jti = _create_token(user_id, TokenType.REFRESH, expires_delta)

    # jti'ni Redis'da saqlaymiz — token amal qilish muddati bilan bir xil TTL bilan.
    await redis_client.set(
        f"refresh_token:{jti}",
        user_id,
        ex=int(expires_delta.total_seconds()),
    )
    return token


async def issue_token_pair(user_id: str) -> dict[str, str]:
    access_token = await create_access_token(user_id)
    refresh_token = await create_refresh_token(user_id)
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}


def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as exc:
        logger.warning("jwt_decode_failed", error=str(exc))
        raise UnauthorizedError("Token yaroqsiz yoki muddati o'tgan.") from exc


async def verify_access_token(token: str) -> str:
    """Access token'ni tekshiradi va foydalanuvchi ID'sini qaytaradi."""
    payload = _decode_token(token)
    if payload.get("type") != TokenType.ACCESS.value:
        raise UnauthorizedError("Noto'g'ri token turi.")
    return payload["sub"]


async def rotate_refresh_token(refresh_token: str) -> dict[str, str]:
    """
    Eski refresh token'ni bekor qilib, yangi access+refresh juftlikni qaytaradi.
    Agar refresh token Redis'da topilmasa (allaqachon ishlatilgan yoki
    logout qilingan) — xato qaytaradi.
    """
    payload = _decode_token(refresh_token)
    if payload.get("type") != TokenType.REFRESH.value:
        raise UnauthorizedError("Noto'g'ri token turi.")

    jti = payload["jti"]
    user_id = payload["sub"]

    stored_user_id = await redis_client.get(f"refresh_token:{jti}")
    if stored_user_id is None or stored_user_id != user_id:
        logger.warning("refresh_token_reuse_detected", user_id=user_id, jti=jti)
        raise UnauthorizedError("Refresh token bekor qilingan. Qaytadan tizimga kiring.")

    # Rotatsiya: eskisini o'chirib, yangisini beramiz.
    await redis_client.delete(f"refresh_token:{jti}")
    return await issue_token_pair(user_id)


async def revoke_refresh_token(refresh_token: str) -> None:
    """Logout — refresh token'ni Redis'dan o'chiradi."""
    try:
        payload = _decode_token(refresh_token)
        await redis_client.delete(f"refresh_token:{payload['jti']}")
    except UnauthorizedError:
        # Token allaqachon yaroqsiz bo'lsa ham, logout muvaffaqiyatli hisoblanadi.
        pass
