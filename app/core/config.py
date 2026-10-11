"""
Ilova sozlamalari.

Barcha muhit o'zgaruvchilari (.env) shu yerda markazlashgan holda o'qiladi
va validatsiya qilinadi. Boshqa hech bir modulda to'g'ridan-to'g'ri
`os.environ` ishlatilmaydi — faqat shu `settings` obyekti orqali.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── Ilova ──────────────────────────────────────────────
    APP_NAME: str = "FocusAI"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str

    # ── Ma'lumotlar bazasi ─────────────────────────────────
    DATABASE_URL: str
    DATABASE_ECHO: bool = False

    # ── Redis / Celery ─────────────────────────────────────
    REDIS_URL: str
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str

    # ── JWT ────────────────────────────────────────────────
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # ── AI (Claude) ────────────────────────────────────────
    ANTHROPIC_API_KEY: str
    AI_MODEL: str = "claude-sonnet-4-6"
    AI_DAILY_REQUEST_LIMIT_FREE: int = 3
    AI_DAILY_REQUEST_LIMIT_PREMIUM: int = 100

    # ── To'lov tizimlari ───────────────────────────────────
    PAYME_MERCHANT_ID: str = ""
    PAYME_SECRET_KEY: str = ""
    CLICK_MERCHANT_ID: str = ""
    CLICK_SERVICE_ID: str = ""
    CLICK_SECRET_KEY: str = ""

    # ── Firebase ───────────────────────────────────────────
    FIREBASE_CREDENTIALS_PATH: str = "./secrets/firebase-service-account.json"

    # ── SMS OTP ────────────────────────────────────────────
    SMS_PROVIDER_API_KEY: str = ""
    SMS_PROVIDER_BASE_URL: str = ""

    # ── Monitoring ─────────────────────────────────────────
    SENTRY_DSN: str = ""
    ADMIN_API_KEY: str = ""  # bo'sh bo'lsa — /api/v1/admin/* butunlay yopiq

    # ── CORS ───────────────────────────────────────────────
    CORS_ORIGINS: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"


@lru_cache
def get_settings() -> Settings:
    """
    Settings obyektini keshlab qaytaradi — har chaqiruvda .env
    qayta o'qilmaydi, dastur ishga tushganda bir marta yuklanadi.
    """
    return Settings()


settings = get_settings()
