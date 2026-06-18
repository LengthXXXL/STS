from io import BytesIO
from zipfile import ZipFile

import pytest
from sqlalchemy import select

from app.api import backtests as backtests_api
from app.models import (
    BacktestEquityPointRecord,
    BacktestTask,
    BacktestTimelineRecord,
    BacktestTradeRecord,
    MarketDataDownloadRange,
    MarketKlineCache,
    UploadedFile,
)
from app.services.market_data_service import MarketDataUnavailableError


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
                },
                {
                    "id": "take-profit-1",
                    "type": "take-profit",
                    "label": "止盈",
                    "x": 280,
                    "y": 96,
                    "params": {"profitRate": "1", "sellPercent": "100"},
                }
            ],
            "edges": [],
            "viewport": {"x": 0, "y": 0, "scale": 1},
        },
        "config": {
            "market": "A_SHARE",
            "symbol": "000001.SZ",
            "timeframe": "5m",
            "startDate": "2026-01-05",
            "endDate": "2026-01-05",
            "initialCash": 100000,
        },
    }


def _seed_market_cache(
    db_session,
    *,
    market: str = "A_SHARE",
    symbol: str = "000001.SZ",
    timeframe: str = "5m",
) -> None:
    base_price = 10.2 if market == "A_SHARE" else 186.4
    candle_times = [
        "2026-01-05 09:35",
        "2026-01-05 09:40",
        "2026-01-05 09:45",
        "2026-01-05 09:50",
        "2026-01-05 09:55",
        "2026-01-05 10:00",
    ]
    open_factors = [1, 1, 1.025, 0.992, 1.055, 1.038]
    for index, factor in enumerate([1, 1.025, 0.992, 1.055, 1.038, 1.073]):
        close = round(base_price * factor, 4)
        db_session.add(
            MarketKlineCache(
                market=market,
                symbol=symbol,
                timeframe=timeframe,
                source="LIVE",
                candle_time=candle_times[index],
                open_price=round(base_price * open_factors[index], 4),
                high_price=round(close * 1.004, 4),
                low_price=round(close * 0.996, 4),
                close=close,
                volume=1000 + index * 120,
                previous_close=base_price,
            )
        )
    db_session.add(
        MarketDataDownloadRange(
            market=market,
            symbol=symbol,
            timeframe=timeframe,
            start_date="2026-01-05",
            end_date="2026-01-05",
            status="completed",
            row_count=len(candle_times),
            source="LIVE",
        )
    )
    db_session.commit()


def account_payload(name: str = "A股日内账户") -> dict:
    return {
        "name": name,
        "description": "用于回测账户选择",
        "market": "A_SHARE",
        "initialCash": 100000,
    }


def test_run_backtest_returns_computed_metrics_and_trade_path(client, db_session):
    _seed_market_cache(db_session)

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
    assert payload["events"]
    assert {event["eventType"] for event in payload["events"]} == {"BLOCKED_ORDER"}
    assert payload["events"][0]["side"] == "SELL"
    assert payload["events"][0]["rule"] == "T+1"
    assert payload["events"][0]["reason"] == "A股 T+1 规则限制，当日买入持仓不可卖出"
    assert payload["timeline"]
    assert payload["timeline"][0]["eventType"] == "TRADE_FILLED"
    assert payload["timeline"][0]["title"] == "买入成交"
    assert any(item["eventType"] == "ORDER_BLOCKED" for item in payload["timeline"])
    assert payload["trades"][0]["price"] > 0
    assert payload["equityCurve"][0]["equity"] == 100000
    assert payload["equityCurve"][-1]["equity"] == payload["summary"]["endingEquity"]


def test_run_backtest_rejects_empty_strategy(client):
    payload = _backtest_payload()
    payload["strategy"]["nodes"] = []

    response = client.post("/api/backtests/run", json=payload)

    assert response.status_code == 400
    assert response.json()["detail"] == "Strategy must contain at least one node"


def test_run_backtest_rejects_unprepared_local_market_data(client):
    response = client.post("/api/backtests/run", json=_backtest_payload())

    assert response.status_code == 422
    assert response.json()["detail"] == "本地行情尚未准备完成，请先下载行情后再运行回测"


def test_run_backtest_rejects_range_without_trading_days(client):
    payload = _backtest_payload()
    payload["config"]["startDate"] = "2026-02-15"
    payload["config"]["endDate"] = "2026-02-23"

    response = client.post("/api/backtests/run", json=payload)

    assert response.status_code == 422
    assert response.json()["detail"] == "该时间段没有交易日，请选择包含交易日的回测区间"


@pytest.mark.parametrize(
    ("start_date", "end_date"),
    [
        ("not-a-date", "2026-03-01"),
        ("2026-03-02", "2026-03-01"),
        ("2025-01-01", "2026-02-02"),
    ],
)
def test_run_backtest_rejects_invalid_date_range_with_422(client, start_date, end_date):
    payload = _backtest_payload()
    payload["config"]["startDate"] = start_date
    payload["config"]["endDate"] = end_date

    response = client.post("/api/backtests/run", json=payload)

    assert response.status_code == 422
    assert response.json()["detail"] != "Internal Server Error"


def test_run_backtest_reports_local_data_provider_failure(client, db_session, monkeypatch):
    _seed_market_cache(db_session)

    class FailingLocalProvider:
        def __init__(self, db):
            pass

        def get_intraday_candles(self, config):
            raise MarketDataUnavailableError("local cache missing")

    monkeypatch.setattr(backtests_api, "LocalOnlyMarketDataProvider", FailingLocalProvider)

    response = client.post("/api/backtests/run", json=_backtest_payload())

    assert response.status_code == 422
    assert response.json()["detail"] == "本地行情尚未准备完成，请先下载行情后再运行回测"


