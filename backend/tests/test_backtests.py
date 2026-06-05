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


def test_run_backtest_returns_mock_metrics_and_trade_path(client):
    response = client.post("/api/backtests/run", json=_backtest_payload())

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"] == {
        "totalReturnPercent": 7.3,
        "maxDrawdownPercent": 2.8,
        "winRatePercent": 66.7,
        "endingEquity": 107300.0,
        "tradeCount": 3,
    }
    assert payload["config"]["symbol"] == "000001.SZ"
    assert payload["trades"][0]["side"] == "BUY"
    assert payload["trades"][0]["price"] > 0
    assert payload["equityCurve"][0]["equity"] == 100000
    assert payload["equityCurve"][-1]["equity"] == 107300.0


def test_run_backtest_rejects_empty_strategy(client):
    payload = _backtest_payload()
    payload["strategy"]["nodes"] = []

    response = client.post("/api/backtests/run", json=payload)

    assert response.status_code == 400
    assert response.json()["detail"] == "Strategy must contain at least one node"
