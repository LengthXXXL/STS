from sqlalchemy import select

from app.models import (
    BacktestEquityPointRecord,
    BacktestTask,
    BacktestTradeRecord,
    MarketKlineCache,
)


def register_and_token(client, username: str, email: str) -> str:
    response = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "email": email,
            "password": "StrongerPass123",
        },
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


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


def test_run_backtest_persists_owned_task_trades_and_equity_curve(client, db_session):
    token = register_and_token(client, "backtester", "backtester@example.com")

    response = client.post(
        "/api/backtests/run",
        json=_backtest_payload(),
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    payload = response.json()
    task = db_session.scalar(select(BacktestTask).where(BacktestTask.run_id == payload["runId"]))
    assert task is not None
    assert task.owner_id is not None
    assert task.market == "A_SHARE"
    assert task.symbol == "000001.SZ"
    assert task.timeframe == "5m"
    assert task.strategy["nodes"][0]["type"] == "buy"
    assert task.config["initialCash"] == 100000
    assert task.total_return_percent == payload["summary"]["totalReturnPercent"]
    assert task.max_drawdown_percent == payload["summary"]["maxDrawdownPercent"]
    assert task.win_rate_percent == payload["summary"]["winRatePercent"]
    assert task.ending_equity == payload["summary"]["endingEquity"]
    assert task.trade_count == payload["summary"]["tradeCount"]

    trades = db_session.scalars(
        select(BacktestTradeRecord)
        .where(BacktestTradeRecord.task_id == task.id)
        .order_by(BacktestTradeRecord.sequence)
    ).all()
    equity_points = db_session.scalars(
        select(BacktestEquityPointRecord)
        .where(BacktestEquityPointRecord.task_id == task.id)
        .order_by(BacktestEquityPointRecord.sequence)
    ).all()

    assert len(trades) == len(payload["trades"])
    assert trades[0].side == payload["trades"][0]["side"]
    assert trades[0].price == payload["trades"][0]["price"]
    assert len(equity_points) == len(payload["equityCurve"])
    assert equity_points[-1].equity == payload["equityCurve"][-1]["equity"]
