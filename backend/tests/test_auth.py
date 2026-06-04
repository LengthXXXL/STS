def test_register_creates_user_and_returns_token(client):
    response = client.post(
        "/api/auth/register",
        json={
            "username": "alice",
            "email": "alice@example.com",
            "password": "StrongerPass123",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert payload["user"]["username"] == "alice"
    assert payload["user"]["roles"] == ["user"]
    assert payload["access_token"]


def test_register_rejects_duplicate_email(client):
    user = {
        "username": "alice",
        "email": "alice@example.com",
        "password": "StrongerPass123",
    }
    assert client.post("/api/auth/register", json=user).status_code == 201

    response = client.post(
        "/api/auth/register",
        json={**user, "username": "alice2"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Email already registered"


def test_login_returns_token_for_valid_credentials(client):
    client.post(
        "/api/auth/register",
        json={
            "username": "alice",
            "email": "alice@example.com",
            "password": "StrongerPass123",
        },
    )

    response = client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "StrongerPass123"},
    )

    assert response.status_code == 200
    assert response.json()["user"]["email"] == "alice@example.com"
    assert response.json()["access_token"]


def test_login_rejects_bad_credentials(client):
    response = client.post(
        "/api/auth/login",
        json={"email": "nobody@example.com", "password": "bad-password"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"
