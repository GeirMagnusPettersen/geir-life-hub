"""Adapter/client for a self-hosted KitchenOwl instance.

Per the project brief, Life Hub does NOT duplicate KitchenOwl's recipe /
shopping-list data model locally. Instead this module is an HTTP client that
talks to KitchenOwl's own API (JWT auth, household scoped) so it can be wired
in without any local schema changes.

KitchenOwl's real routes (verified against the TomBursch/kitchenowl backend
source, since KitchenOwl does not publish a stable API spec) are mounted
under `/api` and look like this:

- ``POST /api/auth`` with ``{username, password}`` -> ``{access_token,
  refresh_token, ...}``. Note this is *not* ``/auth/login``.
- ``GET /api/household/<household_id>`` -> household details, including
  ``default_shopping_list.id`` - KitchenOwl shopping lists are addressed by
  their own id, not the household id, so this client resolves and caches
  that id lazily on first use.
- ``GET /api/shoppinglist/<shoppinglist_id>/items`` / ``POST
  /api/shoppinglist/<shoppinglist_id>/add-item-by-name`` / ``DELETE
  /api/shoppinglist/<shoppinglist_id>/item`` (body: ``{"item_id": ...}``) -
  shopping list item operations live on a top-level ``/shoppinglist``
  resource, *not* nested under ``/household/<id>/...``. KitchenOwl has no
  "uncheck" endpoint: checking an item off is modeled as removing it from
  the list.
- ``GET /api/household/<household_id>/recipe`` (singular) lists recipes for
  the household.

This client intentionally exposes a small, explicit surface (read recipes,
read/write the shopping list) rather than a full SDK.
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
        # KitchenOwl shopping lists are addressed by their own id (not the
        # household id); resolved lazily via the household lookup and
        # cached for the lifetime of this client instance.
        self._shopping_list_id: int | None = None
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
            "/auth",
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

    def _get_shopping_list_id(self) -> int:
        """Resolve (and cache) the household's default shopping list id.

        KitchenOwl shopping lists have their own id distinct from the
        household id, so this must be looked up via the household before any
        shopping-list item endpoint can be called.
        """
        if self._shopping_list_id is not None:
            return self._shopping_list_id
        household_id = self._require_household_id()
        response = self._request("GET", f"/household/{household_id}")
        payload = response.json()
        shopping_list_id = payload["default_shopping_list"]["id"]
        self._shopping_list_id = shopping_list_id
        return shopping_list_id

    def get_shopping_list_items(self) -> list[dict[str, Any]]:
        shopping_list_id = self._get_shopping_list_id()
        response = self._request("GET", f"/shoppinglist/{shopping_list_id}/items")
        return response.json()

    def add_shopping_list_item(
        self, name: str, *, description: str | None = None
    ) -> dict[str, Any]:
        """Add a single item to the household's default shopping list by name."""
        shopping_list_id = self._get_shopping_list_id()
        payload: dict[str, Any] = {"name": name}
        if description:
            payload["description"] = description
        response = self._request(
            "POST", f"/shoppinglist/{shopping_list_id}/add-item-by-name", json=payload
        )
        return response.json()

    def set_shopping_list_item_checked(self, item_id: int, checked: bool) -> dict[str, Any]:
        """Check an item off the shopping list.

        KitchenOwl has no "uncheck" operation - checking an item off removes
        it from the active shopping list (its history is kept separately).
        Only ``checked=True`` is supported; re-adding an item is done via
        :meth:`add_shopping_list_item`.
        """
        if not checked:
            raise NotImplementedError(
                "KitchenOwl has no endpoint to un-check a shopping list item; "
                "use add_shopping_list_item to add it back instead."
            )
        shopping_list_id = self._get_shopping_list_id()
        response = self._request(
            "DELETE",
            f"/shoppinglist/{shopping_list_id}/item",
            json={"item_id": item_id},
        )
        return response.json()

    def clear_shopping_list(self) -> int:
        """Remove every item currently on the shopping list.

        KitchenOwl has no bulk "clear" endpoint, so this fetches the current
        items and removes them one by one via the existing per-item delete
        used by :meth:`set_shopping_list_item_checked`. Returns the number of
        items removed.
        """
        items = self.get_shopping_list_items()
        removed = 0
        for item in items:
            item_id = item.get("id")
            if item_id is None:
                continue
            self.set_shopping_list_item_checked(item_id, True)
            removed += 1
        return removed

    def get_recipes(self) -> list[dict[str, Any]]:
        household_id = self._require_household_id()
        response = self._request("GET", f"/household/{household_id}/recipe")
        return response.json()
