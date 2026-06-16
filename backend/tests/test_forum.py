from datetime import datetime, timedelta

from sqlalchemy import select

from app.models.forum import ForumComment, ForumPost
from app.models.user import Role, User
from tests.test_strategies import auth_headers, register_and_token, strategy_payload


def post_payload(
    title: str = "止盈积木复盘",
    content: str = "这个帖子记录一次止盈积木的使用经验。",
) -> dict:
    return {
        "title": title,
        "content": content,
        "topic": "积木经验",
        "sharedBlockId": None,
    }


def comment_payload(content: str = "这个案例很适合新手复盘。") -> dict:
    return {"content": content}


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


def test_forum_post_submission_requires_review_before_public_listing(client, db_session):
    user_token = register_and_token(client, "alice", "alice@example.com")
    admin_token = register_and_token(client, "admin", "admin@example.com")
    grant_admin_role(db_session, "admin@example.com")

    create_response = client.post(
        "/api/forum/posts",
        json=post_payload(),
        headers=auth_headers(user_token),
    )

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["reviewStatus"] == "pending_review"
    assert created["authorName"] == "alice"

    public_before_review = client.get("/api/forum/posts")
    assert public_before_review.status_code == 200
    assert public_before_review.json()["total"] == 0

    approve_response = client.post(
        f"/api/admin/forum-posts/{created['id']}/approve",
        headers=auth_headers(admin_token),
    )
    assert approve_response.status_code == 200
    assert approve_response.json()["reviewStatus"] == "approved"

    public_after_review = client.get("/api/forum/posts?keyword=止盈&page=1&pageSize=10")
    assert public_after_review.status_code == 200
    payload = public_after_review.json()
    assert payload["total"] == 1
    assert payload["items"][0]["title"] == "止盈积木复盘"
    assert payload["items"][0]["commentCount"] == 0


def test_forum_comments_require_login_and_review_before_public_detail(client, db_session):
    user_token = register_and_token(client, "alice", "alice@example.com")
    commenter_token = register_and_token(client, "bob", "bob@example.com")
    admin_token = register_and_token(client, "admin", "admin@example.com")
    grant_admin_role(db_session, "admin@example.com")

    post_response = client.post(
        "/api/forum/posts",
        json=post_payload("移动止损经验"),
        headers=auth_headers(user_token),
    )
    assert post_response.status_code == 201
    post_id = post_response.json()["id"]
    approve_post_response = client.post(
        f"/api/admin/forum-posts/{post_id}/approve",
        headers=auth_headers(admin_token),
    )
    assert approve_post_response.status_code == 200

    visitor_comment = client.post(
        f"/api/forum/posts/{post_id}/comments",
        json=comment_payload("游客评论"),
    )
    assert visitor_comment.status_code == 401

    comment_response = client.post(
        f"/api/forum/posts/{post_id}/comments",
        json=comment_payload(),
        headers=auth_headers(commenter_token),
    )
    assert comment_response.status_code == 201
    comment = comment_response.json()
    assert comment["reviewStatus"] == "pending_review"
    assert comment["authorName"] == "bob"

    detail_before_review = client.get(f"/api/forum/posts/{post_id}")
    assert detail_before_review.status_code == 200
    assert detail_before_review.json()["commentCount"] == 0
    assert detail_before_review.json()["comments"] == []

    approve_comment_response = client.post(
        f"/api/admin/forum-comments/{comment['id']}/approve",
        headers=auth_headers(admin_token),
    )
    assert approve_comment_response.status_code == 200
    assert approve_comment_response.json()["reviewStatus"] == "approved"

    detail_after_review = client.get(f"/api/forum/posts/{post_id}")
    assert detail_after_review.status_code == 200
    detail = detail_after_review.json()
    assert detail["commentCount"] == 1
    assert detail["comments"][0]["content"] == "这个案例很适合新手复盘。"


