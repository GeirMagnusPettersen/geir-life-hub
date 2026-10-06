from __future__ import annotations


def test_create_list_and_revoke_device_token(auth_client):
    response = auth_client.post("/devices", json={"label": "Geirs telefon"})
    assert response.status_code == 201
    body = response.json()
    assert body["label"] == "Geirs telefon"
    assert len(body["token"]) > 20
    token_id = body["id"]

    response = auth_client.get("/devices")
    assert response.status_code == 200
    tokens = response.json()
    assert len(tokens) == 1
    assert "token" not in tokens[0]  # plaintext is never returned again
    assert tokens[0]["revoked_at"] is None

    response = auth_client.delete(f"/devices/{token_id}")
    assert response.status_code == 204

    response = auth_client.get("/devices")
    assert response.json()[0]["revoked_at"] is not None


def test_device_tokens_require_session_auth(client):
    response = client.post("/devices", json={"label": "Should fail"})
    assert response.status_code == 401


def test_revoke_unknown_device_token_returns_404(auth_client):
    response = auth_client.delete("/devices/does-not-exist")
    assert response.status_code == 404
