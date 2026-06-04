import pytest
from sqlalchemy.exc import IntegrityError

from app.schemas.auth import RegisterRequest
from app.services.auth_service import register_user


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


def test_register_rejects_duplicate_username(client):
    user = {
        "username": "alice",
        "email": "alice@example.com",
        "password": "StrongerPass123",
    }
    assert client.post("/api/auth/register", json=user).status_code == 201

    response = client.post(
        "/api/auth/register",
        json={**user, "email": "alice2@example.com"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Username already registered"


def test_register_rolls_back_and_translates_integrity_error(db_session, monkeypatch):
    original_rollback = db_session.rollback
    rollback_called = False

    def raise_integrity_error():
        raise IntegrityError(
            "INSERT INTO users",
            {},
            Exception("UNIQUE constraint failed: users.username"),
        )

    def track_rollback():
        nonlocal rollback_called
        rollback_called = True
        original_rollback()

    monkeypatch.setattr(db_session, "commit", raise_integrity_error)
    monkeypatch.setattr(db_session, "rollback", track_rollback)

    request = RegisterRequest(
        username="alice",
        email="alice@example.com",
        password="StrongerPass123",
    )
    with pytest.raises(ValueError) as exc_info:
        register_user(db_session, request)

    assert rollback_called
    assert str(exc_info.value) == "Username already registered"


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
