"""
`app.utils.timezone` uchun test — "bugun" UTC emas, Asia/Tashkent bo'yicha
hisoblanishini tasdiqlaydi (TZ 5-bo'lim: kunlik yozuvlar uchun muhim).
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.utils.timezone import TASHKENT_TZ, get_tashkent_today


def test_tashkent_tz_is_correct_zone() -> None:
    assert TASHKENT_TZ.key == "Asia/Tashkent"


def test_get_tashkent_today_returns_a_date() -> None:
    result = get_tashkent_today()
    assert isinstance(result, date)


def test_get_tashkent_today_matches_manual_calculation() -> None:
    expected = datetime.now(ZoneInfo("Asia/Tashkent")).date()
    assert get_tashkent_today() == expected
