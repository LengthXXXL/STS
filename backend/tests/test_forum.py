from sqlalchemy import select

from app.models.user import Role, User
from tests.test_strategies import auth_headers, register_and_token


def post_payload(title: str = "止盈积木复盘", content: str = "这个帖子记录一次止盈积木的使用经验。") -> dict:
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
        headers=auth_headers(admin_token),
    )
    assert reject_post_response.status_code == 200
    assert reject_post_response.json()["reviewStatus"] == "rejected"

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
        headers=auth_headers(admin_token),
    )
    assert reject_comment_response.status_code == 200
    assert reject_comment_response.json()["reviewStatus"] == "rejected"


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