def test_run_backtest_caches_market_data_rows(client, db_session):
    _seed_market_cache(db_session)

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
    _seed_market_cache(db_session)

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
    timeline_items = db_session.scalars(
        select(BacktestTimelineRecord)
        .where(BacktestTimelineRecord.task_id == task.id)
        .order_by(BacktestTimelineRecord.sequence)
    ).all()

    assert len(trades) == len(payload["trades"])
    assert trades[0].side == payload["trades"][0]["side"]
    assert trades[0].price == payload["trades"][0]["price"]
    assert trades[0].gross_amount == payload["trades"][0]["grossAmount"]
    assert trades[0].cost_amount == payload["trades"][0]["costAmount"]
    assert trades[0].slippage_amount == payload["trades"][0]["slippageAmount"]
    assert trades[0].net_cash_change == payload["trades"][0]["netCashChange"]
    assert trades[0].cost_breakdown == payload["trades"][0]["costBreakdown"]
    assert len(equity_points) == len(payload["equityCurve"])
    assert equity_points[-1].equity == payload["equityCurve"][-1]["equity"]
    assert len(timeline_items) == len(payload["timeline"])
    assert timeline_items[0].event_type == payload["timeline"][0]["eventType"]
    assert timeline_items[0].title == payload["timeline"][0]["title"]

    detail = client.get(f"/api/backtests/{task.id}", headers=auth_headers(token))
    assert detail.status_code == 200
    detail_payload = detail.json()
    assert detail_payload["events"] == payload["events"]
    assert detail_payload["timeline"] == payload["timeline"]
    assert detail_payload["trades"][0]["grossAmount"] == payload["trades"][0]["grossAmount"]
    assert detail_payload["trades"][0]["costAmount"] == payload["trades"][0]["costAmount"]
    assert detail_payload["trades"][0]["slippageAmount"] == payload["trades"][0]["slippageAmount"]
    assert detail_payload["trades"][0]["netCashChange"] == payload["trades"][0]["netCashChange"]
    assert detail_payload["trades"][0]["costBreakdown"] == payload["trades"][0]["costBreakdown"]


def test_export_backtest_report_creates_private_xlsx_file(client, db_session):
    _seed_market_cache(db_session)

    alice_token = register_and_token(client, "report-owner", "report-owner@example.com")
    bob_token = register_and_token(client, "report-intruder", "report-intruder@example.com")

    run_response = client.post(
        "/api/backtests/run",
        json=_backtest_payload(),
        headers=auth_headers(alice_token),
    )
    assert run_response.status_code == 200

    backtest_list = client.get("/api/backtests", headers=auth_headers(alice_token))
    assert backtest_list.status_code == 200
    task_id = backtest_list.json()["items"][0]["id"]

    export_response = client.post(
        f"/api/backtests/{task_id}/export",
        headers=auth_headers(alice_token),
    )
    bob_export = client.post(
        f"/api/backtests/{task_id}/export",
        headers=auth_headers(bob_token),
    )

    assert export_response.status_code == 201
    assert bob_export.status_code == 404
    exported = export_response.json()
    assert exported["originalName"].startswith("回测报告_000001.SZ_5m_")
    assert exported["originalName"].endswith(f"_{task_id}.xlsx")
    assert exported["contentType"] == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert exported["businessType"] == "backtest"
    assert exported["businessId"] == task_id
    assert exported["visibility"] == "private"
    assert exported["downloadUrl"] == f"/api/files/{exported['id']}/download"

    stored_file = db_session.scalar(select(UploadedFile).where(UploadedFile.id == exported["id"]))
    assert stored_file is not None
    assert stored_file.business_type == "backtest"
    assert stored_file.business_id == task_id

    file_list = client.get("/api/files?keyword=回测报告", headers=auth_headers(alice_token))
    assert file_list.status_code == 200
    assert file_list.json()["total"] == 1

    download_response = client.get(
        f"/api/files/{exported['id']}/download",
        headers=auth_headers(alice_token),
    )
    assert download_response.status_code == 200
    assert ".xlsx" in download_response.headers["content-disposition"]

    with ZipFile(BytesIO(download_response.content)) as workbook:
        names = set(workbook.namelist())
        assert "xl/workbook.xml" in names
        assert "xl/worksheets/sheet1.xml" in names
        assert "xl/worksheets/sheet2.xml" in names
        root_rels_xml = workbook.read("_rels/.rels").decode()
        workbook_xml = workbook.read("xl/workbook.xml").decode()
        summary_sheet = workbook.read("xl/worksheets/sheet1.xml").decode()
        trades_sheet = workbook.read("xl/worksheets/sheet2.xml").decode()

    assert "relationships/officeDocument" in root_rels_xml
    assert "STS 回测报告" in summary_sheet
    assert "000001.SZ" in summary_sheet
    assert "交易明细" in workbook_xml
    assert "BUY" in trades_sheet


def test_list_backtests_only_returns_current_user_records(client, db_session):
    _seed_market_cache(db_session, symbol="000001.SZ")
    _seed_market_cache(db_session, symbol="600000.SH")

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


def test_backtest_detail_requires_owner(client, db_session):
    _seed_market_cache(db_session)

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


def test_run_backtest_uses_owned_simulation_account_settings(client, db_session):
    _seed_market_cache(db_session, market="US_STOCK", symbol="AAPL")

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
