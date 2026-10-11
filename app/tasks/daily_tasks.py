"""
Kunlik fon vazifalari: streak reset va kunlik eslatma push xabari.

Celery Beat orqali har kuni bir marta (Toshkent vaqti bo'yicha ertalab
erta va kechqurun) ishga tushiriladi — qarang `app/tasks/celery_app.py`
dagi `beat_schedule`.
"""

import asyncio
from datetime import timedelta

from app.core.database import AsyncSessionLocal
from app.core.exceptions import ExternalServiceError
from app.core.logging import get_logger
from app.repositories.daily_tasks_repository import DailyTasksRepository
from app.services.notification_service import NotificationService
from app.tasks.celery_app import celery_app
from app.utils.timezone import get_tashkent_day_start_utc, get_tashkent_today

logger = get_logger(__name__)

REMINDER_TITLE = "FocusAI"
REMINDER_BODY = (
    "Bugun hali diqqatingizni jamlashga vaqt ajratmadingiz. "
    "15 daqiqalik qisqa fokus seansi bilan boshlab ko'ring!"
)


async def _reset_stale_streaks_async() -> int:
    async with AsyncSessionLocal() as db:
        repo = DailyTasksRepository(db)

        # Kecha faol bo'lmagan (bugungi kun hisobga olinmaydi — foydalanuvchi
        # hali bugun seans boshlashi mumkin) streak'lar — buzilgan deb hisoblanadi.
        yesterday = get_tashkent_today() - timedelta(days=1)
        cutoff = get_tashkent_day_start_utc(yesterday)

        stale_streaks = await repo.list_stale_streaks(cutoff)
        await repo.reset_streaks(stale_streaks)
        return len(stale_streaks)


@celery_app.task(name="app.tasks.daily_tasks.reset_stale_streaks")
def reset_stale_streaks() -> int:
    count = asyncio.run(_reset_stale_streaks_async())
    logger.info("stale_streaks_reset", count=count)
    return count


async def _send_daily_reminders_async() -> int:
    async with AsyncSessionLocal() as db:
        repo = DailyTasksRepository(db)
        notifications = NotificationService(db)

        today_start = get_tashkent_day_start_utc()
        user_ids = await repo.list_active_user_ids_without_completed_session_since(today_start)

        sent = 0
        for user_id in user_ids:
            try:
                await notifications.send_to_user(user_id, REMINDER_TITLE, REMINDER_BODY)
                sent += 1
            except ExternalServiceError as exc:
                # Bir foydalanuvchida push xatosi (masalan Firebase sozlanmagan)
                # qolganlarga yuborishni to'xtatmasligi kerak.
                logger.warning("daily_reminder_failed", user_id=str(user_id), error=str(exc))

        return sent


@celery_app.task(name="app.tasks.daily_tasks.send_daily_reminders")
def send_daily_reminders() -> int:
    count = asyncio.run(_send_daily_reminders_async())
    logger.info("daily_reminders_sent", count=count)
    return count
