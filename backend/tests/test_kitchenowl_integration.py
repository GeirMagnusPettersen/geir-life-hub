from __future__ import annotations

import json

import httpx
import pytest

from app.config import Settings
from app.integrations.kitchenowl import KitchenOwlClient, KitchenOwlNotConfiguredError


def _settings_without_kitchenowl(monkeypatch) -> Settings:
    monkeypatch.delenv("KITCHENOWL_BASE_URL", raising=False)
    monkeypatch.setenv("SESSION_SECRET_KEY", "test-only-secret")
    return Settings()


def _settings_with_kitchenowl(monkeypatch) -> Settings:
    monkeypatch.setenv("SESSION_SECRET_KEY", "test-only-secret")
    monkeypatch.setenv("KITCHENOWL_BASE_URL", "https://kitchenowl.example.test")
    monkeypatch.setenv("KITCHENOWL_USERNAME", "geir")
    monkeypatch.setenv("KITCHENOWL_PASSWORD", "hunter2-hunter2")
    monkeypatch.setenv("KITCHENOWL_HOUSEHOLD_ID", "1")
    return Settings()


def test_client_reports_not_configured_when_base_url_missing(monkeypatch):
    settings = _settings_without_kitchenowl(monkeypatch)
    client = KitchenOwlClient(settings=settings)
    assert client.is_configured is False


def test_client_raises_when_fetching_without_configuration(monkeypatch):
    settings = _settings_without_kitchenowl(monkeypatch)
    client = KitchenOwlClient(settings=settings)
    with pytest.raises(KitchenOwlNotConfiguredError):
        client.get_shopping_list_items()


def test_status_endpoint_reports_disabled_integration(auth_client):
    response = auth_client.get("/integrations/kitchenowl/status")
    assert response.status_code == 200
    assert response.json() == {"configured": False}


def test_shopping_list_endpoint_returns_503_when_not_configured(auth_client):
    response = auth_client.get("/integrations/kitchenowl/shopping-list")
    assert response.status_code == 503


# --- Real HTTP client, against a mocked transport (no network access) ------


def test_client_logs_in_and_fetches_shopping_list_items(monkeypatch):
    settings = _settings_with_kitchenowl(monkeypatch)
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.path == "/auth/login":
            assert request.method == "POST"
            assert json.loads(request.content) == {"username": "geir", "password": "hunter2-hunter2"}
            return httpx.Response(200, json={"access_token": "tok-1", "refresh_token": "ref-1"})
        if request.url.path == "/household/1/shoppinglist/1/items":
            assert request.headers["Authorization"] == "Bearer tok-1"
            return httpx.Response(200, json=[{"id": 1, "name": "Milk"}])
        raise AssertionError(f"unexpected request: {request.method} {request.url.path}")

    client = KitchenOwlClient(settings=settings, transport=httpx.MockTransport(handler))
    items = client.get_shopping_list_items()

    assert items == [{"id": 1, "name": "Milk"}]
    assert [c.url.path for c in calls] == ["/auth/login", "/household/1/shoppinglist/1/items"]


def test_client_caches_access_token_across_calls(monkeypatch):
    settings = _settings_with_kitchenowl(monkeypatch)
    login_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal login_calls
        if request.url.path == "/auth/login":
            login_calls += 1
            return httpx.Response(200, json={"access_token": "tok-1"})
        return httpx.Response(200, json=[])

    client = KitchenOwlClient(settings=settings, transport=httpx.MockTransport(handler))
    client.get_shopping_list_items()
    client.get_recipes()

    assert login_calls == 1


def test_client_re_logs_in_once_on_401(monkeypatch):
    settings = _settings_with_kitchenowl(monkeypatch)
    login_calls = 0
    tokens_seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal login_calls
        if request.url.path == "/auth/login":
            login_calls += 1
            return httpx.Response(200, json={"access_token": f"tok-{login_calls}"})
        if request.url.path == "/household/1/recipes":
            auth_header = request.headers["Authorization"]
            tokens_seen.append(auth_header)
            if auth_header == "Bearer tok-1":
                return httpx.Response(401, json={"detail": "expired"})
            return httpx.Response(200, json=[{"id": 1, "name": "Soup"}])
        raise AssertionError(f"unexpected request: {request.method} {request.url.path}")

    client = KitchenOwlClient(settings=settings, transport=httpx.MockTransport(handler))
    recipes = client.get_recipes()

    assert recipes == [{"id": 1, "name": "Soup"}]
    assert login_calls == 2
    assert tokens_seen == ["Bearer tok-1", "Bearer tok-2"]


def test_client_adds_shopping_list_item_by_name(monkeypatch):
    settings = _settings_with_kitchenowl(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/login":
            return httpx.Response(200, json={"access_token": "tok-1"})
        if request.url.path == "/household/1/shoppinglist/1/item-by-name":
            assert request.method == "POST"
            assert json.loads(request.content) == {"name": "Eggs", "description": "dozen"}
            return httpx.Response(200, json={"id": 2, "name": "Eggs"})
        raise AssertionError(f"unexpected request: {request.method} {request.url.path}")

    client = KitchenOwlClient(settings=settings, transport=httpx.MockTransport(handler))
    result = client.add_shopping_list_item("Eggs", description="dozen")

    assert result == {"id": 2, "name": "Eggs"}


def test_client_checks_off_shopping_list_item(monkeypatch):
    settings = _settings_with_kitchenowl(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/login":
            return httpx.Response(200, json={"access_token": "tok-1"})
        if request.url.path == "/household/1/shoppinglist/1/item/7":
            assert request.method == "PUT"
            assert json.loads(request.content) == {"checked": True}
            return httpx.Response(200, json={"id": 7, "checked": True})
        raise AssertionError(f"unexpected request: {request.method} {request.url.path}")

    client = KitchenOwlClient(settings=settings, transport=httpx.MockTransport(handler))
    result = client.set_shopping_list_item_checked(7, True)

    assert result == {"id": 7, "checked": True}


def test_client_raises_when_household_id_missing(monkeypatch):
    settings = _settings_with_kitchenowl(monkeypatch)
    monkeypatch.delenv("KITCHENOWL_HOUSEHOLD_ID", raising=False)
    settings = Settings()

    client = KitchenOwlClient(settings=settings)
    with pytest.raises(KitchenOwlNotConfiguredError):
        client.get_shopping_list_items()


def test_client_propagates_http_errors(monkeypatch):
    settings = _settings_with_kitchenowl(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/login":
            return httpx.Response(200, json={"access_token": "tok-1"})
        return httpx.Response(500, json={"detail": "boom"})

    client = KitchenOwlClient(settings=settings, transport=httpx.MockTransport(handler))
    with pytest.raises(httpx.HTTPStatusError):
        client.get_recipes()
