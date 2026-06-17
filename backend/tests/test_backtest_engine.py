from app.schemas.backtest import BacktestRunRequest
from app.services.backtest_service import (
    MarketCandle,
    run_backtest,
    run_backtest_with_candles,
)
from app.services.market_rule_service import get_market_rule
from app.services.trading_cost_service import affordable_buy_quantity, calculate_trade_fill


def _request(nodes, *, edges=None, initial_cash=1000, market="US_STOCK"):
    return BacktestRunRequest.model_validate(
        {
            "strategy": {
                "version": 1,
                "nodes": nodes,
                "edges": edges or [],
                "viewport": {"x": 0, "y": 0, "scale": 1},
            },
            "config": {
                "market": market,
                "symbol": "TEST",
                "timeframe": "5m",
                "startDate": "2026-01-01",
                "endDate": "2026-01-05",
                "initialCash": initial_cash,
            },
        }
    )


def test_cost_helper_applies_a_share_buy_slippage_and_fees():
    rule = get_market_rule("A_SHARE")

    fill = calculate_trade_fill(
        side="BUY",
        base_price=10,
        quantity=900,
        market_rule=rule,
    )

    assert fill.price == 10.001
    assert fill.gross_amount == 9000.9
    assert fill.cost_breakdown["commission"] == 5
    assert fill.cost_breakdown["marketFees"] == 0.58
    assert fill.cost_breakdown["stampDuty"] == 0
    assert fill.cost_amount == 5.58
    assert fill.net_cash_change == -9006.48


def test_cost_helper_applies_us_sell_regulatory_fees():
    rule = get_market_rule("US_STOCK")

    fill = calculate_trade_fill(
        side="SELL",
        base_price=11,
        quantity=99,
        market_rule=rule,
    )

    assert fill.price == 10.9989
    assert fill.gross_amount == 1088.89
    assert fill.cost_breakdown["secFee"] == 0.02
    assert fill.cost_breakdown["finraTaf"] == 0.02
    assert fill.cost_amount == 0.04
    assert fill.net_cash_change == 1088.85


def test_affordable_buy_quantity_steps_down_for_a_share_costs():
    rule = get_market_rule("A_SHARE")

    quantity = affordable_buy_quantity(
        cash=10000,
        base_price=10,
        target_cash=10000,
        market_rule=rule,
    )

    assert quantity == 900


def test_engine_includes_us_cost_fields_and_costs_lower_return():
    request = _request(
        [
            {
                "id": "buy-1",
                "type": "buy",
                "label": "买入",
                "x": 0,
                "y": 0,
                "params": {"sizePercent": "100", "orderType": "market"},
            },
            {
                "id": "take-profit-1",
                "type": "take-profit",
                "label": "止盈",
                "x": 160,
                "y": 0,
                "params": {"profitRate": "5", "sellPercent": "100"},
            },
        ],
        initial_cash=10000,
        market="US_STOCK",
    )
    candles = [
        MarketCandle(time="2026-01-01 09:35", open=10, high=10.1, low=9.9, close=10),
        MarketCandle(time="2026-01-01 09:40", open=10, high=10.8, low=9.9, close=10.5),
    ]

    result = run_backtest_with_candles(request, candles)

    assert [trade.side for trade in result.trades] == ["BUY", "SELL"]
    assert result.trades[0].price == 10.001
    assert result.trades[0].slippage_amount > 0
    assert result.trades[0].net_cash_change < 0
    assert result.trades[1].price < 10.501
    assert result.trades[1].cost_breakdown["secFee"] > 0
    assert result.trades[1].cost_breakdown["finraTaf"] > 0
    assert result.summary.endingEquity < 10500


def test_engine_applies_a_share_stamp_duty_on_sell_only():
    request = _request(
        [
            {
                "id": "buy-1",
                "type": "buy",
                "label": "买入",
                "x": 0,
                "y": 0,
                "params": {"sizePercent": "100", "orderType": "market"},
            },
            {
                "id": "take-profit-1",
                "type": "take-profit",
                "label": "止盈",
                "x": 160,
                "y": 0,
                "params": {"profitRate": "5", "sellPercent": "100"},
            },
        ],
        initial_cash=10000,
        market="A_SHARE",
    )
    candles = [
        MarketCandle(
            time="2026-01-01 09:35",
            open=10,
            high=10.1,
            low=9.9,
            close=10,
            previous_close=10,
        ),
        MarketCandle(
            time="2026-01-01 09:40",
            open=10,
            high=10.8,
            low=9.9,
            close=10.5,
            previous_close=10,
        ),
        MarketCandle(
            time="2026-01-02 09:35",
            open=10.6,
            high=10.8,
            low=10.1,
            close=10.7,
            previous_close=10,
        ),
    ]

    result = run_backtest_with_candles(request, candles)

    assert [trade.side for trade in result.trades] == ["BUY", "SELL"]
    assert result.trades[0].cost_breakdown["stampDuty"] == 0
    assert result.trades[1].cost_breakdown["stampDuty"] > 0


