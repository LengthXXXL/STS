from types import SimpleNamespace

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api import shared_blocks as shared_blocks_api
from app.models.custom_block import CustomBlock
from app.models.shared_block import RecommendationEvent, SharedBlockImport, SharedBlockStats
from app.models.user import Role, User
from app.services import shared_block_service
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


def register_user_token(client, username: str, email: str) -> str:
    return register_and_token(client, username, email)


def grant_admin_role(db_session, email: str) -> None:
    user = db_session.scalar(select(User).where(User.email == email))
    assert user is not None
    admin_role = db_session.scalar(select(Role).where(Role.name == "admin"))
    if admin_role is None:
        admin_role = Role(name="admin")
        db_session.add(admin_role)
        db_session.flush()
    user.roles.append(admin_role)
    db_session.commit()


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


def test_favorite_and_unfavorite_shared_block(client, db_session):
    owner_token = register_user_token(client, "alice", "alice@example.com")
    viewer_token = register_user_token(client, "bob", "bob@example.com")
    block = create_custom_block(client, owner_token, "收藏模板")
    approve_block_directly(db_session, block["id"])

    favorite_response = client.post(
        f"/api/shared-blocks/{block['id']}/favorite",
        headers=auth_headers(viewer_token),
    )
    duplicate_response = client.post(
        f"/api/shared-blocks/{block['id']}/favorite",
        headers=auth_headers(viewer_token),
    )
    list_response = client.get("/api/shared-blocks", headers=auth_headers(viewer_token))
    unfavorite_response = client.delete(
        f"/api/shared-blocks/{block['id']}/favorite",
        headers=auth_headers(viewer_token),
    )

    assert favorite_response.status_code == 200
    assert duplicate_response.status_code == 200
    assert duplicate_response.json()["favoriteCount"] == 1
    assert list_response.json()["items"][0]["favoriteCount"] == 1
    assert list_response.json()["items"][0]["isFavorited"] is True
    assert unfavorite_response.status_code == 204
    favorite_event_count = db_session.scalar(
        select(func.count()).where(
            RecommendationEvent.event_type == "favorite",
            RecommendationEvent.custom_block_id == block["id"],
        )
    )
    assert favorite_event_count == 1


def test_unfavorite_without_existing_favorite_records_event(client, db_session):
    owner_token = register_user_token(client, "alice", "alice@example.com")
    viewer_token = register_user_token(client, "bob", "bob@example.com")
    block = create_custom_block(client, owner_token, "未收藏模板")
    approve_block_directly(db_session, block["id"])

    response = client.delete(
        f"/api/shared-blocks/{block['id']}/favorite",
        headers=auth_headers(viewer_token),
    )
    list_response = client.get("/api/shared-blocks", headers=auth_headers(viewer_token))

    assert response.status_code == 204
    assert list_response.json()["items"][0]["favoriteCount"] == 0
    event = db_session.scalar(
        select(RecommendationEvent).where(
            RecommendationEvent.event_type == "unfavorite",
            RecommendationEvent.custom_block_id == block["id"],
        )
    )
    assert event is not None


def test_import_shared_block_auto_renames_duplicate(client, db_session):
    owner_token = register_user_token(client, "alice", "alice@example.com")
    importer_token = register_user_token(client, "bob", "bob@example.com")
    source_payload = custom_block_payload("导入模板")
    source_payload["description"] = "可复制的导入模板"
    source_payload["category"] = "动作"
    source_payload["tags"] = ["买入", "复制"]
    source_payload["exposedParams"] = [
        {
            "id": "buy-1:sizePercent",
            "nodeId": "buy-1",
            "paramKey": "sizePercent",
            "label": "买入 - 买入仓位",
            "nodeLabel": "买入",
            "type": "number",
            "defaultValue": "20",
            "suffix": "%",
            "min": "1",
            "max": "100",
            "step": "1",
            "options": [],
        }
    ]
    source_response = client.post(
        "/api/custom-blocks",
        json=source_payload,
        headers=auth_headers(owner_token),
    )
    assert source_response.status_code == 201
    source = source_response.json()
    approve_block_directly(db_session, source["id"])
    existing = create_custom_block(client, importer_token, "导入模板")

    import_response = client.post(
        f"/api/shared-blocks/{source['id']}/import",
        headers=auth_headers(importer_token),
    )

    assert existing["name"] == "导入模板"
    assert import_response.status_code == 201
    payload = import_response.json()
    assert payload["name"] == "导入模板（导入）"
    assert payload["description"] == "可复制的导入模板"
    assert payload["category"] == "动作"
    assert payload["tags"] == ["买入", "复制"]
    assert payload["reviewStatus"] == "private"
    assert payload["template"]["nodes"][0]["type"] == "buy"
    assert payload["exposedParams"][0]["nodeId"] == "buy-1"
    assert payload["exposedParams"][0]["paramKey"] == "sizePercent"
    stats = db_session.scalar(
        select(SharedBlockStats).where(SharedBlockStats.custom_block_id == source["id"])
    )
    assert stats is not None
    assert stats.import_count == 1
    import_record = db_session.scalar(
        select(SharedBlockImport).where(
            SharedBlockImport.source_custom_block_id == source["id"],
            SharedBlockImport.imported_custom_block_id == payload["id"],
        )
    )
    assert import_record is not None
    import_event = db_session.scalar(
        select(RecommendationEvent).where(
            RecommendationEvent.event_type == "import",
            RecommendationEvent.custom_block_id == source["id"],
        )
    )
    assert import_event is not None


