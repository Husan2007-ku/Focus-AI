"""
Celery ilovasi — fon vazifalari (background tasks) uchun markaziy konfiguratsiya.

Ishlatilish maqsadlari:
- Kunlik streak reset, eslatmalar (daily_tasks)
- Moliyaviy maqsadlar muddatini tekshirish (finance_tasks)
- Haftalik AI xulosalarini generatsiya qilish (ai_tasks)
"""

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "focusai",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.finance_tasks",
        "app.tasks.daily_tasks",
        "app.tasks.ai_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Tashkent",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 daqiqa — osilib qolgan vazifalarni to'xtatish uchun
    result_expires=3600,
)

# Rejalashtirilgan (cron) vazifalar.
celery_app.conf.beat_schedule = {
    "resolve-expired-commitments-hourly": {
        "task": "app.tasks.finance_tasks.resolve_expired_commitments",
        "schedule": crontab(minute=0),  # har soat boshida
    },
    "reset-stale-streaks-daily": {
        "task": "app.tasks.daily_tasks.reset_stale_streaks",
        "schedule": crontab(hour=0, minute=5),  # har kuni ertalab 00:05 (Toshkent)
    },
    "send-daily-reminders": {
        "task": "app.tasks.daily_tasks.send_daily_reminders",
        "schedule": crontab(hour=20, minute=0),  # har kuni kechqurun 20:00 (Toshkent)
    },
    "generate-weekly-ai-summaries": {
        "task": "app.tasks.ai_tasks.generate_weekly_ai_summaries",
        "schedule": crontab(hour=20, minute=30, day_of_week=0),  # yakshanba 20:30 (Toshkent)
    },
}