def test_engine_skips_buy_when_cost_adjusted_quantity_is_not_affordable():
    request = _request(
        [
            {
                "id": "buy-1",
                "type": "buy",
                "label": "买入",
                "x": 0,
                "y": 0,
                "params": {"sizePercent": "100", "orderType": "market"},
            }
        ],
        initial_cash=50,
        market="A_SHARE",
    )
    candles = [
        MarketCandle(
            time="2026-01-01 09:35",
            open=10,
            high=10.1,
            low=9.9,
            close=10,
            previous_close=10,
        ),
        MarketCandle(
            time="2026-01-02 09:35",
            open=10,
            high=10.1,
            low=9.9,
            close=10,
            previous_close=10,
        ),
    ]

    result = run_backtest_with_candles(request, candles)

    assert result.trades == []
    assert any(item.event_type == "ORDER_BLOCKED" for item in result.timeline)
    assert "资金不足" in " ".join(item.description for item in result.timeline)


def test_engine_blocks_a_share_buy_above_limit_up():
    request = _request(
        [
            {
                "id": "buy-1",
                "type": "buy",
                "label": "买入",
                "x": 0,
                "y": 0,
                "params": {"sizePercent": "100", "orderType": "market"},
            }
        ],
        initial_cash=10000,
        market="A_SHARE",
    )
    candles = [
        MarketCandle(
            time="2026-01-02 09:35",
            open=10.8,
            high=10.9,
            low=10.7,
            close=10.8,
            previous_close=10.0,
        ),
        MarketCandle(
            time="2026-01-02 09:40",
            open=11.02,
            high=11.02,
            low=11.02,
            close=11.02,
            previous_close=10.0,
        ),
    ]

    result = run_backtest_with_candles(request, candles)

    assert result.trades == []
    blocked = [item for item in result.timeline if item.event_type == "ORDER_BLOCKED"]
    assert len(blocked) == 1
    assert blocked[0].side == "BUY"
    assert blocked[0].rule == "涨跌停"
    assert "高于涨停价 11.00" in blocked[0].description


def test_engine_caps_a_share_buy_at_limit_up_after_slippage():
    request = _request(
        [
            {
                "id": "buy-1",
                "type": "buy",
                "label": "买入",
                "x": 0,
                "y": 0,
                "params": {"sizePercent": "100", "orderType": "market"},
            }
        ],
        initial_cash=10000,
        market="A_SHARE",
    )
    candles = [
        MarketCandle(
            time="2026-01-02 09:35",
            open=10.8,
            high=10.9,
            low=10.7,
            close=10.8,
            previous_close=10.0,
        ),
        MarketCandle(
            time="2026-01-02 09:40",
            open=11.0,
            high=11.0,
            low=11.0,
            close=11.0,
            previous_close=10.0,
        ),
    ]

    result = run_backtest_with_candles(request, candles)

    assert [trade.side for trade in result.trades] == ["BUY"]
    assert result.trades[0].price == 11.0
    assert [item.event_type for item in result.timeline] == ["TRADE_FILLED"]


def test_engine_blocks_a_share_sell_below_limit_down_after_t_plus_one():
    request = _request(
        [
            {
                "id": "buy-1",
                "type": "buy",
                "label": "买入",
                "x": 0,
                "y": 0,
                "params": {"sizePercent": "100", "orderType": "market"},
            },
            {
                "id": "stop-loss-1",
                "type": "stop-loss",
                "label": "止损",
                "x": 160,
                "y": 0,
                "params": {"lossRate": "11", "sellPercent": "100"},
            },
        ],
        initial_cash=10000,
        market="A_SHARE",
    )
    candles = [
        MarketCandle(
            time="2026-01-02 09:35",
            open=10.0,
            high=10.1,
            low=9.9,
            close=10.0,
            previous_close=10.0,
        ),
        MarketCandle(
            time="2026-01-05 09:35",
            open=10.0,
            high=10.1,
            low=9.9,
            close=10.0,
            previous_close=10.0,
        ),
        MarketCandle(
            time="2026-01-06 09:35",
            open=8.9,
            high=9.0,
            low=8.8,
            close=8.9,
            previous_close=10.0,
        ),
    ]

    result = run_backtest_with_candles(request, candles)

    assert [trade.side for trade in result.trades] == ["BUY"]
    blocked = [item for item in result.timeline if item.event_type == "ORDER_BLOCKED"]
    assert len(blocked) == 1
    assert blocked[0].side == "SELL"
    assert blocked[0].rule == "涨跌停"
    assert "低于跌停价 9.00" in blocked[0].description
    assert "T+1" not in blocked[0].description


