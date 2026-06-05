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


def strategy_payload(name: str = "五分钟突破策略") -> dict:
    return {
        "name": name,
        "description": "买入后按规则退出",
        "strategy": {
            "version": 1,
            "nodes": [
                {
                    "id": "buy-1",
                    "type": "buy",
                    "label": "买入",
                    "x": 72,
                    "y": 96,
                    "params": {"sizePercent": "20", "orderType": "market"},
                }
            ],
            "edges": [],
            "viewport": {"x": 0, "y": 0, "scale": 1},
        },
        "backtestConfig": {
            "market": "A_SHARE",
            "symbol": "000001.SZ",
            "timeframe": "5m",
            "startDate": "2026-01-01",
            "endDate": "2026-03-01",
            "initialCash": 100000,
        },
    }


def test_strategy_crud_flow_for_current_user(client):
    token = register_and_token(client, "alice", "alice@example.com")

    create_response = client.post(
        "/api/strategies",
        json=strategy_payload(),
        headers=auth_headers(token),
    )

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["id"]
    assert created["name"] == "五分钟突破策略"
    assert created["strategy"]["nodes"][0]["type"] == "buy"
    assert created["backtestConfig"]["symbol"] == "000001.SZ"

    list_response = client.get(
        "/api/strategies?keyword=突破&page=1&pageSize=10",
        headers=auth_headers(token),
    )

    assert list_response.status_code == 200
    listed = list_response.json()
    assert listed["total"] == 1
    assert listed["items"][0]["id"] == created["id"]

    detail_response = client.get(
        f"/api/strategies/{created['id']}",
        headers=auth_headers(token),
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["strategy"]["nodes"][0]["params"]["sizePercent"] == "20"

    update_payload = strategy_payload("五分钟突破策略 v2")
    update_payload["strategy"]["nodes"][0]["params"]["sizePercent"] = "35"
    update_response = client.put(
        f"/api/strategies/{created['id']}",
        json=update_payload,
        headers=auth_headers(token),
    )

    assert update_response.status_code == 200
    assert update_response.json()["name"] == "五分钟突破策略 v2"
    assert update_response.json()["strategy"]["nodes"][0]["params"]["sizePercent"] == "35"

    delete_response = client.delete(
        f"/api/strategies/{created['id']}",
        headers=auth_headers(token),
    )
    assert delete_response.status_code == 204

    missing_response = client.get(
        f"/api/strategies/{created['id']}",
        headers=auth_headers(token),
    )
    assert missing_response.status_code == 404


def test_strategy_requires_login(client):
    response = client.post("/api/strategies", json=strategy_payload())

    assert response.status_code == 401


def test_strategy_list_only_returns_current_users_items(client):
    alice_token = register_and_token(client, "alice", "alice@example.com")
    bob_token = register_and_token(client, "bob", "bob@example.com")

    alice_create = client.post(
        "/api/strategies",
        json=strategy_payload("Alice 策略"),
        headers=auth_headers(alice_token),
    )
    assert alice_create.status_code == 201
    bob_create = client.post(
        "/api/strategies",
        json=strategy_payload("Bob 策略"),
        headers=auth_headers(bob_token),
    )
    assert bob_create.status_code == 201

    alice_list = client.get("/api/strategies", headers=auth_headers(alice_token)).json()
    bob_list = client.get("/api/strategies", headers=auth_headers(bob_token)).json()

    assert [item["name"] for item in alice_list["items"]] == ["Alice 策略"]
    assert [item["name"] for item in bob_list["items"]] == ["Bob 策略"]

    bob_reads_alice = client.get(
        f"/api/strategies/{alice_create.json()['id']}",
        headers=auth_headers(bob_token),
    )
    assert bob_reads_alice.status_code == 404
