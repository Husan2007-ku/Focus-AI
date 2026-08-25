"""
Eskiz.uz SMS integratsiyasi — O'zbekistonda eng ko'p ishlatiladigan SMS
shlyuzlaridan biri, OTP kodlarni yuborish uchun.

Eskiz autentifikatsiyasi: /api/auth/login orqali bearer token olinadi,
token ~30 kun amal qiladi va Redis'da keshlanadi (har so'rovda qayta
login qilinmasligi uchun).
"""

import httpx

from app.core.config import settings
from app.core.exceptions import ExternalServiceError
from app.core.logging import get_logger
from app.core.redis_client import redis_client

logger = get_logger(__name__)

ESKIZ_TOKEN_CACHE_KEY = "eskiz:auth_token"
ESKIZ_TOKEN_TTL_SECONDS = 25 * 24 * 60 * 60  # ~25 kun (30 kunlik amal qilish muddatidan ehtiyotkorona kam)


class EskizSMSClient:
    def __init__(self) -> None:
        self.base_url = settings.SMS_PROVIDER_BASE_URL.rstrip("/")
        self.email = settings.SMS_PROVIDER_API_KEY  # Eskiz'da bu "email" maydoni sifatida ishlatiladi
        self._http = httpx.AsyncClient(timeout=10.0)

    async def _get_token(self) -> str:
        cached = await redis_client.get(ESKIZ_TOKEN_CACHE_KEY)
        if cached:
            return cached

        try:
            response = await self._http.post(
                f"{self.base_url}/auth/login",
                data={"email": self.email, "password": settings.SMS_PROVIDER_API_KEY},
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("eskiz_auth_failed", error=str(exc))
            raise ExternalServiceError("SMS xizmatiga ulanib bo'lmadi.") from exc

        token = response.json()["data"]["token"]
        await redis_client.setex(ESKIZ_TOKEN_CACHE_KEY, ESKIZ_TOKEN_TTL_SECONDS, token)
        return token

    async def send_otp(self, phone_number: str, code: str) -> None:
        """
        `phone_number` +998 bilan boshlanadi; Eskiz API '+' belgisisiz kutadi.
        """
        token = await self._get_token()
        clean_phone = phone_number.lstrip("+")
        message = f"FocusAI tasdiqlash kodi: {code}. Kodni hech kimga bermang."

        try:
            response = await self._http.post(
                f"{self.base_url}/message/sms/send",
                headers={"Authorization": f"Bearer {token}"},
                data={
                    "mobile_phone": clean_phone,
                    "message": message,
                    "from": "4546",  # Eskiz standart sender ID
                },
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("eskiz_send_failed", phone=clean_phone, error=str(exc))
            raise ExternalServiceError("SMS yuborib bo'lmadi. Birozdan so'ng qayta urinib ko'ring.") from exc

        logger.info("otp_sms_sent", phone=clean_phone)


sms_client = EskizSMSClient()