def test_engine_caps_a_share_sell_at_limit_down_after_slippage():
    request = _request(
        [
            {
                "id": "buy-1",
                "type": "buy",
                "label": "买入",
                "x": 0,
                "y": 0,
                "params": {"sizePercent": "100", "orderType": "market"},
            },
            {
                "id": "sell-1",
                "type": "sell",
                "label": "卖出",
                "x": 160,
                "y": 0,
                "params": {"sellPercent": "100"},
            },
        ],
        initial_cash=10000,
        market="A_SHARE",
    )
    candles = [
        MarketCandle(
            time="2026-01-02 09:35",
            open=10.0,
            high=10.1,
            low=9.9,
            close=10.0,
            previous_close=10.0,
        ),
        MarketCandle(
            time="2026-01-05 09:35",
            open=10.0,
            high=10.1,
            low=9.9,
            close=10.0,
            previous_close=10.0,
        ),
        MarketCandle(
            time="2026-01-06 09:35",
            open=9.0,
            high=9.1,
            low=9.0,
            close=9.05,
            previous_close=10.0,
        ),
    ]

    result = run_backtest_with_candles(request, candles)

    assert [trade.side for trade in result.trades] == ["BUY", "SELL"]
    assert result.trades[1].price == 9.0
    assert not any(item.event_type == "ORDER_BLOCKED" for item in result.timeline)


def test_engine_skips_non_session_candles_before_triggering_orders():
    request = _request(
        [
            {
                "id": "buy-1",
                "type": "buy",
                "label": "买入",
                "x": 0,
                "y": 0,
                "params": {"sizePercent": "100", "orderType": "market"},
            }
        ],
        initial_cash=10000,
        market="US_STOCK",
    )
    candles = [
        MarketCandle(time="2026-01-02 08:00", open=10, high=10.1, low=9.9, close=10),
        MarketCandle(time="2026-01-02 09:35", open=10.2, high=10.3, low=10.1, close=10.2),
    ]

    result = run_backtest_with_candles(request, candles)

    assert result.trades == []
    assert result.timeline == []


def test_off_session_candle_does_not_advance_holding_bars_for_sell_condition():
    request = _request(
        [
            {
                "id": "buy-1",
                "type": "buy",
                "label": "买入",
                "x": 0,
                "y": 0,
                "params": {"sizePercent": "100", "orderType": "market"},
            },
            {
                "id": "holding-bars-1",
                "type": "position-state",
                "label": "持仓K线数",
                "x": 160,
                "y": 0,
                "params": {"state": "holding-bars-gte", "threshold": "2"},
            },
            {
                "id": "sell-1",
                "type": "sell",
                "label": "卖出",
                "x": 320,
                "y": 0,
                "params": {"sellPercent": "100"},
            },
        ],
        edges=[{"id": "holding-sell", "from": "holding-bars-1", "to": "sell-1"}],
        initial_cash=10000,
        market="US_STOCK",
    )
    regular_candles = [
        MarketCandle(time="2026-01-01 15:50", open=10.0, high=10.1, low=9.9, close=10.0),
        MarketCandle(time="2026-01-01 15:55", open=10.0, high=10.1, low=9.9, close=10.0),
        MarketCandle(time="2026-01-02 09:35", open=10.0, high=10.1, low=9.9, close=10.0),
        MarketCandle(time="2026-01-02 09:40", open=10.0, high=10.1, low=9.9, close=10.0),
        MarketCandle(time="2026-01-02 09:45", open=10.0, high=10.1, low=9.9, close=10.0),
    ]
    candles_with_off_session_bar = [
        regular_candles[0],
        regular_candles[1],
        MarketCandle(time="2026-01-01 16:05", open=10.0, high=10.1, low=9.9, close=10.0),
        *regular_candles[2:],
    ]

    baseline = run_backtest_with_candles(request, regular_candles)
    variant = run_backtest_with_candles(request, candles_with_off_session_bar)

    assert [trade.side for trade in baseline.trades] == ["BUY", "SELL"]
    assert [trade.side for trade in variant.trades] == ["BUY", "SELL"]
    baseline_sell_time = next(trade.time for trade in baseline.trades if trade.side == "SELL")
    variant_sell_time = next(trade.time for trade in variant.trades if trade.side == "SELL")
    assert baseline_sell_time == "2026-01-02 09:45"
    assert variant_sell_time == baseline_sell_time


def test_engine_sizes_buy_with_normalized_execution_price():
    request = _request(
        [
            {
                "id": "buy-1",
                "type": "buy",
                "label": "买入",
                "x": 0,
                "y": 0,
                "params": {"sizePercent": "100", "orderType": "market"},
            }
        ],
        initial_cash=1000.01,
        market="US_STOCK",
    )
    candles = [
        MarketCandle(time="2026-01-02 09:35", open=333.0, high=333.2, low=332.9, close=333.0),
        MarketCandle(
            time="2026-01-02 09:40",
            open=333.301,
            high=333.4,
            low=333.2,
            close=333.301,
        ),
    ]

    result = run_backtest_with_candles(request, candles)

    buy_trade = result.trades[0]
    assert buy_trade.side == "BUY"
    assert buy_trade.quantity == 2
    assert abs(buy_trade.net_cash_change) <= request.config.initialCash


