from app.core.security import create_access_token


def test_me_requires_token(client):
    response = client.get("/api/auth/me")

    assert response.status_code == 401


def test_me_returns_current_user(client):
    register_response = client.post(
        "/api/auth/register",
        json={
            "username": "alice",
            "email": "alice@example.com",
            "password": "StrongerPass123",
        },
    )
    assert register_response.status_code == 201
    token = register_response.json()["access_token"]

    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["username"] == "alice"
    assert response.json()["roles"] == ["user"]


def test_me_rejects_malformed_token_subject(client):
    token = create_access_token(subject="abc", roles=["user"])

    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid token"
