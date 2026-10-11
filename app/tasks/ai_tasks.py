"""
Haftalik AI xulosa generatsiyasi — har bir faol foydalanuvchi uchun
`StatsService.get_weekly_ai_summary()` orqali hisoblanadi va push xabar
sifatida yuboriladi (foydalanuvchi ilovani ochmasdan ham haftalik
xulosasini oladi).

Celery Beat orqali haftada bir marta (yakshanba kechqurun, Toshkent vaqti
bo'yicha) ishga tushiriladi — qarang `app/tasks/celery_app.py`.
"""

import asyncio

from app.core.database import AsyncSessionLocal
from app.core.exceptions import ExternalServiceError
from app.core.logging import get_logger
from app.repositories.user_repository import UserRepository
from app.services.notification_service import NotificationService
from app.services.stats_service import StatsService
from app.tasks.celery_app import celery_app

logger = get_logger(__name__)

WEEKLY_SUMMARY_PUSH_TITLE = "Haftalik xulosangiz tayyor"


async def _generate_and_send_weekly_summaries_async() -> int:
    async with AsyncSessionLocal() as db:
        user_ids = await UserRepository(db).list_active_ids()

        sent = 0
        for user_id in user_ids:
            # Har bir foydalanuvchi mustaqil qayta ishlanadi — bittasida AI
            # yoki push xatosi qolganlarga to'sqinlik qilmasligi kerak.
            try:
                user = await UserRepository(db).get_by_id(user_id)
                if user is None:
                    continue

                stats_service = StatsService(db)
                weekly_summary = await stats_service.get_weekly_ai_summary(user)

                notifications = NotificationService(db)
                await notifications.send_to_user(
                    user_id, WEEKLY_SUMMARY_PUSH_TITLE, weekly_summary["summary"]
                )
                sent += 1
            except ExternalServiceError as exc:
                logger.warning(
                    "weekly_ai_summary_task_failed", user_id=str(user_id), error=str(exc)
                )

        return sent


@celery_app.task(name="app.tasks.ai_tasks.generate_weekly_ai_summaries")
def generate_weekly_ai_summaries() -> int:
    count = asyncio.run(_generate_and_send_weekly_summaries_async())
    logger.info("weekly_ai_summaries_generated", count=count)
    return count
