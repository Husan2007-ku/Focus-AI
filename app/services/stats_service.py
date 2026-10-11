"""
Shaxsiy statistika va haftalik AI xulosa biznes logikasi.

DB bilan ishlash `FocusSessionRepository` va `GamificationRepository`
(GamificationService orqali) ga o'tkazilgan (TZ v2.0, 3-band).
"""

from datetime import date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.integrations.claude_client import claude_client
from app.models.user import User
from app.repositories.focus_session_repository import FocusSessionRepository
from app.services.gamification_service import GamificationService
from app.utils.timezone import get_tashkent_day_start_utc, get_tashkent_today

logger = get_logger(__name__)

WEEKLY_WINDOW_DAYS = 7


class StatsService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = FocusSessionRepository(db)
        self.gamification = GamificationService(db)

    async def get_summary(self, user: User) -> dict:
        total_sessions, total_minutes = await self.repo.get_completed_stats(user.id)
        weekly_sessions, weekly_minutes = await self.repo.get_completed_stats(
            user.id, since=_week_start_utc()
        )
        gamification_summary = await self.gamification.get_summary(user.id)

        return {
            "total_completed_sessions": total_sessions,
            "total_focus_minutes": total_minutes,
            "weekly_completed_sessions": weekly_sessions,
            "weekly_focus_minutes": weekly_minutes,
            "current_streak": gamification_summary["current_streak"],
            "longest_streak": gamification_summary["longest_streak"],
            "total_xp": gamification_summary["total_xp"],
        }

    async def get_weekly_ai_summary(self, user: User) -> dict:
        week_start_date, week_end_date = _week_bounds()
        weekly_sessions, weekly_minutes = await self.repo.get_completed_stats(
            user.id, since=get_tashkent_day_start_utc(week_start_date)
        )

        summary_text = await self._generate_ai_summary(user, weekly_sessions, weekly_minutes)

        logger.info("weekly_ai_summary_generated", user_id=str(user.id))
        return {
            "week_start": week_start_date,
            "week_end": week_end_date,
            "weekly_completed_sessions": weekly_sessions,
            "weekly_focus_minutes": weekly_minutes,
            "summary": summary_text,
        }

    # ── Ichki yordamchi metodlar ─────────────────────────────
    async def _generate_ai_summary(
        self, user: User, weekly_sessions: int, weekly_minutes: int
    ) -> str:
        prompt = (
            f"Foydalanuvchi shu hafta {weekly_sessions} ta fokus seansini tugatdi, "
            f"jami {weekly_minutes} daqiqa diqqatini jamlagan holda ishladi.\n\n"
            "Shu ma'lumot asosida foydalanuvchiga 2-3 gapdan iborat, qo'llab-quvvatlovchi "
            "haftalik xulosa yoz va keyingi hafta uchun bitta aniq amaliy maslahat ber."
        )
        return await claude_client.send_message([{"role": "user", "content": prompt}])


def _week_bounds() -> tuple[date, date]:
    """(hafta boshlanishi — dushanba, hafta tugashi — yakshanba), Toshkent
    taqvimi bo'yicha."""
    today = get_tashkent_today()
    week_start_date = today - timedelta(days=today.weekday())
    week_end_date = week_start_date + timedelta(days=WEEKLY_WINDOW_DAYS - 1)
    return week_start_date, week_end_date


def _week_start_utc() -> datetime:
    """Joriy haftaning boshlanishi (dushanba, 00:00, Toshkent vaqti bo'yicha),
    UTC-aware `datetime` sifatida — DB solishtiruvlari uchun."""
    week_start_date, _ = _week_bounds()
    return get_tashkent_day_start_utc(week_start_date)
