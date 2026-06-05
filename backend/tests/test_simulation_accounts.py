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


def account_payload(name: str = "A股日内账户") -> dict:
    return {
        "name": name,
        "description": "专门用于五分钟策略测试",
        "market": "A_SHARE",
        "initialCash": 100000,
    }


def test_simulation_account_crud_flow_for_current_user(client):
    token = register_and_token(client, "account-alice", "account-alice@example.com")

    create_response = client.post(
        "/api/simulation-accounts",
        json=account_payload(),
        headers=auth_headers(token),
    )

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["id"]
    assert created["name"] == "A股日内账户"
    assert created["market"] == "A_SHARE"
    assert created["initialCash"] == 100000

    list_response = client.get(
        "/api/simulation-accounts?keyword=日内&page=1&pageSize=10",
        headers=auth_headers(token),
    )
    assert list_response.status_code == 200
    listed = list_response.json()
    assert listed["total"] == 1
    assert listed["items"][0]["id"] == created["id"]

    detail_response = client.get(
        f"/api/simulation-accounts/{created['id']}",
        headers=auth_headers(token),
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["description"] == "专门用于五分钟策略测试"

    update_payload = account_payload("美股一分钟账户")
    update_payload["market"] = "US_STOCK"
    update_payload["initialCash"] = 50000
    update_response = client.put(
        f"/api/simulation-accounts/{created['id']}",
        json=update_payload,
        headers=auth_headers(token),
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "美股一分钟账户"
    assert update_response.json()["market"] == "US_STOCK"
    assert update_response.json()["initialCash"] == 50000

    delete_response = client.delete(
        f"/api/simulation-accounts/{created['id']}",
        headers=auth_headers(token),
    )
    assert delete_response.status_code == 204

    missing_response = client.get(
        f"/api/simulation-accounts/{created['id']}",
        headers=auth_headers(token),
    )
    assert missing_response.status_code == 404


def test_simulation_account_requires_login(client):
    response = client.post("/api/simulation-accounts", json=account_payload())

    assert response.status_code == 401


def test_simulation_account_list_only_returns_current_users_items(client):
    alice_token = register_and_token(client, "account-list-alice", "account-list-alice@example.com")
    bob_token = register_and_token(client, "account-list-bob", "account-list-bob@example.com")

    alice_create = client.post(
        "/api/simulation-accounts",
        json=account_payload("Alice 账户"),
        headers=auth_headers(alice_token),
    )
    assert alice_create.status_code == 201
    bob_create = client.post(
        "/api/simulation-accounts",
        json=account_payload("Bob 账户"),
        headers=auth_headers(bob_token),
    )
    assert bob_create.status_code == 201

    alice_list = client.get("/api/simulation-accounts", headers=auth_headers(alice_token))
    bob_list = client.get("/api/simulation-accounts", headers=auth_headers(bob_token))

    assert alice_list.status_code == 200
    assert bob_list.status_code == 200
    assert [item["name"] for item in alice_list.json()["items"]] == ["Alice 账户"]
    assert [item["name"] for item in bob_list.json()["items"]] == ["Bob 账户"]

    bob_reads_alice = client.get(
        f"/api/simulation-accounts/{alice_create.json()['id']}",
        headers=auth_headers(bob_token),
    )
    assert bob_reads_alice.status_code == 404
