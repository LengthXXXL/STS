from tests.test_strategies import auth_headers, register_and_token, strategy_payload


def custom_block_payload(name: str = "突破后止盈模板") -> dict:
    strategy = strategy_payload()["strategy"]
    strategy["nodes"].append(
        {
            "id": "take-profit-1",
            "type": "take-profit",
            "label": "止盈",
            "x": 220,
            "y": 96,
            "params": {"profitRate": "5", "sellPercent": "50"},
        }
    )
    strategy["edges"] = [{"id": "edge-1", "from": "buy-1", "to": "take-profit-1"}]
    return {
        "name": name,
        "description": "买入后按收益目标退出的一组模板积木",
        "category": "风控",
        "tags": ["止盈", "模板"],
        "template": strategy,
    }


def test_custom_block_crud_flow_for_current_user(client):
    token = register_and_token(client, "alice", "alice@example.com")

    create_response = client.post(
        "/api/custom-blocks",
        json=custom_block_payload(),
        headers=auth_headers(token),
    )

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["id"]
    assert created["name"] == "突破后止盈模板"
    assert created["reviewStatus"] == "private"
    assert created["template"]["nodes"][1]["type"] == "take-profit"
    assert created["tags"] == ["止盈", "模板"]

    list_response = client.get(
        "/api/custom-blocks?keyword=止盈&page=1&pageSize=10",
        headers=auth_headers(token),
    )

    assert list_response.status_code == 200
    listed = list_response.json()
    assert listed["total"] == 1
    assert listed["items"][0]["id"] == created["id"]

    detail_response = client.get(
        f"/api/custom-blocks/{created['id']}",
        headers=auth_headers(token),
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["template"]["edges"][0]["from"] == "buy-1"

    update_payload = custom_block_payload("突破后止盈模板 v2")
    update_payload["tags"] = ["止盈", "复盘"]
    update_response = client.put(
        f"/api/custom-blocks/{created['id']}",
        json=update_payload,
        headers=auth_headers(token),
    )

    assert update_response.status_code == 200
    assert update_response.json()["name"] == "突破后止盈模板 v2"
    assert update_response.json()["tags"] == ["止盈", "复盘"]

    delete_response = client.delete(
        f"/api/custom-blocks/{created['id']}",
        headers=auth_headers(token),
    )
    assert delete_response.status_code == 204

    missing_response = client.get(
        f"/api/custom-blocks/{created['id']}",
        headers=auth_headers(token),
    )
    assert missing_response.status_code == 404


def test_custom_block_requires_login(client):
    response = client.post("/api/custom-blocks", json=custom_block_payload())

    assert response.status_code == 401


def test_custom_block_list_only_returns_current_users_items(client):
    alice_token = register_and_token(client, "alice", "alice@example.com")
    bob_token = register_and_token(client, "bob", "bob@example.com")

    alice_create = client.post(
        "/api/custom-blocks",
        json=custom_block_payload("Alice 模板"),
        headers=auth_headers(alice_token),
    )
    assert alice_create.status_code == 201
    bob_create = client.post(
        "/api/custom-blocks",
        json=custom_block_payload("Bob 模板"),
        headers=auth_headers(bob_token),
    )
    assert bob_create.status_code == 201

    alice_list = client.get("/api/custom-blocks", headers=auth_headers(alice_token)).json()
    bob_list = client.get("/api/custom-blocks", headers=auth_headers(bob_token)).json()

    assert [item["name"] for item in alice_list["items"]] == ["Alice 模板"]
    assert [item["name"] for item in bob_list["items"]] == ["Bob 模板"]

    bob_reads_alice = client.get(
        f"/api/custom-blocks/{alice_create.json()['id']}",
        headers=auth_headers(bob_token),
    )
    assert bob_reads_alice.status_code == 404
