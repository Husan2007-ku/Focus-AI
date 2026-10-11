"""
Ichki monitoring (admin.py) biznes logikasi.

DB bilan ishlash `AdminRepository`ga o'tkazilgan (TZ v2.0, 3-band). Bu
servisning o'zi hech qanday biznes qoidasini bilmaydi — faqat bir necha
domendan kelgan raqamlarni bitta javobga yig'ib beradi (dashboard uchun).
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.admin_repository import AdminRepository


class AdminService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = AdminRepository(db)

    async def get_dashboard_stats(self) -> dict:
        total_users = await self.repo.count_users()
        active_users = await self.repo.count_active_users()
        users_by_tier = await self.repo.count_users_by_tier()
        total_organizations = await self.repo.count_organizations()
        total_sessions, total_minutes = await self.repo.get_platform_focus_stats()

        return {
            "total_users": total_users,
            "active_users": active_users,
            "users_by_tier": users_by_tier,
            "total_organizations": total_organizations,
            "total_completed_sessions": total_sessions,
            "total_focus_minutes": total_minutes,
        }
