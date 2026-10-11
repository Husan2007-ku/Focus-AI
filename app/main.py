"""
FocusAI backend — FastAPI entrypoint.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger

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

register_exception_handlers(app)


@app.get("/health", tags=["system"])
async def health_check() -> dict[str, str]:
    """Konteyner orkestratori (Docker/K8s) uchun sog'lomlik tekshiruvi."""
    return {"status": "ok", "service": settings.APP_NAME}


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
