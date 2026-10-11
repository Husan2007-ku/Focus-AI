"""
Vaqt zonasi yordamchi funksiyalari.

FocusAI foydalanuvchilari asosan O'zbekistonda, shuning uchun "bugun"
tushunchasi UTC emas, Asia/Tashkent vaqt zonasi bo'yicha hisoblanadi —
aks holda kechqurun soat 23:00dan keyin (UTC bo'yicha allaqachon ertangi
kun) foydalanuvchi uchun "kunlik" yozuvlar noto'g'ri sanaga tushib qolardi.
"""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

TASHKENT_TZ = ZoneInfo("Asia/Tashkent")


def get_tashkent_today() -> date:
    return datetime.now(TASHKENT_TZ).date()


def get_tashkent_day_start_utc(day: date | None = None) -> datetime:
    """Berilgan kunning (berilmasa — bugungi kunning) Toshkent vaqti bo'yicha
    00:00'i, UTC-aware `datetime` sifatida qaytariladi.

    MUHIM: bu shunchaki `datetime(y, m, d, tzinfo=UTC)` EMAS — Toshkent
    UTC+5'da, shuning uchun Toshkent 00:00'i haqiqatda UTC 19:00 (oldingi
    kun) bo'ladi. DB'dagi `started_at` kabi timezone-aware ustunlar bilan
    to'g'ri solishtirish uchun shu farq muhim (aks holda kechqurun 19:00
    dan 00:00 UTC gacha bo'lgan Toshkent ertalabki soatlar noto'g'ri
    haftaga/kunga tushib qolardi)."""
    target_day = day or get_tashkent_today()
    local_midnight = datetime(target_day.year, target_day.month, target_day.day, tzinfo=TASHKENT_TZ)
    return local_midnight.astimezone(UTC)
