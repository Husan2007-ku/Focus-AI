"""
Daily Routine biznes logikasi.
"""

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.integrations.claude_client import claude_client
from app.models.routine import DailyRoutine, RoutineStatus
from app.models.user import User
from app.schemas.routine import EveningReportSchema, MorningPlanSchema
from app.services.gamification_service import GamificationService
from app.utils.timezone import get_tashkent_today

logger = get_logger(__name__)


class RoutineService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def submit_morning_plan(self, user: User, data: MorningPlanSchema) -> DailyRoutine:
        today = get_tashkent_today()
        routine = await self._get_or_create(user.id, today)

        routine.morning_plan = data.morning_plan
        routine.planned_focus_minutes = data.planned_focus_minutes
        await self.db.commit()
        await self.db.refresh(routine)

        logger.info("morning_plan_submitted", user_id=str(user.id), date=str(today))
        return routine

    async def submit_evening_report(self, user: User, data: EveningReportSchema) -> DailyRoutine:
        today = get_tashkent_today()
        routine = await self._get_by_date(user.id, today)

        if routine is None or routine.morning_plan is None:
            raise ConflictError(
                "Kechqurungi hisobot uchun avval shu kunlik ertalabki reja kiritilgan bo'lishi kerak."
            )

        routine.evening_report = data.evening_report
        routine.self_rating = data.self_rating
        routine.status = RoutineStatus.REPORTED

        routine.ai_feedback = await self._generate_ai_feedback(routine)

        await self.db.commit()
        await self.db.refresh(routine)

        gamification = GamificationService(self.db)
        await gamification.register_routine_completed(user.id, routine.id)

        logger.info("evening_report_submitted", user_id=str(user.id), date=str(today))
        return routine

    async def get_today(self, user: User) -> DailyRoutine | None:
        return await self._get_by_date(user.id, get_tashkent_today())

    async def get_history(
        self, user: User, limit: int = 30, offset: int = 0
    ) -> list[DailyRoutine]:
        result = await self.db.execute(
            select(DailyRoutine)
            .where(DailyRoutine.user_id == user.id)
            .order_by(DailyRoutine.routine_date.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    # ── Ichki yordamchi metodlar ─────────────────────────────
    async def _generate_ai_feedback(self, routine: DailyRoutine) -> str:
        prompt = (
            f"Foydalanuvchining bugungi ertalabki rejasi: \"{routine.morning_plan}\".\n"
            f"Rejalashtirilgan fokus vaqti: {routine.planned_focus_minutes or 'ko\u2019rsatilmagan'} daqiqa.\n"
            f"Kechqurungi hisoboti: \"{routine.evening_report}\".\n"
            f"O'z-o'ziga bahosi (1-5): {routine.self_rating}.\n\n"
            "Shu ma'lumotlar asosida foydalanuvchiga 2-3 gapdan iborat, "
            "qo'llab-quvvatlovchi va ertaga uchun bitta aniq amaliy maslahat "
            "beruvchi qisqa fikr yoz."
        )
        return await claude_client.send_message([{"role": "user", "content": prompt}])

    async def _get_by_date(self, user_id: uuid.UUID, routine_date: date) -> DailyRoutine | None:
        result = await self.db.execute(
            select(DailyRoutine).where(
                DailyRoutine.user_id == user_id, DailyRoutine.routine_date == routine_date
            )
        )
        return result.scalar_one_or_none()

    async def _get_or_create(self, user_id: uuid.UUID, routine_date: date) -> DailyRoutine:
        routine = await self._get_by_date(user_id, routine_date)
        if routine is not None:
            return routine

        routine = DailyRoutine(user_id=user_id, routine_date=routine_date)
        self.db.add(routine)
        await self.db.commit()
        await self.db.refresh(routine)
        return routine