def test_engine_final_close_uses_last_regular_session_candle():
    request = _request(
        [
            {
                "id": "buy-1",
                "type": "buy",
                "label": "买入",
                "x": 0,
                "y": 0,
                "params": {"sizePercent": "100", "orderType": "market"},
            }
        ],
        initial_cash=10000,
        market="US_STOCK",
    )
    candles = [
        MarketCandle(time="2026-01-02 09:35", open=10.0, high=10.1, low=9.9, close=10.0),
        MarketCandle(time="2026-01-02 09:40", open=10.2, high=10.3, low=10.1, close=10.2),
        MarketCandle(time="2026-01-02 16:05", open=10.5, high=10.6, low=10.4, close=10.5),
    ]

    result = run_backtest_with_candles(request, candles)

    assert [trade.side for trade in result.trades] == ["BUY", "SELL"]
    assert result.trades[-1].time == "2026-01-02 09:40"
    assert result.timeline[-1].event_type == "POSITION_CLOSED"
    assert not any(item.event_type == "ORDER_BLOCKED" for item in result.timeline)


def test_engine_buys_once_and_sells_when_take_profit_is_hit():
    request = _request(
        [
            {
                "id": "buy-1",
                "type": "buy",
                "label": "买入",
                "x": 0,
                "y": 0,
                "params": {"sizePercent": "50", "orderType": "market"},
            },
            {
                "id": "take-profit-1",
                "type": "take-profit",
                "label": "止盈",
                "x": 160,
                "y": 0,
                "params": {"profitRate": "5", "sellPercent": "100"},
            },
        ]
    )
    candles = [
        MarketCandle(time="2026-01-01 09:35", open=10.0, high=10.1, low=9.9, close=10.0),
        MarketCandle(time="2026-01-01 09:40", open=10.0, high=10.6, low=9.9, close=10.4),
    ]

    result = run_backtest_with_candles(request, candles)

    assert [trade.side for trade in result.trades] == ["BUY", "SELL"]
    assert result.trades[0].quantity == 49
    assert result.trades[1].reason == "止盈触发"
    assert result.summary.endingEquity == 1024.38
    assert result.summary.totalReturnPercent == 2.44
    assert result.summary.maxDrawdownPercent == 0
    assert result.summary.winRatePercent == 100
    assert result.equityCurve[-1].equity == 1024.38
    assert [item.event_type for item in result.timeline] == ["TRADE_FILLED", "TRADE_FILLED"]
    assert result.timeline[0].title == "买入成交"
    assert result.timeline[0].description == "买入积木触发"
    assert result.timeline[0].node_label == "买入"
    assert result.timeline[0].price == 10.001
    assert result.timeline[0].quantity == 49
    assert result.timeline[1].title == "卖出成交"
    assert result.timeline[1].description == "止盈触发"
    assert result.timeline[1].node_label == "止盈"
    assert result.timeline[1].price == 10.499


def test_engine_fills_ordinary_buy_at_next_candle_open():
    request = _request(
        [
            {
                "id": "buy-1",
                "type": "buy",
                "label": "买入",
                "x": 0,
                "y": 0,
                "params": {"sizePercent": "100", "orderType": "market"},
            }
        ]
    )
    candles = [
        MarketCandle(time="2026-01-01 09:35", open=10.0, high=10.8, low=9.9, close=10.5),
        MarketCandle(time="2026-01-01 09:40", open=11.0, high=12.2, low=10.9, close=12.0),
    ]

    result = run_backtest_with_candles(request, candles)

    assert result.trades[0].side == "BUY"
    assert result.trades[0].time == "2026-01-01 09:40"
    assert result.trades[0].price == 11.0011
    assert result.trades[0].quantity == 90


def test_engine_stop_loss_uses_low_touch_price_before_take_profit():
    request = _request(
        [
            {
                "id": "buy-1",
                "type": "buy",
                "label": "买入",
                "x": 0,
                "y": 0,
                "params": {"sizePercent": "100", "orderType": "market"},
            },
            {
                "id": "take-profit-1",
                "type": "take-profit",
                "label": "止盈",
                "x": 160,
                "y": 0,
                "params": {"profitRate": "10", "sellPercent": "100"},
            },
            {
                "id": "stop-loss-1",
                "type": "stop-loss",
                "label": "止损",
                "x": 320,
                "y": 0,
                "params": {"lossRate": "5", "sellPercent": "100"},
            },
        ]
    )
    candles = [
        MarketCandle(time="2026-01-01 09:35", open=10.0, high=10.2, low=9.8, close=10.0),
        MarketCandle(time="2026-01-01 09:40", open=10.0, high=11.5, low=9.2, close=10.8),
    ]

    result = run_backtest_with_candles(request, candles)

    assert [trade.side for trade in result.trades] == ["BUY", "SELL"]
    assert result.trades[0].price == 10.001
    assert result.trades[1].reason == "止损触发"
    assert result.trades[1].price == 9.4991
    assert result.summary.endingEquity == 950.27


