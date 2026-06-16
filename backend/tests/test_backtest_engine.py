from app.schemas.backtest import BacktestRunRequest
from app.services.backtest_service import (
    MarketCandle,
    run_backtest,
    run_backtest_with_candles,
)
from app.services.market_rule_service import get_market_rule
from app.services.trading_cost_service import calculate_trade_fill, affordable_buy_quantity


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
    assert result.trades[0].quantity == 50
    assert result.trades[1].reason == "止盈触发"
    assert result.summary.endingEquity == 1025
    assert result.summary.totalReturnPercent == 2.5
    assert result.summary.maxDrawdownPercent == 0
    assert result.summary.winRatePercent == 100
    assert result.equityCurve[-1].equity == 1025
    assert [item.event_type for item in result.timeline] == ["TRADE_FILLED", "TRADE_FILLED"]
    assert result.timeline[0].title == "买入成交"
    assert result.timeline[0].description == "买入积木触发"
    assert result.timeline[0].node_label == "买入"
    assert result.timeline[0].price == 10
    assert result.timeline[0].quantity == 50
    assert result.timeline[1].title == "卖出成交"
    assert result.timeline[1].description == "止盈触发"
    assert result.timeline[1].node_label == "止盈"
    assert result.timeline[1].price == 10.5


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
    assert result.trades[0].price == 11.0
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
    assert result.trades[0].price == 10.0
    assert result.trades[1].reason == "止损触发"
    assert result.trades[1].price == 9.5
    assert result.summary.endingEquity == 950


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
    assert result.trades[1].price == 10.5
    assert result.summary.endingEquity == 1050


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
        MarketCandle(time="2026-01-01 09:35", open=10.0, high=10.1, low=9.9, close=10.0),
        MarketCandle(time="2026-01-01 09:40", open=10.0, high=11.0, low=9.9, close=11.0),
        MarketCandle(time="2026-01-02 09:35", open=11.4, high=11.5, low=10.1, close=11.5),
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
    assert result.trades[0].quantity == 1000
    assert result.trades[1].time == "2026-01-02 09:35"
    assert result.trades[1].reason == "止盈触发"
    assert result.trades[1].price == 10.1
    assert result.summary.endingEquity == 10100
    assert result.summary.totalReturnPercent == 1


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
        MarketCandle(time="2026-01-01 09:35", open=10.0, high=10.1, low=9.9, close=10.0),
        MarketCandle(time="2026-01-01 09:40", open=10.0, high=11.0, low=9.9, close=11.0),
    ]

    result = run_backtest_with_candles(request, candles)

    assert [trade.side for trade in result.trades] == ["BUY"]
    assert [event.event_type for event in result.events] == ["BLOCKED_ORDER"]
    assert result.events[0].reason == "A股 T+1 规则限制，当日买入持仓不可卖出"
    assert result.summary.endingEquity == 11000
    assert result.summary.tradeCount == 1
    assert result.equityCurve[-1].equity == 11000


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
    assert result.trades[1].price == 9.7
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
    assert result.trades[0].price == 10.9


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
    assert result.trades[0].price == 10.9


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
    assert result.trades[0].price == 10.3


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
    assert result.trades[1].price == 11.4


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
    assert result.trades[0].price == 11
    assert result.trades[-1].price == 11
    assert result.timeline[-1].event_type == "POSITION_CLOSED"
    assert result.timeline[-1].title == "持仓已关闭"
    assert result.timeline[-1].description == "回测结束清仓"
