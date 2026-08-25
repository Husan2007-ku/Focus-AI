"""
Autentifikatsiya biznes logikasi: OTP orqali telefon tasdiqlash,
Google OAuth, va token boshqaruvi.
"""

import hashlib
import secrets

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ExternalServiceError, RateLimitError, UnauthorizedError
from app.core.logging import get_logger
from app.core.redis_client import redis_client
from app.core.security import issue_token_pair
from app.integrations.sms_client import sms_client
from app.models.user import AuthProvider, User

logger = get_logger(__name__)

OTP_TTL_SECONDS = 5 * 60  # 5 daqiqa
OTP_MAX_ATTEMPTS = 5
OTP_RESEND_COOLDOWN_SECONDS = 60  # bir xil raqamga qayta yuborishdan oldingi kutish vaqti


def _hash_otp(code: str) -> str:
    """OTP kodni Redis'da ochiq matnda emas, hash holida saqlaymiz."""
    return hashlib.sha256(code.encode()).hexdigest()


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── OTP oqimi ────────────────────────────────────────────
    async def request_otp(self, phone_number: str) -> None:
        cooldown_key = f"otp:cooldown:{phone_number}"
        if await redis_client.get(cooldown_key):
            raise RateLimitError(
                "Kod endigina yuborilgan. Iltimos, bir daqiqa kutib qayta urinib ko'ring."
            )

        code = f"{secrets.randbelow(1_000_000):06d}"
        code_key = f"otp:code:{phone_number}"
        attempts_key = f"otp:attempts:{phone_number}"

        await redis_client.setex(code_key, OTP_TTL_SECONDS, _hash_otp(code))
        await redis_client.delete(attempts_key)  # yangi kod — urinishlar hisoblagichi ham yangilanadi
        await redis_client.setex(cooldown_key, OTP_RESEND_COOLDOWN_SECONDS, "1")

        await sms_client.send_otp(phone_number, code)
        logger.info("otp_requested", phone=phone_number)

    async def verify_otp(self, phone_number: str, code: str) -> dict[str, str]:
        code_key = f"otp:code:{phone_number}"
        attempts_key = f"otp:attempts:{phone_number}"

        stored_hash = await redis_client.get(code_key)
        if stored_hash is None:
            raise UnauthorizedError("Kod muddati o'tgan yoki mavjud emas. Qaytadan so'rang.")

        attempts = int(await redis_client.get(attempts_key) or 0)
        if attempts >= OTP_MAX_ATTEMPTS:
            await redis_client.delete(code_key)
            raise RateLimitError("Urinishlar soni tugadi. Yangi kod so'rang.")

        if _hash_otp(code) != stored_hash:
            await redis_client.incr(attempts_key)
            await redis_client.expire(attempts_key, OTP_TTL_SECONDS)
            raise UnauthorizedError("Kod noto'g'ri.")

        # Kod to'g'ri — bir martalik ishlatilgani uchun darhol o'chiramiz.
        await redis_client.delete(code_key)
        await redis_client.delete(attempts_key)

        user = await self._get_or_create_user_by_phone(phone_number)
        return await issue_token_pair(str(user.id))

    async def _get_or_create_user_by_phone(self, phone_number: str) -> User:
        result = await self.db.execute(select(User).where(User.phone_number == phone_number))
        user = result.scalar_one_or_none()

        if user is None:
            user = User(phone_number=phone_number, primary_auth_provider=AuthProvider.PHONE)
            self.db.add(user)
            await self.db.commit()
            await self.db.refresh(user)
            logger.info("new_user_created", auth_provider="phone", user_id=str(user.id))

        return user

    # ── Google OAuth oqimi ───────────────────────────────────
    async def google_login(self, google_id_token_str: str) -> dict[str, str]:
        try:
            idinfo = google_id_token.verify_oauth2_token(
                google_id_token_str, google_requests.Request()
            )
        except ValueError as exc:
            logger.warning("google_token_invalid", error=str(exc))
            raise UnauthorizedError("Google token yaroqsiz.") from exc
        except Exception as exc:  # tarmoq/Google xizmati xatosi
            logger.error("google_verification_failed", error=str(exc))
            raise ExternalServiceError("Google bilan bog'lanib bo'lmadi.") from exc

        google_user_id = idinfo["sub"]
        email = idinfo.get("email")
        full_name = idinfo.get("name")
        avatar_url = idinfo.get("picture")

        user = await self._get_or_create_user_by_google(
            google_user_id, email, full_name, avatar_url
        )
        return await issue_token_pair(str(user.id))

    async def _get_or_create_user_by_google(
        self, google_id: str, email: str | None, full_name: str | None, avatar_url: str | None
    ) -> User:
        result = await self.db.execute(select(User).where(User.google_id == google_id))
        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                google_id=google_id,
                email=email,
                full_name=full_name,
                avatar_url=avatar_url,
                primary_auth_provider=AuthProvider.GOOGLE,
            )
            self.db.add(user)
            await self.db.commit()
            await self.db.refresh(user)
            logger.info("new_user_created", auth_provider="google", user_id=str(user.id))

        return user
