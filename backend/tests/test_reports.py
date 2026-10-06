from __future__ import annotations


def test_dashboard_report_aggregates_across_domains(auth_client):
    auth_client.post("/weight", json={"weight_kg": 80})
    auth_client.post("/fluids", json={"amount_ml": 300})
    auth_client.post("/fluids", json={"amount_ml": 200})
    auth_client.post("/coffee", json={"cups": 2})
    auth_client.post(
        "/health-observations",
        json={"category": "symptom", "description": "test"},
    )

    response = auth_client.get("/reports/dashboard")
    assert response.status_code == 200
    body = response.json()
    assert body["period_days"] == 7
    assert len(body["users"]) == 1

    summary = body["users"][0]
    assert summary["latest_weight_kg"] == 80
    assert summary["fluids_ml_total"] == 500
    assert summary["coffee_cups_total"] == 2
    assert summary["health_observation_count"] == 1


def test_dashboard_requires_authentication(client):
    response = client.get("/reports/dashboard")
    assert response.status_code == 401
