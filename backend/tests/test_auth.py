from __future__ import annotations

import pytest

from app.security import PasswordPolicyError, hash_password, validate_password_policy, verify_password


def test_password_hash_roundtrip():
    hashed = hash_password("correct-horse-battery")
    assert hashed != "correct-horse-battery"
    assert verify_password("correct-horse-battery", hashed)
    assert not verify_password("wrong-password", hashed)


def test_password_policy_rejects_short_password():
    with pytest.raises(PasswordPolicyError):
        validate_password_policy("short", min_length=10)


def test_password_policy_accepts_long_enough_password():
    validate_password_policy("longenoughpassword", min_length=10)


def test_login_rejects_unknown_user(client):
    response = client.post("/auth/login", json={"username": "nobody", "password": "whatever123"})
    assert response.status_code == 401


def test_login_rejects_wrong_password(client, seed_user):
    response = client.post("/auth/login", json={"username": "geir", "password": "wrong-password"})
    assert response.status_code == 401


def test_login_succeeds_and_sets_cookie(client, seed_user):
    response = client.post(
        "/auth/login",
        json={"username": "geir", "password": "correct-horse-battery"},
    )
    assert response.status_code == 200
    assert response.json()["username"] == "geir"
    assert "lifehub_session" in response.cookies


def test_me_requires_authentication(client):
    response = client.get("/auth/me")
    assert response.status_code == 401


def test_me_returns_current_user(auth_client):
    response = auth_client.get("/auth/me")
    assert response.status_code == 200
    assert response.json()["username"] == "geir"


def test_logout_clears_session(auth_client):
    response = auth_client.post("/auth/logout")
    assert response.status_code == 204

    response = auth_client.get("/auth/me")
    assert response.status_code == 401
