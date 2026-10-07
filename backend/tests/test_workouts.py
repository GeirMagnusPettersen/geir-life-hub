from __future__ import annotations


def _auth_headers(auth_client, label="Test phone"):
    device_response = auth_client.post("/devices", json={"label": label})
    assert device_response.status_code == 201
    token = device_response.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_workout_sync_requires_device_token(client):
    response = client.post(
        "/workouts/sync",
        json={
            "sessions": [
                {
                    "external_id": "hc-ex-1",
                    "activity_type": "running",
                    "start_time": "2026-01-01T07:00:00Z",
                    "end_time": "2026-01-01T07:30:00Z",
                }
            ]
        },
    )
    assert response.status_code == 401


def test_workout_sync_rejects_session_cookie(auth_client):
    # Device-token-only, like /sleep-activity/sync - a logged-in browser
    # session must not be able to call this without an Authorization header.
    response = auth_client.post(
        "/workouts/sync",
        json={
            "sessions": [
                {
                    "external_id": "hc-ex-1",
                    "activity_type": "running",
                    "start_time": "2026-01-01T07:00:00Z",
                    "end_time": "2026-01-01T07:30:00Z",
                }
            ]
        },
    )
    assert response.status_code == 401


def test_workout_sync_creates_and_lists_sessions(auth_client):
    headers = _auth_headers(auth_client)

    sync_response = auth_client.post(
        "/workouts/sync",
        headers=headers,
        json={
            "sessions": [
                {
                    "external_id": "hc-ex-1",
                    "activity_type": "running",
                    "start_time": "2026-01-01T07:00:00Z",
                    "end_time": "2026-01-01T07:30:00Z",
                    "duration_minutes": 30,
                    "calories": 300.5,
                    "avg_heart_rate": 142,
                    "distance_meters": 5000.0,
                },
                {
                    "external_id": "hc-ex-2",
                    "activity_type": "cycling",
                    "start_time": "2026-01-02T07:00:00Z",
                    "end_time": "2026-01-02T08:00:00Z",
                },
            ]
        },
    )
    assert sync_response.status_code == 200
    assert sync_response.json()["synced"] == 2

    list_response = auth_client.get("/workouts")
    assert list_response.status_code == 200
    sessions = list_response.json()
    assert len(sessions) == 2
    assert all(s["source"] == "health_connect" for s in sessions)
    running = next(s for s in sessions if s["external_id"] == "hc-ex-1")
    assert running["avg_heart_rate"] == 142
    assert running["distance_meters"] == 5000.0


def test_workout_sync_is_idempotent_per_external_id(auth_client):
    headers = _auth_headers(auth_client)
    item = {
        "external_id": "hc-ex-1",
        "activity_type": "running",
        "start_time": "2026-01-01T07:00:00Z",
        "end_time": "2026-01-01T07:30:00Z",
        "calories": 300.0,
    }

    first = auth_client.post("/workouts/sync", headers=headers, json={"sessions": [item]})
    assert first.status_code == 200

    item["calories"] = 320.0
    second = auth_client.post("/workouts/sync", headers=headers, json={"sessions": [item]})
    assert second.status_code == 200

    sessions = auth_client.get("/workouts").json()
    assert len(sessions) == 1
    assert sessions[0]["calories"] == 320.0


def test_workout_sync_rejects_revoked_token(auth_client):
    device_response = auth_client.post("/devices", json={"label": "Revoked phone"})
    token_id = device_response.json()["id"]
    token = device_response.json()["token"]
    auth_client.delete(f"/devices/{token_id}")

    response = auth_client.post(
        "/workouts/sync",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "sessions": [
                {
                    "external_id": "hc-ex-1",
                    "activity_type": "running",
                    "start_time": "2026-01-01T07:00:00Z",
                    "end_time": "2026-01-01T07:30:00Z",
                }
            ]
        },
    )
    assert response.status_code == 401
