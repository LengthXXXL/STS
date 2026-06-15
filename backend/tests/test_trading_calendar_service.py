from datetime import date

from app.services.trading_calendar_service import (
    count_trading_days,
    has_missing_trading_day,
    is_trading_day,
)


def test_a_share_holidays_are_not_trading_days():
    assert is_trading_day("A_SHARE", date(2026, 2, 16)) is False
    assert is_trading_day("A_SHARE", date(2026, 2, 24)) is True


def test_us_stock_holidays_are_not_trading_days():
    assert is_trading_day("US_STOCK", date(2025, 1, 9)) is False
    assert is_trading_day("US_STOCK", date(2026, 4, 3)) is False
    assert is_trading_day("US_STOCK", date(2026, 4, 6)) is True


def test_missing_trading_day_skips_holiday_breaks_but_keeps_regular_weekdays():
    assert has_missing_trading_day("A_SHARE", date(2026, 2, 13), date(2026, 2, 24)) is False
    assert has_missing_trading_day("US_STOCK", date(2026, 4, 2), date(2026, 4, 6)) is False
    assert has_missing_trading_day("US_STOCK", date(2026, 3, 2), date(2026, 3, 6)) is True


def test_count_trading_days_uses_market_holidays():
    assert count_trading_days("A_SHARE", date(2026, 2, 15), date(2026, 2, 24)) == 1
    assert count_trading_days("US_STOCK", date(2026, 4, 3), date(2026, 4, 6)) == 1
