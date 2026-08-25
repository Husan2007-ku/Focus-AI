"""
Moliyaviy maqsadlar muddatini avtomatik tekshiruvchi fon vazifasi.

Celery Beat orqali muntazam (masalan, har soatda) ishga tushiriladi va
muddati o'tgan, lekin hali hal qilinmagan (`ACTIVE`) barcha maqsadlarni
tekshirib, muvaffaqiyat/muvaffaqiyatsizlikni aniqlaydi.
"""

import asyncio

from app.core.database import AsyncSessionLocal
from app.core.logging import get_logger
from app.services.finance_service import FinanceService
from app.tasks.celery_app import celery_app

logger = get_logger(__name__)


async def _resolve_expired_commitments_async() -> int:
    async with AsyncSessionLocal() as db:
        service = FinanceService(db)
        expired = await service.get_expired_active_commitments()

        for commitment in expired:
            await service.resolve_commitment(commitment)

        return len(expired)


@celery_app.task(name="app.tasks.finance_tasks.resolve_expired_commitments")
def resolve_expired_commitments() -> int:
    count = asyncio.run(_resolve_expired_commitments_async())
    logger.info("expired_commitments_resolved", count=count)
    return count
