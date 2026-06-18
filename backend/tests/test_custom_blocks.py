from app.models.custom_block import CustomBlock
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
    assert created["exposedParams"] == []
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


def test_custom_block_owner_can_publish_private_block(client):
    token = register_and_token(client, "alice", "alice@example.com")
    create_response = client.post(
        "/api/custom-blocks",
        json=custom_block_payload("发布模板"),
        headers=auth_headers(token),
    )
    assert create_response.status_code == 201

    publish_response = client.post(
        f"/api/custom-blocks/{create_response.json()['id']}/publish",
        headers=auth_headers(token),
    )

    assert publish_response.status_code == 200
    assert publish_response.json()["reviewStatus"] == "pending_review"


def test_custom_block_publish_rejects_non_owner(client):
    alice_token = register_and_token(client, "alice", "alice@example.com")
    bob_token = register_and_token(client, "bob", "bob@example.com")
    create_response = client.post(
        "/api/custom-blocks",
        json=custom_block_payload("Alice 发布模板"),
        headers=auth_headers(alice_token),
    )
    assert create_response.status_code == 201

    publish_response = client.post(
        f"/api/custom-blocks/{create_response.json()['id']}/publish",
        headers=auth_headers(bob_token),
    )

    assert publish_response.status_code == 404


def test_custom_block_publish_rejects_pending_or_approved(client, db_session):
    token = register_and_token(client, "alice", "alice@example.com")
    create_response = client.post(
        "/api/custom-blocks",
        json=custom_block_payload("只允许发布一次"),
        headers=auth_headers(token),
    )
    assert create_response.status_code == 201
    block_id = create_response.json()["id"]
    first_publish = client.post(
        f"/api/custom-blocks/{block_id}/publish", headers=auth_headers(token)
    )
    second_publish = client.post(
        f"/api/custom-blocks/{block_id}/publish", headers=auth_headers(token)
    )

    assert first_publish.status_code == 200
    assert second_publish.status_code == 409
    assert second_publish.json()["detail"] == "Custom block is already submitted or public"

    approved_create_response = client.post(
        "/api/custom-blocks",
        json=custom_block_payload("已批准模板"),
        headers=auth_headers(token),
    )
    assert approved_create_response.status_code == 201
    approved_block_id = approved_create_response.json()["id"]
    approved_block = db_session.get(CustomBlock, approved_block_id)
    approved_block.review_status = "approved"
    db_session.commit()

    approved_publish = client.post(
        f"/api/custom-blocks/{approved_block_id}/publish", headers=auth_headers(token)
    )

    assert approved_publish.status_code == 409
    assert approved_publish.json()["detail"] == "Custom block is already submitted or public"


def test_custom_block_requires_login(client):
    response = client.post("/api/custom-blocks", json=custom_block_payload())

    assert response.status_code == 401


def test_custom_block_saves_exposed_parameters(client):
    token = register_and_token(client, "param-owner", "param-owner@example.com")
    payload = custom_block_payload("参数化止盈模板")
    payload["exposedParams"] = [
        {
            "id": "take-profit-1:profitRate",
            "nodeId": "take-profit-1",
            "paramKey": "profitRate",
            "label": "止盈 - 止盈比例",
            "nodeLabel": "止盈",
            "type": "number",
            "defaultValue": "5",
            "suffix": "%",
            "min": "0.1",
            "max": "100",
            "step": "0.1",
            "options": [],
        },
        {
            "id": "ghost:profitRate",
            "nodeId": "ghost",
            "paramKey": "profitRate",
            "label": "无效参数",
            "nodeLabel": "幽灵节点",
            "type": "number",
            "defaultValue": "5",
            "options": [],
        },
    ]

    create_response = client.post(
        "/api/custom-blocks",
        json=payload,
        headers=auth_headers(token),
    )

    assert create_response.status_code == 201
    created = create_response.json()
    assert len(created["exposedParams"]) == 1
    assert created["exposedParams"][0]["nodeId"] == "take-profit-1"
    assert created["exposedParams"][0]["paramKey"] == "profitRate"
    assert created["exposedParams"][0]["defaultValue"] == "5"

    update_payload = custom_block_payload("参数化止盈模板 v2")
    update_payload["exposedParams"] = [
        {
            **created["exposedParams"][0],
            "id": "take-profit-1:sellPercent",
            "paramKey": "sellPercent",
            "label": "止盈 - 卖出仓位",
            "defaultValue": "50",
        }
    ]
    update_response = client.put(
        f"/api/custom-blocks/{created['id']}",
        json=update_payload,
        headers=auth_headers(token),
    )

    assert update_response.status_code == 200
    assert update_response.json()["exposedParams"][0]["paramKey"] == "sellPercent"


def test_custom_block_name_must_be_unique_for_current_user(client):
    token = register_and_token(client, "alice", "alice@example.com")

    first_response = client.post(
        "/api/custom-blocks",
        json=custom_block_payload("突破模板"),
        headers=auth_headers(token),
    )
    duplicate_payload = custom_block_payload("  突破模板  ")
    duplicate_response = client.post(
        "/api/custom-blocks",
        json=duplicate_payload,
        headers=auth_headers(token),
    )

    assert first_response.status_code == 201
    assert duplicate_response.status_code == 409
    assert duplicate_response.json()["detail"] == "Custom block name already exists"


def test_custom_block_name_can_repeat_across_different_users(client):
    alice_token = register_and_token(client, "alice", "alice@example.com")
    bob_token = register_and_token(client, "bob", "bob@example.com")

    alice_response = client.post(
        "/api/custom-blocks",
        json=custom_block_payload("突破模板"),
        headers=auth_headers(alice_token),
    )
    bob_response = client.post(
        "/api/custom-blocks",
        json=custom_block_payload("突破模板"),
        headers=auth_headers(bob_token),
    )

    assert alice_response.status_code == 201
    assert bob_response.status_code == 201


def test_custom_block_update_rejects_duplicate_name_for_current_user(client):
    token = register_and_token(client, "alice", "alice@example.com")
    first_response = client.post(
        "/api/custom-blocks",
        json=custom_block_payload("突破模板"),
        headers=auth_headers(token),
    )
    second_response = client.post(
        "/api/custom-blocks",
        json=custom_block_payload("止盈模板"),
        headers=auth_headers(token),
    )

    update_response = client.put(
        f"/api/custom-blocks/{second_response.json()['id']}",
        json=custom_block_payload("突破模板"),
        headers=auth_headers(token),
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert update_response.status_code == 409
    assert update_response.json()["detail"] == "Custom block name already exists"


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
