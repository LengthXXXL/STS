from sqlalchemy import func, select

from app.models.custom_block import CustomBlock
from app.models.shared_block import RecommendationEvent, SharedBlockStats
from tests.test_custom_blocks import custom_block_payload
from tests.test_strategies import auth_headers, register_and_token


def create_custom_block(client, token: str, name: str = "公开模板") -> dict:
    response = client.post(
        "/api/custom-blocks",
        json=custom_block_payload(name),
        headers=auth_headers(token),
    )
    assert response.status_code == 201
    return response.json()


def approve_block_directly(db_session, block_id: int) -> None:
    block = db_session.get(CustomBlock, block_id)
    assert block is not None
    block.review_status = "approved"
    db_session.commit()


def set_shared_stats_directly(
    db_session,
    block_id: int,
    *,
    views: int = 0,
    favorites: int = 0,
    imports: int = 0,
) -> None:
    stats = SharedBlockStats(
        custom_block_id=block_id,
        view_count=views,
        favorite_count=favorites,
        import_count=imports,
    )
    db_session.add(stats)
    db_session.commit()


def test_shared_blocks_list_only_returns_approved_blocks(client, db_session):
    token = register_and_token(client, "alice", "alice@example.com")
    private_block = create_custom_block(client, token, "私有模板")
    approved_block = create_custom_block(client, token, "公开止盈模板")
    approve_block_directly(db_session, approved_block["id"])

    response = client.get("/api/shared-blocks")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == approved_block["id"]
    assert payload["items"][0]["name"] == "公开止盈模板"
    assert payload["items"][0]["authorName"] == "alice"
    assert payload["items"][0]["nodeCount"] == 2
    assert payload["items"][0]["connectionCount"] == 1
    assert private_block["name"] not in [item["name"] for item in payload["items"]]


def test_shared_blocks_plain_list_does_not_create_stats_rows(client, db_session):
    token = register_and_token(client, "alice", "alice@example.com")
    approved_block = create_custom_block(client, token, "未统计公开模板")
    approve_block_directly(db_session, approved_block["id"])

    response = client.get("/api/shared-blocks")

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["viewCount"] == 0
    assert payload["items"][0]["favoriteCount"] == 0
    assert payload["items"][0]["importCount"] == 0
    stats_count = db_session.scalar(
        select(func.count()).where(SharedBlockStats.custom_block_id == approved_block["id"])
    )
    assert stats_count == 0


def test_shared_blocks_support_keyword_category_tag_and_latest_sort(client, db_session):
    token = register_and_token(client, "alice", "alice@example.com")
    risk_block = create_custom_block(client, token, "公开止盈模板")
    action_payload = custom_block_payload("公开买入模板")
    action_payload["category"] = "动作"
    action_payload["tags"] = ["买入", "基础"]
    action_response = client.post(
        "/api/custom-blocks", json=action_payload, headers=auth_headers(token)
    )
    assert action_response.status_code == 201
    approve_block_directly(db_session, risk_block["id"])
    approve_block_directly(db_session, action_response.json()["id"])

    response = client.get("/api/shared-blocks?keyword=买入&category=动作&tag=基础&sort=latest")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["name"] == "公开买入模板"


def test_shared_blocks_keyword_search_matches_exact_tag_only_hit(client, db_session):
    token = register_and_token(client, "alice", "alice@example.com")
    tag_only_payload = custom_block_payload("动量模板")
    tag_only_payload["category"] = "策略"
    tag_only_payload["tags"] = ["基础"]
    tag_only_response = client.post(
        "/api/custom-blocks",
        json=tag_only_payload,
        headers=auth_headers(token),
    )
    assert tag_only_response.status_code == 201
    unrelated_payload = custom_block_payload("无关模板")
    unrelated_payload["category"] = "策略"
    unrelated_payload["tags"] = ["进阶"]
    unrelated_response = client.post(
        "/api/custom-blocks",
        json=unrelated_payload,
        headers=auth_headers(token),
    )
    assert unrelated_response.status_code == 201
    approve_block_directly(db_session, tag_only_response.json()["id"])
    approve_block_directly(db_session, unrelated_response.json()["id"])

    response = client.get("/api/shared-blocks?keyword=基础")
    wildcard_response = client.get("/api/shared-blocks?keyword=%")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["name"] == "动量模板"
    assert wildcard_response.status_code == 200
    assert wildcard_response.json()["total"] == 0