def test_import_shared_block_uses_next_available_duplicate_name(client, db_session):
    owner_token = register_user_token(client, "alice", "alice@example.com")
    importer_token = register_user_token(client, "bob", "bob@example.com")
    source = create_custom_block(client, owner_token, "阶梯导入模板")
    approve_block_directly(db_session, source["id"])
    create_custom_block(client, importer_token, "阶梯导入模板")
    create_custom_block(client, importer_token, "阶梯导入模板（导入）")

    import_response = client.post(
        f"/api/shared-blocks/{source['id']}/import",
        headers=auth_headers(importer_token),
    )

    assert import_response.status_code == 201
    assert import_response.json()["name"] == "阶梯导入模板（导入 2）"


def test_import_shared_block_retries_after_duplicate_name_integrity_error(
    client,
    db_session,
    monkeypatch,
):
    owner_token = register_user_token(client, "alice", "alice@example.com")
    register_user_token(client, "bob", "bob@example.com")
    source = create_custom_block(client, owner_token, "重试导入模板")
    approve_block_directly(db_session, source["id"])
    set_shared_stats_directly(db_session, source["id"])
    importer = db_session.scalar(select(User).where(User.email == "bob@example.com"))
    assert importer is not None
    candidate_names = iter(["重试导入模板（导入）", "重试导入模板（导入 2）"])
    original_flush = db_session.flush
    flush_attempts = {"failed": False}

    def retry_names(db, current_user, base_name):
        assert db is db_session
        assert current_user.id == importer.id
        assert base_name == "重试导入模板"
        return next(candidate_names)

    def fail_first_import_flush(*args, **kwargs):
        pending_import = any(
            isinstance(item, CustomBlock)
            and item.owner_id == importer.id
            and item.name == "重试导入模板（导入）"
            for item in db_session.new
        )
        if pending_import and not flush_attempts["failed"]:
            flush_attempts["failed"] = True
            raise IntegrityError(
                "INSERT INTO custom_blocks",
                {},
                Exception("duplicate name"),
            )
        return original_flush(*args, **kwargs)

    monkeypatch.setattr(shared_block_service, "_import_name", retry_names)
    monkeypatch.setattr(db_session, "flush", fail_first_import_flush)

    imported = shared_block_service.import_shared_block(db_session, importer, source["id"])

    assert flush_attempts["failed"] is True
    assert imported is not None
    assert imported.name == "重试导入模板（导入 2）"
    stats = db_session.scalar(
        select(SharedBlockStats).where(SharedBlockStats.custom_block_id == source["id"])
    )
    assert stats is not None
    assert stats.import_count == 1


