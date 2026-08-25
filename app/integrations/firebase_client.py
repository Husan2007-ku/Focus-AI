"""
Firebase Cloud Messaging (FCM) integratsiyasi — push xabarnomalar uchun.

Muhim: agar `FIREBASE_CREDENTIALS_PATH` topilmasa yoki noto'g'ri bo'lsa,
ilova ishga tushishda qulamaydi — faqat push funksiyasi ishlamay qoladi
va har bir chaqiruvda aniq xato qaytariladi. Bu dev muhitda (hali Firebase
sozlanmagan bo'lsa ham) qolgan barcha funksiyalar ishlashda davom etishi
uchun muhim.
"""

import firebase_admin
from firebase_admin import credentials, messaging

from app.core.config import settings
from app.core.exceptions import ExternalServiceError
from app.core.logging import get_logger

logger = get_logger(__name__)

_firebase_app: firebase_admin.App | None = None

try:
    _cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
    _firebase_app = firebase_admin.initialize_app(_cred)
    logger.info("firebase_initialized")
except Exception as exc:  # fayl topilmasa yoki noto'g'ri formatda bo'lsa
    logger.warning("firebase_init_failed", error=str(exc))
    _firebase_app = None


class FirebaseClient:
    def is_configured(self) -> bool:
        return _firebase_app is not None

    async def send_to_tokens(
        self, tokens: list[str], title: str, body: str, data: dict[str, str] | None = None
    ) -> list[str]:
        """
        Bir nechta qurilmaga push yuboradi.
        Qaytaradi: endi yaroqsiz (unregistered/invalid) bo'lgan token'lar ro'yxati —
        chaqiruvchi tomon ularni bazada `is_active=False` qilib belgilashi kerak.
        """
        if not self.is_configured():
            raise ExternalServiceError("Push xizmati sozlanmagan (Firebase credentials topilmadi).")

        if not tokens:
            return []

        message = messaging.MulticastMessage(
            notification=messaging.Notification(title=title, body=body),
            data=data or {},
            tokens=tokens,
        )

        try:
            response = messaging.send_each_for_multicast(message, app=_firebase_app)
        except Exception as exc:
            logger.error("fcm_send_failed", error=str(exc))
            raise ExternalServiceError("Push xabar yuborishda xatolik yuz berdi.") from exc

        invalid_tokens: list[str] = []
        for token, result in zip(tokens, response.responses, strict=True):
            if not result.success:
                error_code = getattr(result.exception, "code", None)
                if error_code in ("UNREGISTERED", "INVALID_ARGUMENT"):
                    invalid_tokens.append(token)
                logger.warning("fcm_token_failed", token=token[:20], error=str(result.exception))

        logger.info(
            "push_sent", success_count=response.success_count, failure_count=response.failure_count
        )
        return invalid_tokens


firebase_client = FirebaseClient()
