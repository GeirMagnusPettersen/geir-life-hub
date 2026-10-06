from __future__ import annotations


def test_create_and_list_weight_entry(auth_client):
    response = auth_client.post("/weight", json={"weight_kg": 82.5, "note": "morning"})
    assert response.status_code == 201
    body = response.json()
    assert body["weight_kg"] == 82.5
    assert body["note"] == "morning"

    response = auth_client.get("/weight")
    assert response.status_code == 200
    entries = response.json()
    assert len(entries) == 1
    assert entries[0]["weight_kg"] == 82.5


def test_weight_requires_authentication(client):
    response = client.post("/weight", json={"weight_kg": 80})
    assert response.status_code == 401


def test_weight_rejects_out_of_range_value(auth_client):
    response = auth_client.post("/weight", json={"weight_kg": -5})
    assert response.status_code == 422


def test_create_fluid_entry_defaults_to_water(auth_client):
    response = auth_client.post("/fluids", json={"amount_ml": 250})
    assert response.status_code == 201
    assert response.json()["fluid_type"] == "water"


def test_create_coffee_entry(auth_client):
    response = auth_client.post("/coffee", json={"cups": 1.5})
    assert response.status_code == 201
    assert response.json()["cups"] == 1.5


def test_create_health_observation(auth_client):
    response = auth_client.post(
        "/health-observations",
        json={"category": "headache", "description": "mild", "severity": 2},
    )
    assert response.status_code == 201
    assert response.json()["severity"] == 2


def test_sleep_activity_upsert_by_date(auth_client):
    payload = {"summary_date": "2026-01-01", "sleep_minutes": 420, "steps": 8000}
    response = auth_client.post("/sleep-activity", json=payload)
    assert response.status_code == 201
    first_id = response.json()["id"]

    payload["sleep_minutes"] = 450
    response = auth_client.post("/sleep-activity", json=payload)
    assert response.status_code == 201
    assert response.json()["id"] == first_id
    assert response.json()["sleep_minutes"] == 450

    response = auth_client.get("/sleep-activity")
    assert len(response.json()) == 1