def test_import_shared_block_retry_exhaustion_returns_conflict(client, monkeypatch):
    token = register_user_token(client, "alice", "alice@example.com")

    def exhausted_import(db, current_user, block_id):
        raise ValueError("Unable to import shared block with a unique name")

    monkeypatch.setattr(shared_blocks_api, "import_shared_block", exhausted_import)

    response = client.post(
        "/api/shared-blocks/1/import",
        headers=auth_headers(token),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Unable to import shared block with a unique name"


def test_increment_stat_raises_when_stats_row_missing(db_session):
    with pytest.raises(RuntimeError):
        shared_block_service._increment_stat(db_session, 9999, "import_count")


def test_decrement_stat_raises_when_stats_row_missing(db_session):
    with pytest.raises(RuntimeError):
        shared_block_service._decrement_stat_safely(db_session, 9999, "favorite_count")


def test_ensure_stats_retries_and_raises_when_integrity_race_leaves_no_stats(
    db_session,
    monkeypatch,
):
    block = SimpleNamespace(id=123, shared_stats=None)
    flush_count = {"value": 0}

    def approved_block(db, block_id):
        assert db is db_session
        assert block_id == block.id
        return block

    def missing_stats_flush(*args, **kwargs):
        flush_count["value"] += 1
        raise IntegrityError(
            "INSERT INTO shared_block_stats",
            {},
            Exception("duplicate stats"),
        )

    monkeypatch.setattr(shared_block_service, "_approved_block", approved_block)
    monkeypatch.setattr(db_session, "flush", missing_stats_flush)

    with pytest.raises(RuntimeError):
        shared_block_service._ensure_approved_block_stats(db_session, block.id)

    assert flush_count["value"] == 2


def test_admin_can_approve_and_reject_pending_blocks(client, db_session):
    owner_token = register_user_token(client, "alice", "alice@example.com")
    admin_token = register_user_token(client, "admin", "admin@example.com")
    grant_admin_role(db_session, "admin@example.com")
    pending_block = create_custom_block(client, owner_token, "审核模板")
    publish_response = client.post(
        f"/api/custom-blocks/{pending_block['id']}/publish",
        headers=auth_headers(owner_token),
    )
    assert publish_response.status_code == 200

    review_list = client.get(
        "/api/admin/custom-block-reviews",
        headers=auth_headers(admin_token),
    )
    approve_response = client.post(
        f"/api/admin/custom-block-reviews/{pending_block['id']}/approve",
        headers=auth_headers(admin_token),
    )
    public_list = client.get("/api/shared-blocks")

    assert review_list.status_code == 200
    assert review_list.json()["items"][0]["id"] == pending_block["id"]
    assert approve_response.status_code == 200
    assert approve_response.json()["reviewStatus"] == "approved"
    assert public_list.json()["items"][0]["id"] == pending_block["id"]


def test_admin_review_transitions_are_pending_only(client, db_session):
    owner_token = register_user_token(client, "alice", "alice@example.com")
    admin_token = register_user_token(client, "admin", "admin@example.com")
    grant_admin_role(db_session, "admin@example.com")
    approved_candidate = create_custom_block(client, owner_token, "只审核一次模板")
    rejected_candidate = create_custom_block(client, owner_token, "拒绝模板")
    for block in (approved_candidate, rejected_candidate):
        publish_response = client.post(
            f"/api/custom-blocks/{block['id']}/publish",
            headers=auth_headers(owner_token),
        )
        assert publish_response.status_code == 200

    approve_response = client.post(
        f"/api/admin/custom-block-reviews/{approved_candidate['id']}/approve",
        headers=auth_headers(admin_token),
    )
    approve_again_response = client.post(
        f"/api/admin/custom-block-reviews/{approved_candidate['id']}/approve",
        headers=auth_headers(admin_token),
    )
    reject_after_approve_response = client.post(
        f"/api/admin/custom-block-reviews/{approved_candidate['id']}/reject",
        headers=auth_headers(admin_token),
    )
    reject_response = client.post(
        f"/api/admin/custom-block-reviews/{rejected_candidate['id']}/reject",
        headers=auth_headers(admin_token),
    )
    approve_after_reject_response = client.post(
        f"/api/admin/custom-block-reviews/{rejected_candidate['id']}/approve",
        headers=auth_headers(admin_token),
    )

    assert approve_response.status_code == 200
    assert approve_response.json()["reviewStatus"] == "approved"
    assert approve_again_response.status_code == 404
    assert reject_after_approve_response.status_code == 404
    assert reject_response.status_code == 200
    assert reject_response.json()["reviewStatus"] == "rejected"
    assert approve_after_reject_response.status_code == 404


def test_non_admin_cannot_review_blocks(client):
    token = register_user_token(client, "alice", "alice@example.com")

    response = client.get("/api/admin/custom-block-reviews", headers=auth_headers(token))

    assert response.status_code == 403