def test_engine_take_profit_uses_high_touch_price():
    request = _request(
        [
            {
                "id": "buy-1",
                "type": "buy",
                "label": "买入",
                "x": 0,
                "y": 0,
                "params": {"sizePercent": "100", "orderType": "market"},
            },
            {
                "id": "take-profit-1",
                "type": "take-profit",
                "label": "止盈",
                "x": 160,
                "y": 0,
                "params": {"profitRate": "5", "sellPercent": "100"},
            },
        ]
    )
    candles = [
        MarketCandle(time="2026-01-01 09:35", open=10.0, high=10.1, low=9.9, close=10.0),
        MarketCandle(time="2026-01-01 09:40", open=10.0, high=10.8, low=9.9, close=10.2),
    ]

    result = run_backtest_with_candles(request, candles)

    assert [trade.side for trade in result.trades] == ["BUY", "SELL"]
    assert result.trades[1].reason == "止盈触发"
    assert result.trades[1].price == 10.499
    assert result.summary.endingEquity == 1049.26


def test_engine_blocks_a_share_same_day_sell_until_next_trading_day():
    request = _request(
        [
            {
                "id": "buy-1",
                "type": "buy",
                "label": "买入",
                "x": 0,
                "y": 0,
                "params": {"sizePercent": "100", "orderType": "market"},
            },
            {
                "id": "take-profit-1",
                "type": "take-profit",
                "label": "止盈",
                "x": 160,
                "y": 0,
                "params": {"profitRate": "1", "sellPercent": "100"},
            },
        ],
        initial_cash=10000,
        market="A_SHARE",
    )
    candles = [
        MarketCandle(
            time="2026-01-01 09:35",
            open=10.0,
            high=10.1,
            low=9.9,
            close=10.0,
            previous_close=10.0,
        ),
        MarketCandle(
            time="2026-01-01 09:40",
            open=10.0,
            high=11.0,
            low=9.9,
            close=11.0,
            previous_close=10.0,
        ),
        MarketCandle(
            time="2026-01-02 09:35",
            open=11.4,
            high=11.5,
            low=10.1,
            close=11.5,
            previous_close=11.0,
        ),
    ]

    result = run_backtest_with_candles(request, candles)

    assert [trade.side for trade in result.trades] == ["BUY", "SELL"]
    assert [event.event_type for event in result.events] == ["BLOCKED_ORDER"]
    assert result.events[0].time == "2026-01-01 09:40"
    assert result.events[0].side == "SELL"
    assert result.events[0].reason == "A股 T+1 规则限制，当日买入持仓不可卖出"
    assert result.events[0].rule == "T+1"
    blocked_items = [item for item in result.timeline if item.event_type == "ORDER_BLOCKED"]
    assert len(blocked_items) == 1
    assert blocked_items[0].title == "卖出信号被拦截"
    assert blocked_items[0].description == "A股 T+1 规则限制，当日买入持仓不可卖出"
    assert blocked_items[0].rule == "T+1"
    assert blocked_items[0].node_label == "止盈"
    assert result.trades[0].time == "2026-01-01 09:40"
    assert result.trades[0].quantity == 900
    assert result.trades[1].time == "2026-01-02 09:35"
    assert result.trades[1].reason == "止盈触发"
    assert result.trades[1].price == 10.099
    assert result.summary.endingEquity == 10072.5
    assert result.summary.totalReturnPercent == 0.73


def test_engine_keeps_a_share_position_open_when_backtest_ends_on_buy_day():
    request = _request(
        [
            {
                "id": "buy-1",
                "type": "buy",
                "label": "买入",
                "x": 0,
                "y": 0,
                "params": {"sizePercent": "100", "orderType": "market"},
            },
            {
                "id": "take-profit-1",
                "type": "take-profit",
                "label": "止盈",
                "x": 160,
                "y": 0,
                "params": {"profitRate": "1", "sellPercent": "100"},
            },
        ],
        initial_cash=10000,
        market="A_SHARE",
    )
    candles = [
        MarketCandle(
            time="2026-01-01 09:35",
            open=10.0,
            high=10.1,
            low=9.9,
            close=10.0,
            previous_close=10.0,
        ),
        MarketCandle(
            time="2026-01-01 09:40",
            open=10.0,
            high=11.0,
            low=9.9,
            close=11.0,
            previous_close=10.0,
        ),
    ]

    result = run_backtest_with_candles(request, candles)

    assert [trade.side for trade in result.trades] == ["BUY"]
    assert [event.event_type for event in result.events] == ["BLOCKED_ORDER"]
    assert result.events[0].reason == "A股 T+1 规则限制，当日买入持仓不可卖出"
    assert result.summary.endingEquity == 10893.52
    assert result.summary.tradeCount == 1
    assert result.equityCurve[-1].equity == 10893.52


