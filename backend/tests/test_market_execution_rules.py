from app.services.market_data_service import MarketCandle
from app.services.market_execution_rule_service import (
    is_regular_session_candle,
    normalize_order_price,
    validate_market_order,
)
from app.services.market_rule_service import get_market_rule


def test_normalize_order_price_rounds_buy_up_and_sell_down():
    assert normalize_order_price("BUY", 10.001) == 10.01
    assert normalize_order_price("SELL", 10.009) == 10.00
    assert normalize_order_price("BUY", 10.01) == 10.01
    assert normalize_order_price("SELL", 10.01) == 10.01


def test_a_share_buy_above_limit_up_is_blocked():
    result = validate_market_order(
        market_rule=get_market_rule("A_SHARE"),
        candle=MarketCandle(
            time="2026-01-02 09:35",
            open=11.02,
            high=11.02,
            low=11.02,
            close=11.02,
            previous_close=10.0,
        ),
        side="BUY",
        execution_price=11.02,
        quantity=100,
    )

    assert result.allowed is False
    assert result.rule == "涨跌停"
    assert "高于涨停价 11.00" in result.reason


def test_a_share_sell_below_limit_down_is_blocked():
    result = validate_market_order(
        market_rule=get_market_rule("A_SHARE"),
        candle=MarketCandle(
            time="2026-01-02 09:35",
            open=8.98,
            high=8.98,
            low=8.98,
            close=8.98,
            previous_close=10.0,
        ),
        side="SELL",
        execution_price=8.98,
        quantity=100,
    )

    assert result.allowed is False
    assert result.rule == "涨跌停"
    assert "低于跌停价 9.00" in result.reason


def test_a_share_missing_previous_close_is_blocked():
    result = validate_market_order(
        market_rule=get_market_rule("A_SHARE"),
        candle=MarketCandle(time="2026-01-02 09:35", close=10.0),
        side="BUY",
        execution_price=10.0,
        quantity=100,
    )

    assert result.allowed is False
    assert result.rule == "前收盘价"
    assert result.reason == "行情缺少前收盘价，无法执行 A 股涨跌停规则"


def test_regular_session_checks_a_share_lunch_break_and_us_regular_hours():
    assert (
        is_regular_session_candle(
            get_market_rule("A_SHARE"),
            MarketCandle(time="2026-01-02 11:30", close=10.0),
        )
        is True
    )
    assert (
        is_regular_session_candle(
            get_market_rule("A_SHARE"),
            MarketCandle(time="2026-01-02 11:31", close=10.0),
        )
        is False
    )
    assert (
        is_regular_session_candle(
            get_market_rule("US_STOCK"),
            MarketCandle(time="2026-01-02 16:00", close=180.0),
        )
        is True
    )
    assert (
        is_regular_session_candle(
            get_market_rule("US_STOCK"),
            MarketCandle(time="2026-01-02 16:01", close=180.0),
        )
        is False
    )
