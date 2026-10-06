"""Adapter/client for a self-hosted KitchenOwl instance.

Per the project brief, Life Hub does NOT duplicate KitchenOwl's recipe /
shopping-list data model locally. Instead this module is a thin HTTP client
that talks to KitchenOwl's own API (JWT auth, household/group scoped) so it
can be wired in later without any local schema changes.

KitchenOwl's auth flow (as of the versions this was reviewed against) is
roughly: POST /auth/login {username, password} -> {access_token, refresh_token},
then Bearer-authenticated requests against /household/<id>/... endpoints
scoped to the configured household/group. This client intentionally exposes a
small, explicit surface rather than a full SDK.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings, get_settings


class KitchenOwlNotConfiguredError(RuntimeError):
    """Raised when the adapter is used without KITCHENOWL_BASE_URL configured."""


class KitchenOwlClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._access_token: str | None = None

    @property
    def is_configured(self) -> bool:
        return bool(self._settings.kitchenowl_base_url)

    def _require_configured(self) -> str:
        if not self._settings.kitchenowl_base_url:
            raise KitchenOwlNotConfiguredError(
                "KITCHENOWL_BASE_URL is not set; the KitchenOwl integration is disabled."
            )
        return self._settings.kitchenowl_base_url.rstrip("/")

    def _authenticate(self, client: httpx.Client) -> str:
        if self._access_token:
            return self._access_token
        if not (self._settings.kitchenowl_username and self._settings.kitchenowl_password):
            raise KitchenOwlNotConfiguredError(
                "KITCHENOWL_USERNAME/KITCHENOWL_PASSWORD are not set."
            )
        response = client.post(
            "/auth/login",
            json={
                "username": self._settings.kitchenowl_username,
                "password": self._settings.kitchenowl_password,
            },
        )
        response.raise_for_status()
        token = response.json()["access_token"]
        self._access_token = token
        return token

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        base_url = self._require_configured()
        with httpx.Client(base_url=base_url, timeout=10.0) as client:
            token = self._authenticate(client)
            headers = kwargs.pop("headers", {})
            headers["Authorization"] = f"Bearer {token}"
            return client.request(method, path, headers=headers, **kwargs)

    def get_shopping_list_items(self) -> list[dict[str, Any]]:
        household_id = self._settings.kitchenowl_household_id
        if not household_id:
            raise KitchenOwlNotConfiguredError("KITCHENOWL_HOUSEHOLD_ID is not set.")
        response = self._request("GET", f"/household/{household_id}/shoppinglist/1/items")
        response.raise_for_status()
        return response.json()

    def get_recipes(self) -> list[dict[str, Any]]:
        household_id = self._settings.kitchenowl_household_id
        if not household_id:
            raise KitchenOwlNotConfiguredError("KITCHENOWL_HOUSEHOLD_ID is not set.")
        response = self._request("GET", f"/household/{household_id}/recipes")
        response.raise_for_status()
        return response.json()
