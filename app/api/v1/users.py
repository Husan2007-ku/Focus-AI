"""
Foydalanuvchi profili endpoint'lari (`/auth/me`dan tashqari — u faqat
autentifikatsiya konteksti uchun qisqa shakl qaytaradi, bu yerda esa
to'liq profil CRUD).
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.user import UserProfileSchema, UserProfileUpdateSchema
from app.services.user_service import UserService

router = APIRouter()


@router.get("/me", response_model=UserProfileSchema)
async def get_my_profile(current_user: User = Depends(get_current_user)) -> UserProfileSchema:
    """Joriy foydalanuvchining to'liq profil ma'lumotlari."""
    return UserProfileSchema.model_validate(current_user)


@router.patch("/me", response_model=UserProfileSchema)
async def update_my_profile(
    payload: UserProfileUpdateSchema,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserProfileSchema:
    """Profil maydonlarini (ism, yosh, maqsad, avatar) qisman yangilaydi —
    faqat so'rovda yuborilgan maydonlar o'zgaradi."""
    service = UserService(db)
    user = await service.update_profile(current_user, payload)
    return UserProfileSchema.model_validate(user)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_my_account(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Hisobni faolsizlantiradi (yumshoq o'chirish) — ma'lumotlar o'chirilmaydi,
    lekin foydalanuvchi endi tizimga kira olmaydi."""
    service = UserService(db)
    await service.deactivate(current_user)
