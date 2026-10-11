"""
Focus Session biznes logikasi.

Asosiy qoida: bir vaqtning o'zida foydalanuvchida faqat BITTA faol
(ACTIVE) seans bo'lishi mumkin — bu ma'lumotlar bazasi darajasida emas,
service qatlamida tekshiriladi (chunki shartli tekshiruv, oddiy unique
constraint bilan ifodalab bo'lmaydi).

DB bilan ishlash `FocusSessionRepository`ga o'tkazilgan (TZ v2.0, 3-band).
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.models.focus_session import FocusSession, FocusSessionStatus
from app.models.user import User
from app.repositories.focus_session_repository import FocusSessionRepository
from app.schemas.focus import FocusSessionStartSchema
from app.services.gamification_service import GamificationService

logger = get_logger(__name__)


class FocusSessionService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = FocusSessionRepository(db)

    async def start_session(self, user: User, data: FocusSessionStartSchema) -> FocusSession:
        existing_active = await self.repo.get_active_for_user(user.id)
        if existing_active is not None:
            raise ConflictError("Sizda allaqachon faol fokus seansi bor. Avval uni yakunlang.")

        session = FocusSession(
            user_id=user.id,
            planned_duration_minutes=data.planned_duration_minutes,
            blocked_apps=data.blocked_apps,
            status=FocusSessionStatus.ACTIVE,
        )
        session = await self.repo.add(session)

        logger.info(
            "focus_session_started",
            user_id=str(user.id),
            session_id=str(session.id),
            planned_minutes=data.planned_duration_minutes,
        )
        return session

    async def complete_session(self, user: User, session_id: uuid.UUID) -> FocusSession:
        session = await self._get_owned_session(
            user.id, session_id, expected_status=FocusSessionStatus.ACTIVE
        )
        session.status = FocusSessionStatus.COMPLETED
        self._finalize(session)

        await self.repo.commit()
        await self.repo.refresh(session)

        gamification = GamificationService(self.db)
        await gamification.register_focus_session_completed(user.id, session.id)

        logger.info(
            "focus_session_completed",
            user_id=str(user.id),
            session_id=str(session.id),
            actual_minutes=session.actual_duration_minutes,
        )
        return session

    async def cancel_session(self, user: User, session_id: uuid.UUID) -> FocusSession:
        session = await self._get_owned_session(
            user.id, session_id, expected_status=FocusSessionStatus.ACTIVE
        )
        session.status = FocusSessionStatus.CANCELLED
        self._finalize(session)

        await self.repo.commit()
        await self.repo.refresh(session)

        logger.info("focus_session_cancelled", user_id=str(user.id), session_id=str(session.id))
        return session

    async def fail_session(self, user: User, session_id: uuid.UUID) -> FocusSession:
        """
        Mobil ilova bloklangan ilovaga kirishga urinishni aniqlaganda chaqiriladi —
        seans "buzilgan" deb belgilanadi (masalan, moliyaviy jarima uchun asos).
        """
        session = await self._get_owned_session(
            user.id, session_id, expected_status=FocusSessionStatus.ACTIVE
        )
        session.status = FocusSessionStatus.FAILED
        self._finalize(session)

        await self.repo.commit()
        await self.repo.refresh(session)

        logger.warning("focus_session_failed", user_id=str(user.id), session_id=str(session.id))
        return session

    async def get_active_session(self, user: User) -> FocusSession | None:
        return await self.repo.get_active_for_user(user.id)

    async def get_history(
        self, user: User, limit: int = 20, offset: int = 0
    ) -> tuple[list[FocusSession], int]:
        return await self.repo.list_for_user(user.id, limit, offset)

    # ── Ichki yordamchi metodlar ─────────────────────────────
    def _finalize(self, session: FocusSession) -> None:
        now = datetime.now(UTC)
        session.ended_at = now
        elapsed_seconds = (now - session.started_at).total_seconds()
        session.actual_duration_minutes = max(0, int(elapsed_seconds // 60))

    async def _get_owned_session(
        self, user_id: uuid.UUID, session_id: uuid.UUID, expected_status: FocusSessionStatus
    ) -> FocusSession:
        session = await self.repo.get_owned(user_id, session_id)

        if session is None:
            raise NotFoundError("Fokus seansi topilmadi.")
        if session.status != expected_status:
            raise ConflictError(
                f"Bu amal faqat '{expected_status.value}' holatidagi seanslar uchun mumkin."
            )

        return session
