def test_market_rules_list_includes_a_share_and_us_stock(client):
    response = client.get("/api/market-rules")

    assert response.status_code == 200
    payload = response.json()
    markets = {item["market"]: item for item in payload["items"]}
    assert set(markets) == {"A_SHARE", "US_STOCK"}

    a_share = markets["A_SHARE"]
    assert a_share["marketLabel"] == "A股"
    assert a_share["currency"] == "CNY"
    assert a_share["timezone"] == "Asia/Shanghai"
    assert a_share["buyLotSize"] == 100
    assert a_share["sellLotSize"] == 1
    assert a_share["settlementCycle"] == "T+1"
    assert a_share["supportsIntradayRoundTrip"] is False
    assert a_share["priceLimitPercent"] == 10
    assert a_share["sessions"][0] == {"label": "上午连续竞价", "start": "09:30", "end": "11:30"}

    us_stock = markets["US_STOCK"]
    assert us_stock["marketLabel"] == "美股"
    assert us_stock["currency"] == "USD"
    assert us_stock["timezone"] == "America/New_York"
    assert us_stock["buyLotSize"] == 1
    assert us_stock["sellLotSize"] == 1
    assert us_stock["settlementCycle"] == "T+1"
    assert us_stock["supportsIntradayRoundTrip"] is True
    assert us_stock["priceLimitPercent"] is None


def test_market_rule_detail_returns_single_market_rule(client):
    response = client.get("/api/market-rules/A_SHARE")

    assert response.status_code == 200
    payload = response.json()
    assert payload["market"] == "A_SHARE"
    assert payload["marketLabel"] == "A股"
    assert any("买入委托数量按 100 股整数倍处理" in note for note in payload["notes"])


def test_market_rule_detail_rejects_unknown_market(client):
    response = client.get("/api/market-rules/CRYPTO")

    assert response.status_code == 404
    assert response.json()["detail"] == "Market rule not found"