def test_forum_post_can_attach_owned_strategy_summary(client, db_session):
    user_token = register_and_token(client, "alice", "alice@example.com")
    admin_token = register_and_token(client, "admin", "admin@example.com")
    grant_admin_role(db_session, "admin@example.com")

    strategy_response = client.post(
        "/api/strategies",
        json=strategy_payload("论坛关联策略"),
        headers=auth_headers(user_token),
    )
    assert strategy_response.status_code == 201
    strategy_id = strategy_response.json()["id"]

    post_response = client.post(
        "/api/forum/posts",
        json={
            **post_payload("关联策略复盘", "这条帖子附带一个策略卡片。"),
            "relatedType": "strategy",
            "relatedId": strategy_id,
        },
        headers=auth_headers(user_token),
    )
    assert post_response.status_code == 201
    created = post_response.json()
    assert created["relatedType"] == "strategy"
    assert created["relatedId"] == strategy_id
    assert created["relatedTitle"] == "论坛关联策略"
    assert "000001.SZ" in created["relatedSummary"]

    assert (
        client.post(
            f"/api/admin/forum-posts/{created['id']}/approve",
            headers=auth_headers(admin_token),
        ).status_code
        == 200
    )

    detail_response = client.get(f"/api/forum/posts/{created['id']}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["relatedType"] == "strategy"
    assert detail["relatedId"] == strategy_id
    assert detail["relatedTitle"] == "论坛关联策略"
    assert "000001.SZ" in detail["relatedSummary"]


def test_forum_post_cannot_attach_another_users_private_strategy(client):
    alice_token = register_and_token(client, "alice", "alice@example.com")
    bob_token = register_and_token(client, "bob", "bob@example.com")

    bob_strategy = client.post(
        "/api/strategies",
        json=strategy_payload("Bob 私有策略"),
        headers=auth_headers(bob_token),
    )
    assert bob_strategy.status_code == 201

    post_response = client.post(
        "/api/forum/posts",
        json={
            **post_payload("越权关联策略", "这条帖子不应该能关联别人的策略。"),
            "relatedType": "strategy",
            "relatedId": bob_strategy.json()["id"],
        },
        headers=auth_headers(alice_token),
    )

    assert post_response.status_code == 404
    assert post_response.json()["detail"] == "Related content not found"


def test_public_forum_posts_support_reply_publish_and_comment_sorting(client, db_session):
    author_token = register_and_token(client, "alice", "alice@example.com")
    commenter_token = register_and_token(client, "bob", "bob@example.com")
    admin_token = register_and_token(client, "admin", "admin@example.com")
    grant_admin_role(db_session, "admin@example.com")

    older_post = client.post(
        "/api/forum/posts",
        json=post_payload("早发布但有新回复", "这条帖子发布时间较早，但后续讨论更多。"),
        headers=auth_headers(author_token),
    )
    newer_post = client.post(
        "/api/forum/posts",
        json=post_payload("最新发布帖子", "这条帖子创建时间更新，但还没有足够讨论。"),
        headers=auth_headers(author_token),
    )
    assert older_post.status_code == 201
    assert newer_post.status_code == 201
    older_post_id = older_post.json()["id"]
    newer_post_id = newer_post.json()["id"]
    assert (
        client.post(
            f"/api/admin/forum-posts/{older_post_id}/approve",
            headers=auth_headers(admin_token),
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/admin/forum-posts/{newer_post_id}/approve",
            headers=auth_headers(admin_token),
        ).status_code
        == 200
    )

    first_comment = client.post(
        f"/api/forum/posts/{older_post_id}/comments",
        json=comment_payload("第一条公开回复"),
        headers=auth_headers(commenter_token),
    )
    second_comment = client.post(
        f"/api/forum/posts/{older_post_id}/comments",
        json=comment_payload("第二条公开回复"),
        headers=auth_headers(commenter_token),
    )
    assert first_comment.status_code == 201
    assert second_comment.status_code == 201
    for comment_id in (first_comment.json()["id"], second_comment.json()["id"]):
        assert (
            client.post(
                f"/api/admin/forum-comments/{comment_id}/approve",
                headers=auth_headers(admin_token),
            ).status_code
            == 200
        )

    base_time = datetime(2026, 6, 7, 9, 0, 0)
    db_session.get(ForumPost, older_post_id).created_at = base_time
    db_session.get(ForumPost, older_post_id).updated_at = base_time
    db_session.get(ForumPost, newer_post_id).created_at = base_time + timedelta(hours=1)
    db_session.get(ForumPost, newer_post_id).updated_at = base_time + timedelta(hours=1)
    db_session.get(ForumComment, first_comment.json()["id"]).updated_at = (
        base_time + timedelta(hours=2)
    )
    db_session.get(ForumComment, second_comment.json()["id"]).updated_at = (
        base_time + timedelta(hours=3)
    )
    db_session.commit()

    latest_reply = client.get("/api/forum/posts?sort=latest_reply&page=1&pageSize=10")
    assert latest_reply.status_code == 200
    assert latest_reply.json()["items"][0]["title"] == "早发布但有新回复"

    newest = client.get("/api/forum/posts?sort=newest&page=1&pageSize=10")
    assert newest.status_code == 200
    assert newest.json()["items"][0]["title"] == "最新发布帖子"

    most_commented = client.get("/api/forum/posts?sort=most_commented&page=1&pageSize=10")
    assert most_commented.status_code == 200
    assert most_commented.json()["items"][0]["title"] == "早发布但有新回复"
    assert most_commented.json()["items"][0]["commentCount"] == 2


def test_admin_can_reject_forum_posts_and_comments(client, db_session):
    user_token = register_and_token(client, "alice", "alice@example.com")
    admin_token = register_and_token(client, "admin", "admin@example.com")
    grant_admin_role(db_session, "admin@example.com")

    post_response = client.post(
        "/api/forum/posts",
        json=post_payload("需要拒绝的帖子"),
        headers=auth_headers(user_token),
    )
    assert post_response.status_code == 201
    post_id = post_response.json()["id"]

    reject_post_response = client.post(
        f"/api/admin/forum-posts/{post_id}/reject",
        json={"reason": "复盘内容太少，无法判断策略逻辑。"},
        headers=auth_headers(admin_token),
    )
    assert reject_post_response.status_code == 200
    assert reject_post_response.json()["reviewStatus"] == "rejected"
    assert reject_post_response.json()["reviewReason"] == "复盘内容太少，无法判断策略逻辑。"

    approved_post_response = client.post(
        "/api/forum/posts",
        json=post_payload("可评论帖子"),
        headers=auth_headers(user_token),
    )
    assert approved_post_response.status_code == 201
    approved_post_id = approved_post_response.json()["id"]
    assert (
        client.post(
            f"/api/admin/forum-posts/{approved_post_id}/approve",
            headers=auth_headers(admin_token),
        ).status_code
        == 200
    )
    comment_response = client.post(
        f"/api/forum/posts/{approved_post_id}/comments",
        json=comment_payload("需要拒绝的评论"),
        headers=auth_headers(user_token),
    )
    assert comment_response.status_code == 201

    reject_comment_response = client.post(
        f"/api/admin/forum-comments/{comment_response.json()['id']}/reject",
        json={"reason": "评论偏离主题。"},
        headers=auth_headers(admin_token),
    )
    assert reject_comment_response.status_code == 200
    assert reject_comment_response.json()["reviewStatus"] == "rejected"
    assert reject_comment_response.json()["reviewReason"] == "评论偏离主题。"


def test_admin_can_list_pending_forum_post_reviews(client, db_session):
    user_token = register_and_token(client, "alice", "alice@example.com")
    normal_token = register_and_token(client, "bob", "bob@example.com")
    admin_token = register_and_token(client, "admin", "admin@example.com")
    grant_admin_role(db_session, "admin@example.com")

    first_post = client.post(
        "/api/forum/posts",
        json=post_payload("待审核止盈帖子"),
        headers=auth_headers(user_token),
    )
    second_post = client.post(
        "/api/forum/posts",
        json=post_payload("待审核冷却帖子", "这个帖子记录一次冷却规则的使用经验。"),
        headers=auth_headers(user_token),
    )
    rejected_post = client.post(
        "/api/forum/posts",
        json=post_payload("已拒绝帖子", "这个帖子会被管理员驳回。"),
        headers=auth_headers(user_token),
    )
    assert first_post.status_code == 201
    assert second_post.status_code == 201
    assert rejected_post.status_code == 201
    assert (
        client.post(
            f"/api/admin/forum-posts/{rejected_post.json()['id']}/reject",
            json={"reason": "帖子不符合发布规范。"},
            headers=auth_headers(admin_token),
        ).status_code
        == 200
    )

    normal_user_response = client.get(
        "/api/admin/forum-post-reviews",
        headers=auth_headers(normal_token),
    )
    assert normal_user_response.status_code == 403

    review_response = client.get(
        "/api/admin/forum-post-reviews?keyword=止盈&page=1&pageSize=10",
        headers=auth_headers(admin_token),
    )
    assert review_response.status_code == 200
    payload = review_response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["title"] == "待审核止盈帖子"
    assert payload["items"][0]["reviewStatus"] == "pending_review"
    assert payload["items"][0]["authorName"] == "alice"


def test_admin_can_list_pending_forum_comment_reviews(client, db_session):
    author_token = register_and_token(client, "alice", "alice@example.com")
    commenter_token = register_and_token(client, "bob", "bob@example.com")
    admin_token = register_and_token(client, "admin", "admin@example.com")
    grant_admin_role(db_session, "admin@example.com")

    post_response = client.post(
        "/api/forum/posts",
        json=post_payload("已公开讨论帖"),
        headers=auth_headers(author_token),
    )
    assert post_response.status_code == 201
    post_id = post_response.json()["id"]
    assert (
        client.post(
            f"/api/admin/forum-posts/{post_id}/approve",
            headers=auth_headers(admin_token),
        ).status_code
        == 200
    )

    first_comment = client.post(
        f"/api/forum/posts/{post_id}/comments",
        json=comment_payload("待审核止损评论"),
        headers=auth_headers(commenter_token),
    )
    second_comment = client.post(
        f"/api/forum/posts/{post_id}/comments",
        json=comment_payload("待审核冷却评论"),
        headers=auth_headers(commenter_token),
    )
    assert first_comment.status_code == 201
    assert second_comment.status_code == 201
    assert (
        client.post(
            f"/api/admin/forum-comments/{second_comment.json()['id']}/reject",
            json={"reason": "评论内容不适合公开展示。"},
            headers=auth_headers(admin_token),
        ).status_code
        == 200
    )

    review_response = client.get(
        "/api/admin/forum-comment-reviews?keyword=止损&page=1&pageSize=10",
        headers=auth_headers(admin_token),
    )
    assert review_response.status_code == 200
    payload = review_response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["content"] == "待审核止损评论"
    assert payload["items"][0]["postTitle"] == "已公开讨论帖"
    assert payload["items"][0]["reviewStatus"] == "pending_review"
    assert payload["items"][0]["authorName"] == "bob"


def test_user_can_list_own_forum_posts_and_comments_with_review_status(client, db_session):
    alice_token = register_and_token(client, "alice", "alice@example.com")
    bob_token = register_and_token(client, "bob", "bob@example.com")
    admin_token = register_and_token(client, "admin", "admin@example.com")
    grant_admin_role(db_session, "admin@example.com")

    alice_pending_post = client.post(
        "/api/forum/posts",
        json=post_payload("Alice 待审核帖子", "Alice 自己的待审核帖子。"),
        headers=auth_headers(alice_token),
    )
    alice_rejected_post = client.post(
        "/api/forum/posts",
        json=post_payload("Alice 已驳回帖子", "Alice 自己的已驳回帖子。"),
        headers=auth_headers(alice_token),
    )
    bob_post = client.post(
        "/api/forum/posts",
        json=post_payload("Bob 待审核帖子", "Bob 的帖子不应该出现在 Alice 列表里。"),
        headers=auth_headers(bob_token),
    )
    assert alice_pending_post.status_code == 201
    assert alice_rejected_post.status_code == 201
    assert bob_post.status_code == 201
    assert (
        client.post(
            f"/api/admin/forum-posts/{alice_rejected_post.json()['id']}/reject",
            json={"reason": "帖子缺少可复现的策略细节。"},
            headers=auth_headers(admin_token),
        ).status_code
        == 200
    )

    visitor_posts = client.get("/api/forum/my-posts")
    assert visitor_posts.status_code == 401

    alice_posts = client.get(
        "/api/forum/my-posts?page=1&pageSize=10",
        headers=auth_headers(alice_token),
    )
    assert alice_posts.status_code == 200
    posts_payload = alice_posts.json()
    assert posts_payload["total"] == 2
    post_titles = {item["title"] for item in posts_payload["items"]}
    post_statuses = {item["title"]: item["reviewStatus"] for item in posts_payload["items"]}
    assert post_titles == {"Alice 待审核帖子", "Alice 已驳回帖子"}
    assert post_statuses["Alice 待审核帖子"] == "pending_review"
    assert post_statuses["Alice 已驳回帖子"] == "rejected"
    post_reasons = {item["title"]: item["reviewReason"] for item in posts_payload["items"]}
    assert post_reasons["Alice 待审核帖子"] is None
    assert post_reasons["Alice 已驳回帖子"] == "帖子缺少可复现的策略细节。"

    public_post = client.post(
        "/api/forum/posts",
        json=post_payload("Bob 公开讨论帖", "用于承载 Alice 的评论。"),
        headers=auth_headers(bob_token),
    )
    assert public_post.status_code == 201
    public_post_id = public_post.json()["id"]
    assert (
        client.post(
            f"/api/admin/forum-posts/{public_post_id}/approve",
            headers=auth_headers(admin_token),
        ).status_code
        == 200
    )

    alice_pending_comment = client.post(
        f"/api/forum/posts/{public_post_id}/comments",
        json=comment_payload("Alice 待审核评论"),
        headers=auth_headers(alice_token),
    )
    alice_rejected_comment = client.post(
        f"/api/forum/posts/{public_post_id}/comments",
        json=comment_payload("Alice 已驳回评论"),
        headers=auth_headers(alice_token),
    )
    bob_comment = client.post(
        f"/api/forum/posts/{public_post_id}/comments",
        json=comment_payload("Bob 的评论不应该出现在 Alice 列表里"),
        headers=auth_headers(bob_token),
    )
    assert alice_pending_comment.status_code == 201
    assert alice_rejected_comment.status_code == 201
    assert bob_comment.status_code == 201
    assert (
        client.post(
            f"/api/admin/forum-comments/{alice_rejected_comment.json()['id']}/reject",
            json={"reason": "评论不够具体，无法帮助其他用户。"},
            headers=auth_headers(admin_token),
        ).status_code
        == 200
    )

    visitor_comments = client.get("/api/forum/my-comments")
    assert visitor_comments.status_code == 401

    alice_comments = client.get(
        "/api/forum/my-comments?page=1&pageSize=10",
        headers=auth_headers(alice_token),
    )
    assert alice_comments.status_code == 200
    comments_payload = alice_comments.json()
    assert comments_payload["total"] == 2
    comment_statuses = {
        item["content"]: item["reviewStatus"] for item in comments_payload["items"]
    }
    assert set(comment_statuses) == {"Alice 待审核评论", "Alice 已驳回评论"}
    assert comment_statuses["Alice 待审核评论"] == "pending_review"
    assert comment_statuses["Alice 已驳回评论"] == "rejected"
    comment_reasons = {
        item["content"]: item["reviewReason"] for item in comments_payload["items"]
    }
    assert comment_reasons["Alice 待审核评论"] is None
    assert comment_reasons["Alice 已驳回评论"] == "评论不够具体，无法帮助其他用户。"
    assert comments_payload["items"][0]["postTitle"] == "Bob 公开讨论帖"
