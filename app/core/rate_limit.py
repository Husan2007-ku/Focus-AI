"""
So'rov chastotasini cheklash (rate limiting) — IP manzil bo'yicha.

Nega kerak (xavfsizlik auditi, 2026-10-12): OTP/Google/refresh kabi hali
autentifikatsiya qilinmagan (token talab qilmaydigan) endpoint'lar hech
qanday global chegarasiz qolsa, bitta IP manzildan ko'plab turli telefon
raqamlariga OTP so'rab SMS byudjetini sarflash ("SMS pumping" firibgarligi)
yoki Payme/Click webhook'larini haddan tashqari ko'p chaqirish mumkin.

Har bir OTP so'rovining o'zida allaqachon TELEFON bo'yicha cooldown/urinish
limiti bor (`auth_service.py`) — bu yerdagi limit IP darajasida qo'shimcha
himoya qatlami, turli telefon raqamlari bilan sprey qilishdan himoya qiladi.

Hisoblagich Redis'da saqlanadi — bir nechta API instance (yoki qayta ishga
tushirish) orasida ham to'g'ri ishlaydi.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

limiter = Limiter(key_func=get_remote_address, storage_uri=settings.REDIS_URL)