def test_engine_applies_stop_loss_and_cooldown_before_reentering():
    request = _request(
        [
            {
                "id": "buy-1",
                "type": "buy",
                "label": "买入",
                "x": 0,
                "y": 0,
                "params": {"sizePercent": "100", "orderType": "market"},
            },
            {
                "id": "stop-loss-1",
                "type": "stop-loss",
                "label": "止损",
                "x": 160,
                "y": 0,
                "params": {"lossRate": "3", "sellPercent": "100"},
            },
            {
                "id": "cooldown-1",
                "type": "cooldown",
                "label": "冷却",
                "x": 320,
                "y": 0,
                "params": {"abnormalRule": "止损后冷却", "durationBars": "2"},
            },
        ]
    )
    candles = [
        MarketCandle(time="2026-01-01 09:35", open=10.0, high=10.1, low=9.9, close=10.0),
        MarketCandle(time="2026-01-01 09:40", open=10.0, high=10.1, low=9.6, close=9.8),
        MarketCandle(time="2026-01-01 09:45", open=9.8, high=9.9, low=9.7, close=9.8),
        MarketCandle(time="2026-01-01 09:50", open=9.9, high=10.0, low=9.8, close=9.9),
        MarketCandle(time="2026-01-01 09:55", open=10.0, high=10.1, low=9.9, close=10.0),
        MarketCandle(time="2026-01-01 10:00", open=10.0, high=10.2, low=9.9, close=10.1),
    ]

    result = run_backtest_with_candles(request, candles)

    buy_trades = [trade for trade in result.trades if trade.side == "BUY"]
    assert len(buy_trades) == 2
    assert buy_trades[1].time == "2026-01-01 10:00"
    assert result.trades[1].side == "SELL"
    assert result.trades[1].reason == "止损触发"
    assert result.trades[1].price == 9.699
    assert result.summary.maxDrawdownPercent > 0
    cooldown_items = [item for item in result.timeline if item.event_type == "COOLDOWN_STARTED"]
    assert len(cooldown_items) == 1
    assert cooldown_items[0].title == "进入冷却"
    assert cooldown_items[0].description == "止损后冷却"
    assert cooldown_items[0].node_label == "冷却"
    assert cooldown_items[0].details == {"durationBars": 2, "reason": "止损后冷却"}


def test_engine_uses_and_logic_before_buying():
    request = _request(
        [
            {
                "id": "price-change-1",
                "type": "price-change",
                "label": "N根收益率",
                "x": 0,
                "y": 0,
                "params": {"lookbackBars": "1", "comparator": ">=", "changePercent": "5"},
            },
            {
                "id": "time-window-1",
                "type": "time-window",
                "label": "交易时段",
                "x": 160,
                "y": 0,
                "params": {"startTime": "09:45", "endTime": "09:45"},
            },
            {
                "id": "and-1",
                "type": "and",
                "label": "与",
                "x": 320,
                "y": 0,
                "params": {},
            },
            {
                "id": "buy-1",
                "type": "buy",
                "label": "买入",
                "x": 480,
                "y": 0,
                "params": {"sizePercent": "100", "orderType": "market"},
            },
        ],
        edges=[
            {"id": "signal-and", "from": "price-change-1", "to": "and-1"},
            {"id": "time-and", "from": "time-window-1", "to": "and-1"},
            {"id": "and-buy", "from": "and-1", "to": "buy-1"},
        ],
    )
    candles = [
        MarketCandle(time="2026-01-01 09:35", close=10.0),
        MarketCandle(time="2026-01-01 09:40", close=10.2),
        MarketCandle(time="2026-01-01 09:45", close=10.8),
        MarketCandle(time="2026-01-01 09:50", open=10.9, close=10.9),
    ]

    result = run_backtest_with_candles(request, candles)

    assert result.trades[0].side == "BUY"
    assert result.trades[0].time == "2026-01-01 09:50"
    assert result.trades[0].price == 10.9011


def test_engine_uses_or_logic_before_buying():
    request = _request(
        [
            {
                "id": "current-price-1",
                "type": "current-price",
                "label": "当前价",
                "x": 0,
                "y": 0,
                "params": {"comparator": "<=", "price": "9"},
            },
            {
                "id": "price-change-1",
                "type": "price-change",
                "label": "N根收益率",
                "x": 0,
                "y": 72,
                "params": {"lookbackBars": "1", "comparator": ">=", "changePercent": "5"},
            },
            {
                "id": "or-1",
                "type": "or",
                "label": "或",
                "x": 180,
                "y": 36,
                "params": {},
            },
            {
                "id": "buy-1",
                "type": "buy",
                "label": "买入",
                "x": 340,
                "y": 36,
                "params": {"sizePercent": "100", "orderType": "market"},
            },
        ],
        edges=[
            {"id": "current-or", "from": "current-price-1", "to": "or-1"},
            {"id": "change-or", "from": "price-change-1", "to": "or-1"},
            {"id": "or-buy", "from": "or-1", "to": "buy-1"},
        ],
    )
    candles = [
        MarketCandle(time="2026-01-01 09:35", close=10.0),
        MarketCandle(time="2026-01-01 09:40", close=10.2),
        MarketCandle(time="2026-01-01 09:45", close=10.8),
        MarketCandle(time="2026-01-01 09:50", open=10.9, close=10.9),
    ]

    result = run_backtest_with_candles(request, candles)

    assert result.trades[0].side == "BUY"
    assert result.trades[0].time == "2026-01-01 09:50"
    assert result.trades[0].price == 10.9011


