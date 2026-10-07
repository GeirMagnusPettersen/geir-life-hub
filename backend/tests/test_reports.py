from __future__ import annotations

from datetime import date, timedelta

import pytest

TODAY = date.today()


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


def test_dashboard_weekly_trend_includes_sleep_minutes_and_heart_rate(auth_client):
    auth_client.post(
        "/sleep-activity",
        json={
            "summary_date": TODAY.isoformat(),
            "sleep_minutes": 420,
            "steps": 8000,
            "resting_heart_rate": 52,
            "avg_heart_rate": 60,
        },
    )
    auth_client.post(
        "/sleep-activity",
        json={
            "summary_date": (TODAY - timedelta(days=1)).isoformat(),
            "sleep_minutes": 380,
            "steps": 7000,
            "resting_heart_rate": 54,
            "avg_heart_rate": 62,
        },
    )

    response = auth_client.get("/reports/dashboard")
    assert response.status_code == 200
    weekly_trend = response.json()["users"][0]["weekly_trend"]
    current_bucket = weekly_trend[-1]
    assert current_bucket["avg_sleep_minutes"] == pytest.approx((420 + 380) / 2)
    assert current_bucket["avg_resting_heart_rate"] == pytest.approx((52 + 54) / 2)
    for bucket in weekly_trend[:-1]:
        assert bucket["avg_sleep_minutes"] is None
        assert bucket["avg_resting_heart_rate"] is None


def test_dashboard_requires_authentication(client):
    response = client.get("/reports/dashboard")
    assert response.status_code == 401


def test_sleep_trend_returns_daily_points_across_users(client, db_session):
    from app.models import User
    from app.security import hash_password

    geir = User(
        username="geir",
        display_name="Geir",
        password_hash=hash_password("correct-horse-battery"),
    )
    kristin = User(
        username="kristin",
        display_name="Kristin",
        password_hash=hash_password("correct-horse-battery"),
    )
    db_session.add_all([geir, kristin])
    db_session.commit()
    db_session.refresh(geir)
    db_session.refresh(kristin)

    login = client.post(
        "/auth/login", json={"username": "geir", "password": "correct-horse-battery"}
    )
    assert login.status_code == 200

    client.post(
        "/sleep-activity",
        json={
            "summary_date": TODAY.isoformat(),
            "sleep_minutes": 420,
            "steps": 8000,
            "resting_heart_rate": 50,
            "avg_heart_rate": 58,
        },
    )

    # Simulate Kristin's data arriving via the device-token sync path by
    # inserting directly, since there's no auth_client for a second user here.
    from app.models import SleepActivitySummary

    db_session.add(
        SleepActivitySummary(
            user_id=kristin.id,
            summary_date=TODAY,
            sleep_minutes=400,
            steps=6000,
            resting_heart_rate=55,
            avg_heart_rate=64,
        )
    )
    db_session.commit()

    response = client.get("/reports/sleep-trend", params={"days": 30})
    assert response.status_code == 200
    body = response.json()
    assert body["period_days"] == 30
    assert len(body["points"]) == 2
    display_names = {point["display_name"] for point in body["points"]}
    assert display_names == {"Geir", "Kristin"}
    geir_point = next(p for p in body["points"] if p["display_name"] == "Geir")
    assert geir_point["sleep_minutes"] == 420
    assert geir_point["resting_heart_rate"] == 50
    assert geir_point["avg_heart_rate"] == 58


def test_sleep_trend_excludes_points_outside_window(auth_client):
    auth_client.post(
        "/sleep-activity",
        json={"summary_date": "2020-01-01", "sleep_minutes": 300, "steps": 1000},
    )

    response = auth_client.get("/reports/sleep-trend", params={"days": 7})
    assert response.status_code == 200
    assert response.json()["points"] == []


def test_sleep_trend_requires_authentication(client):
    response = client.get("/reports/sleep-trend")
    assert response.status_code == 401
