"""
Gamification biznes logikasi: streak hisoblash, XP berish, badge aniqlash.

Bu servis boshqa servislar (FocusSessionService, RoutineService) tomonidan
"ichki API" sifatida chaqiriladi — o'zining alohida yozish endpoint'lari yo'q,
faqat o'qish (`/summary`) uchun ochiq.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import get_cached, invalidate_cached, set_cached
from app.core.logging import get_logger
from app.models.gamification import BadgeCode, UserBadge, UserStreak, XPReason, XPTransaction
from app.utils.timezone import get_tashkent_today

logger = get_logger(__name__)

CACHE_NAMESPACE = "gamification_summary"
CACHE_TTL_SECONDS = 60  # qisqa TTL — yangi XP/streak tez ko'rinishi kerak, lekin ortiqcha DB yukini kamaytiradi

XP_VALUES: dict[XPReason, int] = {
    XPReason.FOCUS_SESSION_COMPLETED: 10,
    XPReason.DAILY_ROUTINE_COMPLETED: 5,
    XPReason.STREAK_MILESTONE: 20,
    XPReason.BADGE_EARNED: 15,
}

STREAK_BADGE_THRESHOLDS: dict[int, BadgeCode] = {
    3: BadgeCode.STREAK_3,
    7: BadgeCode.STREAK_7,
    30: BadgeCode.STREAK_30,
}


class GamificationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def award_xp(
        self,
        user_id: uuid.UUID,
        reason: XPReason,
        reference_id: uuid.UUID | None = None,
    ) -> None:
        transaction = XPTransaction(
            user_id=user_id,
            amount=XP_VALUES[reason],
            reason=reason,
            reference_id=reference_id,
        )
        self.db.add(transaction)
        await self.db.commit()

    async def register_focus_session_completed(
        self, user_id: uuid.UUID, session_id: uuid.UUID
    ) -> None:
        """FocusSessionService.complete_session() muvaffaqiyatli tugagach chaqiriladi."""
        await self.award_xp(user_id, XPReason.FOCUS_SESSION_COMPLETED, session_id)
        await self._update_streak(user_id)

        streak = await self._get_or_create_streak(user_id)

        if streak.current_streak == 1:
            await self._award_badge_if_new(user_id, BadgeCode.FIRST_SESSION)

        milestone_badge = STREAK_BADGE_THRESHOLDS.get(streak.current_streak)
        if milestone_badge is not None:
            newly_awarded = await self._award_badge_if_new(user_id, milestone_badge)
            if newly_awarded:
                await self.award_xp(user_id, XPReason.STREAK_MILESTONE, streak.id)

        await invalidate_cached(CACHE_NAMESPACE, str(user_id))

    async def register_routine_completed(self, user_id: uuid.UUID, routine_id: uuid.UUID) -> None:
        """RoutineService.submit_evening_report() muvaffaqiyatli tugagach chaqiriladi."""
        await self.award_xp(user_id, XPReason.DAILY_ROUTINE_COMPLETED, routine_id)
        await invalidate_cached(CACHE_NAMESPACE, str(user_id))

    async def get_summary(self, user_id: uuid.UUID) -> dict:
        cached = await get_cached(CACHE_NAMESPACE, str(user_id))
        if cached is not None:
            return cached

        streak = await self._get_or_create_streak(user_id)

        total_xp_result = await self.db.execute(
            select(func.coalesce(func.sum(XPTransaction.amount), 0)).where(
                XPTransaction.user_id == user_id
            )
        )
        total_xp = total_xp_result.scalar_one()

        badges_result = await self.db.execute(
            select(UserBadge).where(UserBadge.user_id == user_id).order_by(UserBadge.earned_at)
        )
        badges = list(badges_result.scalars().all())

        summary = {
            "current_streak": streak.current_streak,
            "longest_streak": streak.longest_streak,
            "total_xp": total_xp,
            "badges": [{"badge_code": b.badge_code.value, "earned_at": b.earned_at} for b in badges],
        }

        await set_cached(CACHE_NAMESPACE, str(user_id), summary, CACHE_TTL_SECONDS)
        return summary

    # ── Ichki yordamchi metodlar ─────────────────────────────
    async def _get_or_create_streak(self, user_id: uuid.UUID) -> UserStreak:
        result = await self.db.execute(select(UserStreak).where(UserStreak.user_id == user_id))
        streak = result.scalar_one_or_none()

        if streak is None:
            streak = UserStreak(user_id=user_id)
            self.db.add(streak)
            await self.db.commit()
            await self.db.refresh(streak)

        return streak

    async def _update_streak(self, user_id: uuid.UUID) -> None:
        streak = await self._get_or_create_streak(user_id)
        today = get_tashkent_today()

        last_date = streak.last_active_date.date() if streak.last_active_date else None

        if last_date == today:
            # Bugun allaqachon hisobga olingan — ikkinchi seans streak'ni oshirmaydi.
            return
        elif last_date == today - timedelta(days=1):
            streak.current_streak += 1
        else:
            # Kun o'tkazib yuborilgan (yoki birinchi marta) — streak 1'dan boshlanadi.
            streak.current_streak = 1

        streak.longest_streak = max(streak.longest_streak, streak.current_streak)
        streak.last_active_date = datetime.now(timezone.utc)

        await self.db.commit()
        logger.info(
            "streak_updated", user_id=str(user_id), current_streak=streak.current_streak
        )

    async def _award_badge_if_new(self, user_id: uuid.UUID, badge_code: BadgeCode) -> bool:
        """Agar badge allaqachon berilgan bo'lsa, hech narsa qilmaydi. Yangi berilsa — True qaytaradi."""
        result = await self.db.execute(
            select(UserBadge).where(
                UserBadge.user_id == user_id, UserBadge.badge_code == badge_code
            )
        )
        if result.scalar_one_or_none() is not None:
            return False

        badge = UserBadge(user_id=user_id, badge_code=badge_code)
        self.db.add(badge)
        await self.db.commit()

        logger.info("badge_awarded", user_id=str(user_id), badge_code=badge_code.value)
        return True
