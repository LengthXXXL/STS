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


def account_payload(name: str = "A股日内账户") -> dict:
    return {
        "name": name,
        "description": "用于回测账户选择",
        "market": "A_SHARE",
        "initialCash": 100000,
    }


def test_run_backtest_returns_computed_metrics_and_trade_path(client):
    response = client.post("/api/backtests/run", json=_backtest_payload())

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["totalReturnPercent"] > 0
    assert payload["summary"]["maxDrawdownPercent"] >= 0
    assert payload["summary"]["winRatePercent"] == 0
    assert payload["summary"]["endingEquity"] > 100000
    assert payload["summary"]["tradeCount"] == len(payload["trades"])
    assert payload["config"]["symbol"] == "000001.SZ"
    assert payload["runId"] == "engine-000001.SZ-5m"
    assert [trade["side"] for trade in payload["trades"]] == ["BUY"]
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


def test_list_backtests_only_returns_current_user_records(client):
    alice_token = register_and_token(client, "alice-backtest", "alice-backtest@example.com")
    bob_token = register_and_token(client, "bob-backtest", "bob-backtest@example.com")

    alice_response = client.post(
        "/api/backtests/run",
        json=_backtest_payload(),
        headers=auth_headers(alice_token),
    )
    assert alice_response.status_code == 200

    bob_payload = _backtest_payload()
    bob_payload["config"]["symbol"] = "600000.SH"
    bob_response = client.post(
        "/api/backtests/run",
        json=bob_payload,
        headers=auth_headers(bob_token),
    )
    assert bob_response.status_code == 200

    alice_list = client.get(
        "/api/backtests?keyword=000001&page=1&pageSize=10",
        headers=auth_headers(alice_token),
    )
    bob_list = client.get("/api/backtests", headers=auth_headers(bob_token))

    assert alice_list.status_code == 200
    assert bob_list.status_code == 200
    assert alice_list.json()["total"] == 1
    assert alice_list.json()["items"][0]["symbol"] == "000001.SZ"
    assert bob_list.json()["total"] == 1
    assert bob_list.json()["items"][0]["symbol"] == "600000.SH"


def test_backtest_detail_requires_owner(client):
    alice_token = register_and_token(client, "alice-detail", "alice-detail@example.com")
    bob_token = register_and_token(client, "bob-detail", "bob-detail@example.com")

    response = client.post(
        "/api/backtests/run",
        json=_backtest_payload(),
        headers=auth_headers(alice_token),
    )
    assert response.status_code == 200

    alice_list = client.get("/api/backtests", headers=auth_headers(alice_token))
    assert alice_list.status_code == 200
    task_id = alice_list.json()["items"][0]["id"]

    alice_detail = client.get(f"/api/backtests/{task_id}", headers=auth_headers(alice_token))
    bob_detail = client.get(f"/api/backtests/{task_id}", headers=auth_headers(bob_token))

    assert alice_detail.status_code == 200
    detail = alice_detail.json()
    assert detail["id"] == task_id
    assert detail["config"]["symbol"] == "000001.SZ"
    assert detail["summary"]["tradeCount"] == len(detail["trades"])
    assert detail["equityCurve"][-1]["equity"] == detail["summary"]["endingEquity"]
    assert bob_detail.status_code == 404


def test_run_backtest_uses_owned_simulation_account_settings(client):
    token = register_and_token(client, "account-runner", "account-runner@example.com")
    account_response = client.post(
        "/api/simulation-accounts",
        json={**account_payload("美股一分钟账户"), "market": "US_STOCK", "initialCash": 50000},
        headers=auth_headers(token),
    )
    assert account_response.status_code == 201

    payload = _backtest_payload()
    payload["config"]["market"] = "A_SHARE"
    payload["config"]["symbol"] = "AAPL"
    payload["config"]["initialCash"] = 100000
    payload["config"]["simulationAccountId"] = account_response.json()["id"]

    response = client.post(
        "/api/backtests/run",
        json=payload,
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    config = response.json()["config"]
    assert config["market"] == "US_STOCK"
    assert config["initialCash"] == 50000
    assert config["simulationAccountId"] == account_response.json()["id"]

    records = client.get("/api/backtests", headers=auth_headers(token))
    assert records.status_code == 200
    listed_record = records.json()["items"][0]
    assert listed_record["simulationAccountId"] == account_response.json()["id"]
    assert listed_record["simulationAccountName"] == "美股一分钟账户"

    detail = client.get(f"/api/backtests/{listed_record['id']}", headers=auth_headers(token))
    assert detail.status_code == 200
    assert detail.json()["simulationAccountId"] == account_response.json()["id"]
    assert detail.json()["simulationAccountName"] == "美股一分钟账户"


def test_run_backtest_rejects_other_users_simulation_account(client):
    alice_token = register_and_token(client, "account-owner", "account-owner@example.com")
    bob_token = register_and_token(client, "account-intruder", "account-intruder@example.com")
    account_response = client.post(
        "/api/simulation-accounts",
        json=account_payload(),
        headers=auth_headers(alice_token),
    )
    assert account_response.status_code == 201

    payload = _backtest_payload()
    payload["config"]["simulationAccountId"] = account_response.json()["id"]

    response = client.post(
        "/api/backtests/run",
        json=payload,
        headers=auth_headers(bob_token),
    )

    assert response.status_code == 404
