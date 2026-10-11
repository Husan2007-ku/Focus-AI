"""
Ichki monitoring endpoint'lari.

MUHIM: bu router oddiy foydalanuvchi tokeni (`get_current_user`) bilan
EMAS, alohida `verify_admin_key` (X-Admin-Key header) bilan himoyalangan —
qarang `app/api/deps.py`. Mobil ilova foydalanuvchilariga umuman
ko'rinmaydi, faqat ichki monitoring/dashboard uchun.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import verify_admin_key
from app.core.database import get_db
from app.schemas.admin import AdminDashboardSchema
from app.services.admin_service import AdminService

router = APIRouter(dependencies=[Depends(verify_admin_key)])


@router.get("/dashboard", response_model=AdminDashboardSchema)
async def get_admin_dashboard(db: AsyncSession = Depends(get_db)) -> AdminDashboardSchema:
    """Platforma bo'yicha umumiy raqamlar: foydalanuvchilar, tariflar, fokus statistikasi."""
    service = AdminService(db)
    stats = await service.get_dashboard_stats()
    return AdminDashboardSchema.model_validate(stats)
