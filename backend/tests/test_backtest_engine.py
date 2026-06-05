from app.schemas.backtest import BacktestRunRequest
from app.services.backtest_service import (
    MarketCandle,
    run_backtest,
    run_backtest_with_candles,
)


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
        MarketCandle(time="2026-01-01 09:35", close=10.0),
        MarketCandle(time="2026-01-01 09:40", close=10.6),
    ]

    result = run_backtest_with_candles(request, candles)

    assert [trade.side for trade in result.trades] == ["BUY", "SELL"]
    assert result.trades[0].quantity == 50
    assert result.trades[1].reason == "止盈触发"
    assert result.summary.endingEquity == 1030
    assert result.summary.totalReturnPercent == 3.0
    assert result.summary.maxDrawdownPercent == 0
    assert result.summary.winRatePercent == 100
    assert result.equityCurve[-1].equity == 1030


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
        MarketCandle(time="2026-01-01 09:35", close=10.0),
        MarketCandle(time="2026-01-01 09:40", close=9.6),
        MarketCandle(time="2026-01-01 09:45", close=9.7),
        MarketCandle(time="2026-01-01 09:50", close=9.8),
        MarketCandle(time="2026-01-01 09:55", close=10.0),
    ]

    result = run_backtest_with_candles(request, candles)

    buy_trades = [trade for trade in result.trades if trade.side == "BUY"]
    assert len(buy_trades) == 2
    assert buy_trades[1].time == "2026-01-01 09:55"
    assert result.trades[1].side == "SELL"
    assert result.trades[1].reason == "止损触发"
    assert result.summary.maxDrawdownPercent > 0


def test_engine_uses_connected_conditions_before_buying():
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
                "id": "if-1",
                "type": "if",
                "label": "如果",
                "x": 160,
                "y": 0,
                "params": {"mode": "all"},
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
            {"id": "signal-if", "from": "price-change-1", "to": "if-1"},
            {"id": "if-buy", "from": "if-1", "to": "buy-1"},
        ],
    )
    candles = [
        MarketCandle(time="2026-01-01 09:35", close=10.0),
        MarketCandle(time="2026-01-01 09:40", close=10.2),
        MarketCandle(time="2026-01-01 09:45", close=10.8),
    ]

    result = run_backtest_with_candles(request, candles)

    assert result.trades[0].side == "BUY"
    assert result.trades[0].time == "2026-01-01 09:45"
    assert result.trades[0].price == 10.8


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
        MarketCandle(time="2026-01-01 09:35", close=10.0),
        MarketCandle(time="2026-01-01 09:40", close=12.0),
        MarketCandle(time="2026-01-01 09:45", close=11.3),
    ]

    result = run_backtest_with_candles(request, candles)

    assert [trade.side for trade in result.trades] == ["BUY", "SELL"]
    assert result.trades[1].time == "2026-01-01 09:45"
    assert result.trades[1].reason == "移动止损触发"


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
    assert result.trades[0].price == 10
    assert result.trades[-1].price == 11
