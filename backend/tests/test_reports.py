from __future__ import annotations

import pytest


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

    assert body["trend_weeks"] == 4
    weekly_trend = summary["weekly_trend"]
    assert len(weekly_trend) == 4
    # Everything was logged "now", so it should land in the most recent bucket.
    current_bucket = weekly_trend[-1]
    assert current_bucket["avg_weight_kg"] == 80
    assert current_bucket["symptom_count"] == 1
    assert current_bucket["fluids_ml_per_day"] == pytest.approx(500 / 7)
    assert current_bucket["coffee_cups_per_day"] == pytest.approx(2 / 7)
    # Older buckets have nothing logged yet.
    for bucket in weekly_trend[:-1]:
        assert bucket["avg_weight_kg"] is None
        assert bucket["symptom_count"] == 0


def test_dashboard_weeks_query_param_controls_trend_length(auth_client):
    response = auth_client.get("/reports/dashboard", params={"weeks": 2})
    assert response.status_code == 200
    body = response.json()
    assert body["trend_weeks"] == 2
    assert len(body["users"][0]["weekly_trend"]) == 2


def test_dashboard_requires_authentication(client):
    response = client.get("/reports/dashboard")
    assert response.status_code == 401
