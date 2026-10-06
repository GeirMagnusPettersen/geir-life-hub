from __future__ import annotations

import pytest

from app.config import Settings
from app.integrations.kitchenowl import KitchenOwlClient, KitchenOwlNotConfiguredError


def _settings_without_kitchenowl(monkeypatch) -> Settings:
    monkeypatch.delenv("KITCHENOWL_BASE_URL", raising=False)
    monkeypatch.setenv("SESSION_SECRET_KEY", "test-only-secret")
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
