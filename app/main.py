"""
FocusAI backend — FastAPI entrypoint.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import sentry_sdk
from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestIDMiddleware
from app.core.rate_limit import limiter
from app.core.redis_client import redis_client

configure_logging()
logger = get_logger(__name__)

if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN, environment=settings.ENVIRONMENT, traces_sample_rate=0.2
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("app_starting", environment=settings.ENVIRONMENT)
    yield
    logger.info("app_stopping")


app = FastAPI(
    title=settings.APP_NAME,
    description="FocusAI — diqqatingizni qaytarib beruvchi AI yordamchi backend API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MUHIM: eng oxirida qo'shiladi -- Starlette middleware stackida oxirgi
# qo'shilgan eng tashqi qatlam bo'ladi, ya'ni request_id CORS'dan oldinroq
# (har bir so'rov, shu jumladan OPTIONS preflight uchun ham) o'rnatiladi.
app.add_middleware(RequestIDMiddleware)

register_exception_handlers(app)

# IP-darajasidagi rate-limit (slowapi) — qarang: app/core/rate_limit.py
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.get("/health", tags=["system"])
async def health_check(response: Response) -> dict[str, Any]:
    """
    Konteyner orkestratori (Docker/K8s) uchun TAYYORLIK (readiness) tekshiruvi.

    MUHIM: ilgari bu endpoint faqat statik {"status": "ok"} qaytargan --
    ya'ni FastAPI process tirik bo'lsa ham, DB yoki Redis bilan ulanish
    uzilgan bo'lsa ham, orkestrator buni "sog'lom" deb hisoblab, trafikni
    shu instansga yuborishda davom etardi (noto'g'ri pozitiv natija).
    Endi haqiqatan ham DB'ga (SELECT 1) va Redis'ga (PING) murojaat qilib
    tekshiramiz; ikkalasidan biri ishlamasa -- 503 qaytaramiz, shunda
    load balancer/Docker bu instansga so'rov yubormay turadi.
    """
    checks: dict[str, str] = {}

    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001 -- har qanday DB xatosi "down" hisoblanadi
        logger.error("health_check_database_failed", error=str(exc))
        checks["database"] = "down"

    try:
        await redis_client.ping()
        checks["redis"] = "ok"
    except Exception as exc:  # noqa: BLE001 -- har qanday Redis xatosi "down" hisoblanadi
        logger.error("health_check_redis_failed", error=str(exc))
        checks["redis"] = "down"

    is_healthy = all(value == "ok" for value in checks.values())
    response.status_code = status.HTTP_200_OK if is_healthy else status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ok" if is_healthy else "degraded",
        "service": settings.APP_NAME,
        "checks": checks,
    }


# API routerlar
from app.api.v1 import (  # noqa: E402
    admin,
    ai_agent,
    auth,
    finance,
    focus,
    gamification,
    notifications,
    organizations,
    payments,
    routine,
    stats,
    subscriptions,
    users,
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
app.include_router(focus.router, prefix="/api/v1/focus", tags=["focus"])
app.include_router(ai_agent.router, prefix="/api/v1/ai-agent", tags=["ai-agent"])
app.include_router(routine.router, prefix="/api/v1/routine", tags=["routine"])
app.include_router(gamification.router, prefix="/api/v1/gamification", tags=["gamification"])
app.include_router(stats.router, prefix="/api/v1/stats", tags=["stats"])
app.include_router(notifications.router, prefix="/api/v1/notifications", tags=["notifications"])
app.include_router(finance.router, prefix="/api/v1/finance", tags=["finance"])
app.include_router(payments.router, prefix="/api/v1/payments", tags=["payments"])
app.include_router(subscriptions.router, prefix="/api/v1/subscriptions", tags=["subscriptions"])
app.include_router(organizations.router, prefix="/api/v1/organizations", tags=["organizations"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])
