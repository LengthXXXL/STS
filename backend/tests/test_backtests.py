from sqlalchemy import select

from app.models import MarketKlineCache


def _backtest_payload():
    return {
        "strategy": {
            "version": 1,
            "nodes": [
                {
                    "id": "buy-1",
                    "type": "buy",
                    "label": "买入",
                    "x": 120,
                    "y": 96,
                    "params": {"sizePercent": "20", "orderType": "market"},
                }
            ],
            "edges": [],
            "viewport": {"x": 0, "y": 0, "scale": 1},
        },
        "config": {
            "market": "A_SHARE",
            "symbol": "000001.SZ",
            "timeframe": "5m",
            "startDate": "2026-01-01",
            "endDate": "2026-03-01",
            "initialCash": 100000,
        },
    }


def test_run_backtest_returns_computed_metrics_and_trade_path(client):
    response = client.post("/api/backtests/run", json=_backtest_payload())

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["totalReturnPercent"] > 0
    assert payload["summary"]["maxDrawdownPercent"] >= 0
    assert payload["summary"]["winRatePercent"] == 100
    assert payload["summary"]["endingEquity"] > 100000
    assert payload["summary"]["tradeCount"] == len(payload["trades"])
    assert payload["config"]["symbol"] == "000001.SZ"
    assert payload["runId"] == "engine-000001.SZ-5m"
    assert payload["trades"][0]["side"] == "BUY"
    assert payload["trades"][0]["price"] > 0
    assert payload["equityCurve"][0]["equity"] == 100000
    assert payload["equityCurve"][-1]["equity"] == payload["summary"]["endingEquity"]


def test_run_backtest_rejects_empty_strategy(client):
    payload = _backtest_payload()
    payload["strategy"]["nodes"] = []

    response = client.post("/api/backtests/run", json=payload)

    assert response.status_code == 400
    assert response.json()["detail"] == "Strategy must contain at least one node"


def test_run_backtest_caches_market_data_rows(client, db_session):
    response = client.post("/api/backtests/run", json=_backtest_payload())

    assert response.status_code == 200
    cached_rows = db_session.scalars(
        select(MarketKlineCache)
        .where(MarketKlineCache.market == "A_SHARE")
        .where(MarketKlineCache.symbol == "000001.SZ")
        .where(MarketKlineCache.timeframe == "5m")
        .order_by(MarketKlineCache.candle_time)
    ).all()
    assert cached_rows
    assert cached_rows[0].candle_time.startswith("2026-")
    assert cached_rows[0].close > 0
