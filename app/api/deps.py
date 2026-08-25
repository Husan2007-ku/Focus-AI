"""
FastAPI dependency'lari — endpoint'lar orasida qayta ishlatiladigan
umumiy komponentlar (joriy foydalanuvchi, DB sessiyasi va h.k.).
"""

import uuid

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import UnauthorizedError
from app.core.security import verify_access_token
from app.models.user import User

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

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise UnauthorizedError("Foydalanuvchi topilmadi.")
    if not user.is_active:
        raise UnauthorizedError("Hisob faol emas.")

    return user
