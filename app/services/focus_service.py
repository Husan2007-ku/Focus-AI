"""
Focus Session biznes logikasi.

Asosiy qoida: bir vaqtning o'zida foydalanuvchida faqat BITTA faol
(ACTIVE) seans bo'lishi mumkin — bu ma'lumotlar bazasi darajasida emas,
service qatlamida tekshiriladi (chunki shartli tekshiruv, oddiy unique
constraint bilan ifodalab bo'lmaydi).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.models.focus_session import FocusSession, FocusSessionStatus
from app.models.user import User
from app.schemas.focus import FocusSessionStartSchema
from app.services.gamification_service import GamificationService

logger = get_logger(__name__)


class FocusSessionService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def start_session(self, user: User, data: FocusSessionStartSchema) -> FocusSession:
        existing_active = await self._get_active_session(user.id)
        if existing_active is not None:
            raise ConflictError(
                "Sizda allaqachon faol fokus seansi bor. Avval uni yakunlang."
            )

        session = FocusSession(
            user_id=user.id,
            planned_duration_minutes=data.planned_duration_minutes,
            blocked_apps=data.blocked_apps,
            status=FocusSessionStatus.ACTIVE,
        )
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)

        logger.info(
            "focus_session_started",
            user_id=str(user.id),
            session_id=str(session.id),
            planned_minutes=data.planned_duration_minutes,
        )
        return session

    async def complete_session(self, user: User, session_id: uuid.UUID) -> FocusSession:
        session = await self._get_owned_session(user.id, session_id, expected_status=FocusSessionStatus.ACTIVE)
        session.status = FocusSessionStatus.COMPLETED
        self._finalize(session)

        await self.db.commit()
        await self.db.refresh(session)

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
        session = await self._get_owned_session(user.id, session_id, expected_status=FocusSessionStatus.ACTIVE)
        session.status = FocusSessionStatus.CANCELLED
        self._finalize(session)

        await self.db.commit()
        await self.db.refresh(session)

        logger.info("focus_session_cancelled", user_id=str(user.id), session_id=str(session.id))
        return session

    async def fail_session(self, user: User, session_id: uuid.UUID) -> FocusSession:
        """
        Mobil ilova bloklangan ilovaga kirishga urinishni aniqlaganda chaqiriladi —
        seans "buzilgan" deb belgilanadi (masalan, moliyaviy jarima uchun asos).
        """
        session = await self._get_owned_session(user.id, session_id, expected_status=FocusSessionStatus.ACTIVE)
        session.status = FocusSessionStatus.FAILED
        self._finalize(session)

        await self.db.commit()
        await self.db.refresh(session)

        logger.warning("focus_session_failed", user_id=str(user.id), session_id=str(session.id))
        return session

    async def get_active_session(self, user: User) -> FocusSession | None:
        return await self._get_active_session(user.id)

    async def get_history(
        self, user: User, limit: int = 20, offset: int = 0
    ) -> tuple[list[FocusSession], int]:
        result = await self.db.execute(
            select(FocusSession)
            .where(FocusSession.user_id == user.id)
            .order_by(FocusSession.started_at.desc())
            .limit(limit)
            .offset(offset)
        )
        items = list(result.scalars().all())

        count_result = await self.db.execute(
            select(FocusSession).where(FocusSession.user_id == user.id)
        )
        total = len(count_result.scalars().all())

        return items, total

    # ── Ichki yordamchi metodlar ─────────────────────────────
    def _finalize(self, session: FocusSession) -> None:
        now = datetime.now(timezone.utc)
        session.ended_at = now
        elapsed_seconds = (now - session.started_at).total_seconds()
        session.actual_duration_minutes = max(0, int(elapsed_seconds // 60))

    async def _get_active_session(self, user_id: uuid.UUID) -> FocusSession | None:
        result = await self.db.execute(
            select(FocusSession).where(
                FocusSession.user_id == user_id,
                FocusSession.status == FocusSessionStatus.ACTIVE,
            )
        )
        return result.scalar_one_or_none()

    async def _get_owned_session(
        self, user_id: uuid.UUID, session_id: uuid.UUID, expected_status: FocusSessionStatus
    ) -> FocusSession:
        result = await self.db.execute(
            select(FocusSession).where(
                FocusSession.id == session_id, FocusSession.user_id == user_id
            )
        )
        session = result.scalar_one_or_none()

        if session is None:
            raise NotFoundError("Fokus seansi topilmadi.")
        if session.status != expected_status:
            raise ConflictError(
                f"Bu amal faqat '{expected_status.value}' holatidagi seanslar uchun mumkin."
            )

        return session
