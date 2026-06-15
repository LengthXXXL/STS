from datetime import date, timedelta


MarketCode = str

A_SHARE_HOLIDAYS: dict[int, set[date]] = {
    2025: {
        date(2025, 1, 1),
        *{date(2025, 1, day) for day in range(28, 32)},
        *{date(2025, 2, day) for day in range(1, 5)},
        *{date(2025, 4, day) for day in range(4, 7)},
        *{date(2025, 5, day) for day in range(1, 6)},
        date(2025, 5, 31),
        date(2025, 6, 1),
        date(2025, 6, 2),
        *{date(2025, 10, day) for day in range(1, 9)},
    },
    2026: {
        date(2026, 1, 1),
        date(2026, 1, 2),
        date(2026, 1, 3),
        *{date(2026, 2, day) for day in range(15, 24)},
        *{date(2026, 4, day) for day in range(4, 7)},
        *{date(2026, 5, day) for day in range(1, 6)},
        date(2026, 6, 19),
        date(2026, 6, 20),
        date(2026, 6, 21),
        date(2026, 9, 25),
        date(2026, 9, 26),
        date(2026, 9, 27),
        *{date(2026, 10, day) for day in range(1, 8)},
    },
}

US_STOCK_HOLIDAYS: dict[int, set[date]] = {
    2025: {
        date(2025, 1, 1),
        date(2025, 1, 20),
        date(2025, 2, 17),
        date(2025, 4, 18),
        date(2025, 5, 26),
        date(2025, 6, 19),
        date(2025, 7, 4),
        date(2025, 9, 1),
        date(2025, 11, 27),
        date(2025, 12, 25),
    },
    2026: {
        date(2026, 1, 1),
        date(2026, 1, 19),
        date(2026, 2, 16),
        date(2026, 4, 3),
        date(2026, 5, 25),
        date(2026, 6, 19),
        date(2026, 7, 3),
        date(2026, 9, 7),
        date(2026, 11, 26),
        date(2026, 12, 25),
    },
}

MARKET_HOLIDAYS: dict[MarketCode, dict[int, set[date]]] = {
    "A_SHARE": A_SHARE_HOLIDAYS,
    "US_STOCK": US_STOCK_HOLIDAYS,
}


def is_trading_day(market: MarketCode, day: date) -> bool:
    if day.weekday() >= 5:
        return False
    holidays = MARKET_HOLIDAYS.get(market, {})
    return day not in holidays.get(day.year, set())


def count_trading_days(market: MarketCode, start: date, end: date) -> int:
    cursor = start
    count = 0
    while cursor <= end:
        if is_trading_day(market, cursor):
            count += 1
        cursor += timedelta(days=1)
    return count


def has_missing_trading_day(market: MarketCode, previous_date: date, next_date: date) -> bool:
    cursor = previous_date + timedelta(days=1)
    while cursor < next_date:
        if is_trading_day(market, cursor):
            return True
        cursor += timedelta(days=1)
    return False