def test_engine_uses_not_logic_before_buying():
    request = _request(
        [
            {
                "id": "current-price-1",
                "type": "current-price",
                "label": "当前价",
                "x": 0,
                "y": 0,
                "params": {"comparator": "<=", "price": "10.1"},
            },
            {
                "id": "not-1",
                "type": "not",
                "label": "非",
                "x": 160,
                "y": 0,
                "params": {},
            },
            {
                "id": "buy-1",
                "type": "buy",
                "label": "买入",
                "x": 320,
                "y": 0,
                "params": {"sizePercent": "100", "orderType": "market"},
            },
        ],
        edges=[
            {"id": "price-not", "from": "current-price-1", "to": "not-1"},
            {"id": "not-buy", "from": "not-1", "to": "buy-1"},
        ],
    )
    candles = [
        MarketCandle(time="2026-01-01 09:35", close=10.0),
        MarketCandle(time="2026-01-01 09:40", close=10.2),
        MarketCandle(time="2026-01-01 09:45", open=10.3, close=10.3),
    ]

    result = run_backtest_with_candles(request, candles)

    assert result.trades[0].side == "BUY"
    assert result.trades[0].time == "2026-01-01 09:45"
    assert result.trades[0].price == 10.301


def test_engine_uses_rsi_condition_before_buying():
    request = _request(
        [
            {
                "id": "rsi-1",
                "type": "rsi",
                "label": "RSI",
                "x": 0,
                "y": 0,
                "params": {"period": "3", "comparator": "<=", "value": "30"},
            },
            {
                "id": "buy-1",
                "type": "buy",
                "label": "买入",
                "x": 160,
                "y": 0,
                "params": {"sizePercent": "100", "orderType": "market"},
            },
        ],
        edges=[{"id": "rsi-buy", "from": "rsi-1", "to": "buy-1"}],
    )
    candles = [
        MarketCandle(time="2026-01-01 09:35", close=10.0),
        MarketCandle(time="2026-01-01 09:40", close=9.5),
        MarketCandle(time="2026-01-01 09:45", close=9.0),
        MarketCandle(time="2026-01-01 09:50", close=8.5),
        MarketCandle(time="2026-01-01 09:55", open=8.6, close=8.7),
    ]

    result = run_backtest_with_candles(request, candles)

    assert result.trades[0].side == "BUY"
    assert result.trades[0].time == "2026-01-01 09:55"
    assert result.trades[0].price == 8.6009


def test_engine_uses_macd_histogram_condition_before_buying():
    request = _request(
        [
            {
                "id": "macd-1",
                "type": "macd",
                "label": "MACD",
                "x": 0,
                "y": 0,
                "params": {
                    "fastPeriod": "2",
                    "slowPeriod": "3",
                    "signalPeriod": "2",
                    "signal": "histogram-gte",
                    "histogramValue": "0",
                },
            },
            {
                "id": "buy-1",
                "type": "buy",
                "label": "买入",
                "x": 160,
                "y": 0,
                "params": {"sizePercent": "100", "orderType": "market"},
            },
        ],
        edges=[{"id": "macd-buy", "from": "macd-1", "to": "buy-1"}],
    )
    candles = [
        MarketCandle(time="2026-01-01 09:35", close=10.0),
        MarketCandle(time="2026-01-01 09:40", close=10.0),
        MarketCandle(time="2026-01-01 09:45", close=10.0),
        MarketCandle(time="2026-01-01 09:50", close=12.0),
        MarketCandle(time="2026-01-01 09:55", close=14.0),
        MarketCandle(time="2026-01-01 10:00", open=15.0, close=15.0),
    ]

    result = run_backtest_with_candles(request, candles)

    assert result.trades[0].side == "BUY"
    assert result.trades[0].time == "2026-01-01 10:00"
    assert result.trades[0].price == 15.0015


def test_engine_uses_bollinger_band_condition_before_buying():
    request = _request(
        [
            {
                "id": "bollinger-1",
                "type": "bollinger-band",
                "label": "布林带",
                "x": 0,
                "y": 0,
                "params": {"period": "3", "stddev": "1", "relation": "below-lower"},
            },
            {
                "id": "buy-1",
                "type": "buy",
                "label": "买入",
                "x": 160,
                "y": 0,
                "params": {"sizePercent": "100", "orderType": "market"},
            },
        ],
        edges=[{"id": "bollinger-buy", "from": "bollinger-1", "to": "buy-1"}],
    )
    candles = [
        MarketCandle(time="2026-01-01 09:35", close=10.0),
        MarketCandle(time="2026-01-01 09:40", close=10.0),
        MarketCandle(time="2026-01-01 09:45", close=10.0),
        MarketCandle(time="2026-01-01 09:50", close=8.0),
        MarketCandle(time="2026-01-01 09:55", open=8.1, close=8.2),
    ]

    result = run_backtest_with_candles(request, candles)

    assert result.trades[0].side == "BUY"
    assert result.trades[0].time == "2026-01-01 09:55"
    assert result.trades[0].price == 8.1008


