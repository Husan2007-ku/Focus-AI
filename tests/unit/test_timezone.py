"""
`app.utils.timezone` uchun test — "bugun" UTC emas, Asia/Tashkent bo'yicha
hisoblanishini tasdiqlaydi (TZ 5-bo'lim: kunlik yozuvlar uchun muhim).
"""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.utils.timezone import TASHKENT_TZ, get_tashkent_day_start_utc, get_tashkent_today


def test_tashkent_tz_is_correct_zone() -> None:
    assert TASHKENT_TZ.key == "Asia/Tashkent"


def test_get_tashkent_today_returns_a_date() -> None:
    result = get_tashkent_today()
    assert isinstance(result, date)


def test_get_tashkent_today_matches_manual_calculation() -> None:
    expected = datetime.now(ZoneInfo("Asia/Tashkent")).date()
    assert get_tashkent_today() == expected


def test_day_start_is_tashkent_midnight_not_utc_midnight() -> None:
    """MUHIM: Toshkent UTC+5'da — shuning uchun Toshkent 00:00'i UTC 00:00
    EMAS, balki oldingi kunning UTC 19:00'i bo'lishi kerak."""
    day = date(2026, 6, 15)
    result = get_tashkent_day_start_utc(day)

    assert result == datetime(2026, 6, 14, 19, 0, tzinfo=UTC)


def test_day_start_defaults_to_today() -> None:
    result = get_tashkent_day_start_utc()
    expected_date = get_tashkent_today()

    # Natija shu kunning Toshkent 00:00'iga to'g'ri keladi — bugungi kun
    # boshlanishidan keyin va ertangi kun boshlanishidan oldin.
    assert result <= datetime.now(UTC)
    assert result > datetime.now(UTC) - timedelta(days=1, hours=1)
    assert result.astimezone(TASHKENT_TZ).date() == expected_date
