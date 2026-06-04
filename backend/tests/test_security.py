from datetime import timedelta

from app.core.security import create_access_token, decode_access_token, hash_password, verify_password


def test_password_hash_round_trip():
    password = "StrongerPass123"

    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("wrong-password", hashed)


def test_access_token_contains_user_id_and_roles():
    token = create_access_token(
        subject="42",
        roles=["user", "admin"],
        expires_delta=timedelta(minutes=10),
        secret_key="test-secret",
    )

    payload = decode_access_token(token, secret_key="test-secret")

    assert payload["sub"] == "42"
    assert payload["roles"] == ["user", "admin"]