def test_engine_uses_vwap_condition_before_buying():
    request = _request(
        [
            {
                "id": "vwap-1",
                "type": "vwap",
                "label": "VWAP",
                "x": 0,
                "y": 0,
                "params": {"period": "2", "relation": "above"},
            },
            {
                "id": "buy-1",
                "type": "buy",
                "label": "买入",
                "x": 160,
                "y": 0,
                "params": {"sizePercent": "100", "orderType": "market"},
            },
        ],
        edges=[{"id": "vwap-buy", "from": "vwap-1", "to": "buy-1"}],
    )
    candles = [
        MarketCandle(time="2026-01-01 09:35", high=10.1, low=9.9, close=10.0, volume=100),
        MarketCandle(time="2026-01-01 09:40", high=11.1, low=10.9, close=11.0, volume=100),
        MarketCandle(time="2026-01-01 09:45", open=11.2, close=11.3, volume=100),
    ]

    result = run_backtest_with_candles(request, candles)

    assert result.trades[0].side == "BUY"
    assert result.trades[0].time == "2026-01-01 09:45"
    assert result.trades[0].price == 11.2011


def test_engine_rebalances_to_target_position_after_price_move():
    request = _request(
        [
            {
                "id": "rebalance-1",
                "type": "rebalance",
                "label": "调仓",
                "x": 0,
                "y": 0,
                "params": {"targetPositionPercent": "80", "orderType": "market"},
            },
        ],
        initial_cash=1000,
    )
    candles = [
        MarketCandle(time="2026-01-01 09:35", close=10.0),
        MarketCandle(time="2026-01-01 09:40", open=10.0, close=20.0),
        MarketCandle(time="2026-01-01 09:45", open=20.0, close=20.0),
    ]

    result = run_backtest_with_candles(request, candles)

    assert [trade.side for trade in result.trades[:2]] == ["BUY", "SELL"]
    assert result.trades[0].reason == "调仓至 80% 仓位"
    assert result.trades[0].quantity == 79
    assert result.trades[1].reason == "调仓至 80% 仓位"
    assert result.trades[1].quantity > 0
    assert result.timeline[0].node_label == "调仓"


def test_engine_applies_moving_stop_after_profit_retraces():
    request = _request(
        [
            {
                "id": "buy-1",
                "type": "buy",
                "label": "买入",
                "x": 0,
                "y": 0,
                "params": {"sizePercent": "100", "orderType": "market"},
            },
            {
                "id": "moving-stop-1",
                "type": "moving-stop",
                "label": "移动止损",
                "x": 160,
                "y": 0,
                "params": {
                    "minProfitPercent": "5",
                    "trailPercent": "5",
                    "sellPercent": "100",
                },
            },
        ]
    )
    candles = [
        MarketCandle(time="2026-01-01 09:35", open=10.0, high=10.1, low=9.9, close=10.0),
        MarketCandle(time="2026-01-01 09:40", open=10.0, high=12.0, low=10.0, close=12.0),
        MarketCandle(time="2026-01-01 09:45", open=11.8, high=11.9, low=11.3, close=11.3),
    ]

    result = run_backtest_with_candles(request, candles)

    assert [trade.side for trade in result.trades] == ["BUY", "SELL"]
    assert result.trades[1].time == "2026-01-01 09:45"
    assert result.trades[1].reason == "移动止损触发"
    assert result.trades[1].price == 11.3989


class StaticMarketDataProvider:
    def __init__(self, candles):
        self.candles = candles
        self.received_config = None

    def get_intraday_candles(self, config):
        self.received_config = config
        return self.candles


def test_run_backtest_uses_injected_market_data_provider():
    request = _request(
        [
            {
                "id": "buy-1",
                "type": "buy",
                "label": "买入",
                "x": 0,
                "y": 0,
                "params": {"sizePercent": "100", "orderType": "market"},
            }
        ]
    )
    provider = StaticMarketDataProvider(
        [
            MarketCandle(time="2026-01-01 09:35", close=10.0),
            MarketCandle(time="2026-01-01 09:40", close=11.0),
        ]
    )

    result = run_backtest(request, market_data_provider=provider)

    assert provider.received_config == request.config
    assert result.trades[0].price == 11.0011
    assert result.trades[-1].price == 10.9989
    assert result.timeline[-1].event_type == "POSITION_CLOSED"
    assert result.timeline[-1].title == "持仓已关闭"
    assert result.timeline[-1].description == "回测结束清仓"
