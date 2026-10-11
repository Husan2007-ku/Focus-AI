"""
Daily Routine biznes logikasi.

DB bilan ishlash `RoutineRepository`ga o'tkazilgan (TZ v2.0, 3-band).
"""

import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.core.logging import get_logger
from app.integrations.claude_client import claude_client
from app.models.routine import DailyRoutine, RoutineStatus
from app.models.user import User
from app.repositories.routine_repository import RoutineRepository
from app.schemas.routine import EveningReportSchema, MorningPlanSchema
from app.services.gamification_service import GamificationService
from app.utils.timezone import get_tashkent_today

logger = get_logger(__name__)


class RoutineService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = RoutineRepository(db)

    async def submit_morning_plan(self, user: User, data: MorningPlanSchema) -> DailyRoutine:
        today = get_tashkent_today()
        routine = await self._get_or_create(user.id, today)

        routine.morning_plan = data.morning_plan
        routine.planned_focus_minutes = data.planned_focus_minutes
        routine = await self.repo.save(routine)

        logger.info("morning_plan_submitted", user_id=str(user.id), date=str(today))
        return routine

    async def submit_evening_report(self, user: User, data: EveningReportSchema) -> DailyRoutine:
        today = get_tashkent_today()
        routine = await self.repo.get_by_date(user.id, today)

        if routine is None or routine.morning_plan is None:
            raise ConflictError(
                "Kechqurungi hisobot uchun avval shu kunlik ertalabki reja "
                "kiritilgan bo'lishi kerak."
            )

        routine.evening_report = data.evening_report
        routine.self_rating = data.self_rating
        routine.status = RoutineStatus.REPORTED

        routine.ai_feedback = await self._generate_ai_feedback(routine)

        routine = await self.repo.save(routine)

        gamification = GamificationService(self.db)
        await gamification.register_routine_completed(user.id, routine.id)

        logger.info("evening_report_submitted", user_id=str(user.id), date=str(today))
        return routine

    async def get_today(self, user: User) -> DailyRoutine | None:
        return await self.repo.get_by_date(user.id, get_tashkent_today())

    async def get_history(self, user: User, limit: int = 30, offset: int = 0) -> list[DailyRoutine]:
        return await self.repo.list_for_user(user.id, limit, offset)

    # ── Ichki yordamchi metodlar ─────────────────────────────
    async def _generate_ai_feedback(self, routine: DailyRoutine) -> str:
        prompt = (
            f'Foydalanuvchining bugungi ertalabki rejasi: "{routine.morning_plan}".\n'
            f"Rejalashtirilgan fokus vaqti: "
            f"{routine.planned_focus_minutes or 'ko’rsatilmagan'} daqiqa.\n"
            f'Kechqurungi hisoboti: "{routine.evening_report}".\n'
            f"O'z-o'ziga bahosi (1-5): {routine.self_rating}.\n\n"
            "Shu ma'lumotlar asosida foydalanuvchiga 2-3 gapdan iborat, "
            "qo'llab-quvvatlovchi va ertaga uchun bitta aniq amaliy maslahat "
            "beruvchi qisqa fikr yoz."
        )
        return await claude_client.send_message([{"role": "user", "content": prompt}])

    async def _get_or_create(self, user_id: uuid.UUID, routine_date: date) -> DailyRoutine:
        routine = await self.repo.get_by_date(user_id, routine_date)
        if routine is not None:
            return routine

        routine = DailyRoutine(user_id=user_id, routine_date=routine_date)
        return await self.repo.add(routine)
