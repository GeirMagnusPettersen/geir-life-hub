"""Adapter/client for a self-hosted KitchenOwl instance.

Per the project brief, Life Hub does NOT duplicate KitchenOwl's recipe /
shopping-list data model locally. Instead this module is an HTTP client that
talks to KitchenOwl's own API (JWT auth, household/group scoped) so it can be
wired in without any local schema changes.

KitchenOwl's auth flow is roughly: POST /auth/login {username, password} ->
{access_token, refresh_token}, then Bearer-authenticated requests against
/household/<id>/... endpoints scoped to the configured household/group. This
client intentionally exposes a small, explicit surface (read recipes, read/
write the shopping list) rather than a full SDK.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings, get_settings


class KitchenOwlNotConfiguredError(RuntimeError):
    """Raised when the adapter is used without KITCHENOWL_BASE_URL configured."""


class KitchenOwlClient:
    def __init__(
        self,
        settings: Settings | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        # Only ever set by tests, to inject a mock transport; production
        # code always talks over the real network.
        self._transport = transport

    @property
    def is_configured(self) -> bool:
        return bool(self._settings.kitchenowl_base_url)

    def _require_configured(self) -> str:
        if not self._settings.kitchenowl_base_url:
            raise KitchenOwlNotConfiguredError(
                "KITCHENOWL_BASE_URL is not set; the KitchenOwl integration is disabled."
            )
        return self._settings.kitchenowl_base_url.rstrip("/")

    def _require_household_id(self) -> str:
        household_id = self._settings.kitchenowl_household_id
        if not household_id:
            raise KitchenOwlNotConfiguredError("KITCHENOWL_HOUSEHOLD_ID is not set.")
        return household_id

    def _client(self) -> httpx.Client:
        base_url = self._require_configured()
        return httpx.Client(base_url=base_url, timeout=10.0, transport=self._transport)

    def _login(self, client: httpx.Client) -> str:
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
        payload = response.json()
        self._access_token = payload["access_token"]
        self._refresh_token = payload.get("refresh_token")
        return self._access_token

    def _authenticate(self, client: httpx.Client) -> str:
        if self._access_token:
            return self._access_token
        return self._login(client)

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        with self._client() as client:
            token = self._authenticate(client)
            headers = kwargs.pop("headers", {})
            headers["Authorization"] = f"Bearer {token}"
            response = client.request(method, path, headers=headers, **kwargs)

            # KitchenOwl access tokens are short-lived JWTs. If ours expired
            # or was otherwise rejected, drop the cached token and log in
            # again once before giving up - this keeps the adapter usable
            # across long-running processes without implementing a separate
            # refresh-token flow.
            if response.status_code == 401:
                self._access_token = None
                token = self._login(client)
                headers["Authorization"] = f"Bearer {token}"
                response = client.request(method, path, headers=headers, **kwargs)

            response.raise_for_status()
            return response

    def get_shopping_list_items(self) -> list[dict[str, Any]]:
        household_id = self._require_household_id()
        response = self._request("GET", f"/household/{household_id}/shoppinglist/1/items")
        return response.json()

    def add_shopping_list_item(
        self, name: str, *, description: str | None = None
    ) -> dict[str, Any]:
        """Add a single item to the household's (first) shopping list by name."""
        household_id = self._require_household_id()
        payload: dict[str, Any] = {"name": name}
        if description:
            payload["description"] = description
        response = self._request(
            "POST", f"/household/{household_id}/shoppinglist/1/item-by-name", json=payload
        )
        return response.json()

    def set_shopping_list_item_checked(self, item_id: int, checked: bool) -> dict[str, Any]:
        """Mark an existing shopping list item as checked/unchecked."""
        household_id = self._require_household_id()
        response = self._request(
            "PUT",
            f"/household/{household_id}/shoppinglist/1/item/{item_id}",
            json={"checked": checked},
        )
        return response.json()

    def get_recipes(self) -> list[dict[str, Any]]:
        household_id = self._require_household_id()
        response = self._request("GET", f"/household/{household_id}/recipes")
        return response.json()
