"""
FastAPI dependency'lari — endpoint'lar orasida qayta ishlatiladigan
umumiy komponentlar (joriy foydalanuvchi, DB sessiyasi va h.k.).
"""

import secrets
import uuid

from fastapi import Depends, Header
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import UnauthorizedError
from app.core.security import verify_access_token
from app.models.user import User
from app.repositories.user_repository import UserRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/otp/verify", auto_error=False)


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if token is None:
        raise UnauthorizedError("Autentifikatsiya talab qilinadi.")

    user_id_str = await verify_access_token(token)

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError as exc:
        raise UnauthorizedError("Token yaroqsiz.") from exc

    user = await UserRepository(db).get_by_id(user_id)

    if user is None:
        raise UnauthorizedError("Foydalanuvchi topilmadi.")
    if not user.is_active:
        raise UnauthorizedError("Hisob faol emas.")

    return user


async def verify_admin_key(x_admin_key: str | None = Header(default=None)) -> None:
    """`/api/v1/admin/*` — oddiy foydalanuvchi tokeni bilan emas, alohida
    `X-Admin-Key` header orqali himoyalangan (bu ichki monitoring, mobil
    ilova foydalanuvchilariga umuman ko'rinmaydi).

    `ADMIN_API_KEY` sozlanmagan bo'lsa (bo'sh satr) — xavfsizlik uchun
    endpoint har doim yopiq deb hisoblanadi, hech qanday kalit bilan ham
    ochilmaydi."""
    if not settings.ADMIN_API_KEY or x_admin_key is None:
        raise UnauthorizedError("Admin kaliti talab qilinadi.")
    if not secrets.compare_digest(x_admin_key, settings.ADMIN_API_KEY):
        raise UnauthorizedError("Admin kaliti noto'g'ri.")
