"""
Vaqt zonasi yordamchi funksiyalari.

FocusAI foydalanuvchilari asosan O'zbekistonda, shuning uchun "bugun"
tushunchasi UTC emas, Asia/Tashkent vaqt zonasi bo'yicha hisoblanadi —
aks holda kechqurun soat 23:00dan keyin (UTC bo'yicha allaqachon ertangi
kun) foydalanuvchi uchun "kunlik" yozuvlar noto'g'ri sanaga tushib qolardi.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

TASHKENT_TZ = ZoneInfo("Asia/Tashkent")


def get_tashkent_today() -> date:
    return datetime.now(TASHKENT_TZ).date()
