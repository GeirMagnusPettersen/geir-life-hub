from __future__ import annotations

import json

import httpx

from app.config import Settings
from app.main import app
from app.routers.ai_import import get_kitchenowl_client
from app.integrations.kitchenowl import KitchenOwlClient


def test_import_requires_auth(client):
    response = client.post(
        "/import/ai",
        json={"source_model": "copilot", "items": [{"domain": "weight", "data": {"weight_kg": 80.0}}]},
    )
    assert response.status_code == 401


def test_import_weight_entry(auth_client):
    response = auth_client.post(
        "/import/ai",
        json={
            "source_model": "copilot",
            "items": [{"domain": "weight", "data": {"weight_kg": 81.5, "note": "from screenshot"}}],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["imported"] == 1
    assert body["skipped"] == 0
    assert body["results"][0]["status"] == "created"

    weight_response = auth_client.get("/weight")
    entries = weight_response.json()
    assert len(entries) == 1
    assert entries[0]["weight_kg"] == 81.5
    assert entries[0]["source"] == "ai_import:copilot"


def test_import_fluid_coffee_health_observation(auth_client):
    response = auth_client.post(
        "/import/ai",
        json={
            "source_model": "ChatGPT",
            "items": [
                {"domain": "fluid", "data": {"amount_ml": 500, "fluid_type": "water"}},
                {"domain": "coffee", "data": {"cups": 2}},
                {
                    "domain": "health_observation",
                    "data": {"category": "headache", "description": "mild", "severity": 2},
                },
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["imported"] == 3
    assert body["skipped"] == 0

    assert auth_client.get("/fluids").json()[0]["source"] == "ai_import:chatgpt"
    assert auth_client.get("/coffee").json()[0]["source"] == "ai_import:chatgpt"
    assert auth_client.get("/health-observations").json()[0]["source"] == "ai_import:chatgpt"


def test_import_sleep_activity_upserts_existing_date(auth_client):
    first = auth_client.post(
        "/import/ai",
        json={
            "source_model": "copilot",
            "items": [
                {
                    "domain": "sleep_activity",
                    "data": {"summary_date": "2024-05-01", "sleep_minutes": 400, "steps": 1000},
                }
            ],
        },
    )
    assert first.json()["imported"] == 1

    second = auth_client.post(
        "/import/ai",
        json={
            "source_model": "copilot",
            "items": [
                {
                    "domain": "sleep_activity",
                    "data": {"summary_date": "2024-05-01", "sleep_minutes": 420, "steps": 1200},
                }
            ],
        },
    )
    assert second.status_code == 200
    assert second.json()["imported"] == 1

    history = auth_client.get("/sleep-activity").json()
    matching = [e for e in history if e["summary_date"] == "2024-05-01"]
    assert len(matching) == 1
    assert matching[0]["sleep_minutes"] == 420
    assert matching[0]["steps"] == 1200
    assert matching[0]["source"] == "ai_import:copilot"


def test_import_batch_partial_failure(auth_client):
    response = auth_client.post(
        "/import/ai",
        json={
            "source_model": "copilot",
            "items": [
                {"domain": "weight", "data": {"weight_kg": 82.0}},
                {"domain": "weight", "data": {"weight_kg": -5}},
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["imported"] == 1
    assert body["skipped"] == 1
    assert body["results"][0]["status"] == "created"
    assert body["results"][1]["status"] == "error"
    assert body["results"][1]["detail"]


def test_import_shopping_list_item_without_kitchenowl_configured_is_a_per_item_error(auth_client, monkeypatch):
    monkeypatch.delenv("KITCHENOWL_BASE_URL", raising=False)
    response = auth_client.post(
        "/import/ai",
        json={
            "source_model": "copilot",
            "items": [{"domain": "shopping_list_item", "data": {"name": "Milk"}}],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["imported"] == 0
    assert body["skipped"] == 1
    assert body["results"][0]["status"] == "error"


def test_import_shopping_list_item_forwards_to_kitchenowl(auth_client, monkeypatch):
    monkeypatch.setenv("SESSION_SECRET_KEY", "test-only-secret")
    monkeypatch.setenv("KITCHENOWL_BASE_URL", "https://kitchenowl.example.test")
    monkeypatch.setenv("KITCHENOWL_USERNAME", "geir")
    monkeypatch.setenv("KITCHENOWL_PASSWORD", "hunter2-hunter2")
    monkeypatch.setenv("KITCHENOWL_HOUSEHOLD_ID", "1")
    settings = Settings()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth":
            return httpx.Response(200, json={"access_token": "tok-1"})
        if request.url.path == "/household/1":
            return httpx.Response(200, json={"id": 1, "default_shopping_list": {"id": 1}})
        if request.url.path == "/shoppinglist/1/add-item-by-name":
            assert json.loads(request.content) == {"name": "Milk", "description": "whole, 1L"}
            return httpx.Response(200, json={"id": 9, "name": "Milk"})
        raise AssertionError(f"unexpected request: {request.method} {request.url.path}")

    test_client = KitchenOwlClient(settings=settings, transport=httpx.MockTransport(handler))
    app.dependency_overrides[get_kitchenowl_client] = lambda: test_client
    try:
        response = auth_client.post(
            "/import/ai",
            json={
                "source_model": "copilot",
                "items": [
                    {
                        "domain": "shopping_list_item",
                        "data": {"name": "Milk", "description": "whole, 1L"},
                    }
                ],
            },
        )
    finally:
        del app.dependency_overrides[get_kitchenowl_client]

    assert response.status_code == 200
    body = response.json()
    assert body["imported"] == 1
    assert body["results"][0]["id"] == "9"