def test_shared_blocks_tag_filter_uses_exact_membership(client, db_session):
    token = register_and_token(client, "alice", "alice@example.com")
    block_payload = custom_block_payload("精确标签模板")
    block_payload["tags"] = ["X"]
    response = client.post(
        "/api/custom-blocks",
        json=block_payload,
        headers=auth_headers(token),
    )
    assert response.status_code == 201
    approve_block_directly(db_session, response.json()["id"])

    percent_response = client.get("/api/shared-blocks?tag=%")
    underscore_response = client.get("/api/shared-blocks?tag=_")
    exact_response = client.get("/api/shared-blocks?tag=X")

    assert percent_response.status_code == 200
    assert percent_response.json()["total"] == 0
    assert underscore_response.status_code == 200
    assert underscore_response.json()["total"] == 0
    assert exact_response.status_code == 200
    assert exact_response.json()["total"] == 1
    assert exact_response.json()["items"][0]["name"] == "精确标签模板"


def test_shared_blocks_popular_sort_weights_imports_above_favorites(client, db_session):
    token = register_and_token(client, "alice", "alice@example.com")
    favorite_block = create_custom_block(client, token, "收藏较多模板")
    import_block = create_custom_block(client, token, "导入较多模板")
    approve_block_directly(db_session, favorite_block["id"])
    approve_block_directly(db_session, import_block["id"])
    set_shared_stats_directly(db_session, favorite_block["id"], favorites=3)
    set_shared_stats_directly(db_session, import_block["id"], imports=3)

    response = client.get("/api/shared-blocks?sort=popular")

    assert response.status_code == 200
    payload = response.json()
    assert [item["name"] for item in payload["items"]] == ["导入较多模板", "收藏较多模板"]


def test_shared_blocks_beginner_sort_prioritizes_beginner_tags(client, db_session):
    token = register_and_token(client, "alice", "alice@example.com")
    beginner_payload = custom_block_payload("基础标签模板")
    beginner_payload["category"] = "策略"
    beginner_payload["tags"] = ["基础"]
    beginner_response = client.post(
        "/api/custom-blocks",
        json=beginner_payload,
        headers=auth_headers(token),
    )
    assert beginner_response.status_code == 201
    normal_payload = custom_block_payload("普通策略模板")
    normal_payload["category"] = "策略"
    normal_payload["tags"] = ["进阶"]
    normal_response = client.post(
        "/api/custom-blocks",
        json=normal_payload,
        headers=auth_headers(token),
    )
    assert normal_response.status_code == 201
    approve_block_directly(db_session, beginner_response.json()["id"])
    approve_block_directly(db_session, normal_response.json()["id"])

    response = client.get("/api/shared-blocks?sort=beginner")

    assert response.status_code == 200
    payload = response.json()
    assert [item["name"] for item in payload["items"]] == ["基础标签模板", "普通策略模板"]


def test_shared_block_detail_records_view_count(client, db_session):
    token = register_and_token(client, "alice", "alice@example.com")
    block = create_custom_block(client, token, "详情模板")
    approve_block_directly(db_session, block["id"])

    first_response = client.get(f"/api/shared-blocks/{block['id']}")
    second_response = client.get(f"/api/shared-blocks/{block['id']}")

    assert first_response.status_code == 200
    assert first_response.json()["viewCount"] == 1
    assert second_response.status_code == 200
    assert second_response.json()["viewCount"] == 2
    assert second_response.json()["template"]["edges"][0]["from"] == "buy-1"


def test_shared_block_detail_records_view_recommendation_event(client, db_session):
    token = register_and_token(client, "alice", "alice@example.com")
    block = create_custom_block(client, token, "推荐事件模板")
    approve_block_directly(db_session, block["id"])

    response = client.get(f"/api/shared-blocks/{block['id']}")

    assert response.status_code == 200
    event = db_session.scalar(
        select(RecommendationEvent).where(
            RecommendationEvent.event_type == "view",
            RecommendationEvent.custom_block_id == block["id"],
        )
    )
    assert event is not None
