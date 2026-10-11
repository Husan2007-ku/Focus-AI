"""
Foydalanuvchi profili biznes logikasi.

DB bilan ishlash `UserRepository`ga o'tkazilgan (TZ v2.0, 3-band).
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserProfileUpdateSchema

logger = get_logger(__name__)


class UserService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = UserRepository(db)

    async def update_profile(self, user: User, data: UserProfileUpdateSchema) -> User:
        """Faqat so'rovda haqiqatan yuborilgan maydonlarni yangilaydi — yuborilmagan
        maydon (None emas, umuman yuborilmagan) eskisicha qoladi."""
        updates = data.model_dump(exclude_unset=True)
        for field, value in updates.items():
            setattr(user, field, value)

        user = await self.repo.save(user)
        logger.info("user_profile_updated", user_id=str(user.id), fields=list(updates.keys()))
        return user

    async def deactivate(self, user: User) -> None:
        """Hisobni faolsizlantiradi (yumshoq o'chirish) — yozuvlar saqlanib qoladi,
        lekin `get_current_user` endi bu foydalanuvchini kirita olmaydi."""
        user.is_active = False
        await self.repo.save(user)
        logger.warning("user_deactivated", user_id=str(user.id))
