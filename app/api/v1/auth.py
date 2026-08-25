"""
Autentifikatsiya endpoint'lari: OTP, Google OAuth, token yangilash, logout.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.security import revoke_refresh_token, rotate_refresh_token
from app.models.user import User
from app.schemas.auth import (
    GoogleAuthSchema,
    OTPRequestSchema,
    OTPVerifySchema,
    RefreshTokenSchema,
    TokenResponseSchema,
    UserResponseSchema,
)
from app.services.auth_service import AuthService

router = APIRouter()


@router.post("/otp/request", status_code=status.HTTP_204_NO_CONTENT)
async def request_otp(payload: OTPRequestSchema, db: AsyncSession = Depends(get_db)) -> None:
    """Telefon raqamiga bir martalik tasdiqlash kodini yuboradi."""
    service = AuthService(db)
    await service.request_otp(payload.phone_number)


@router.post("/otp/verify", response_model=TokenResponseSchema)
async def verify_otp(
    payload: OTPVerifySchema, db: AsyncSession = Depends(get_db)
) -> TokenResponseSchema:
    """Kodni tasdiqlaydi va access/refresh token juftligini qaytaradi."""
    service = AuthService(db)
    tokens = await service.verify_otp(payload.phone_number, payload.code)
    return TokenResponseSchema(**tokens)


@router.post("/google", response_model=TokenResponseSchema)
async def google_login(
    payload: GoogleAuthSchema, db: AsyncSession = Depends(get_db)
) -> TokenResponseSchema:
    """Google ID token orqali kirish/ro'yxatdan o'tish."""
    service = AuthService(db)
    tokens = await service.google_login(payload.id_token)
    return TokenResponseSchema(**tokens)


@router.post("/refresh", response_model=TokenResponseSchema)
async def refresh_token(payload: RefreshTokenSchema) -> TokenResponseSchema:
    """Refresh token'ni yangi juftlikka almashtiradi (rotatsiya bilan)."""
    tokens = await rotate_refresh_token(payload.refresh_token)
    return TokenResponseSchema(**tokens)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(payload: RefreshTokenSchema) -> None:
    """Refresh token'ni bekor qiladi."""
    await revoke_refresh_token(payload.refresh_token)


@router.get("/me", response_model=UserResponseSchema)
async def get_me(current_user: User = Depends(get_current_user)) -> UserResponseSchema:
    """Joriy autentifikatsiya qilingan foydalanuvchi ma'lumotlari."""
    return UserResponseSchema.model_validate(current_user)
