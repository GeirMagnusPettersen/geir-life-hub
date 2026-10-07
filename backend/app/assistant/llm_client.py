"""Thin client for an OpenAI-compatible chat-completions API.

This is deliberately not a provider SDK: it speaks the widely-supported
``POST /chat/completions`` shape (OpenAI, Azure OpenAI via a compatible
gateway, and most local/self-hosted model servers implement this), so the
provider is swappable purely via ``ASSISTANT_BASE_URL`` /
``ASSISTANT_API_KEY`` / ``ASSISTANT_MODEL`` env vars without any code
changes.

The only feature this client depends on is "tool calling" (aka function
calling): the model can ask the caller to invoke a named tool with JSON
arguments instead of (or in addition to) replying in plain text. That is
how the meal-planning assistant turns a conversation into concrete
shopping-list writes, see ``app.assistant.chat``.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings, get_settings


class AssistantNotConfiguredError(RuntimeError):
    """Raised when the assistant is used without ASSISTANT_API_KEY configured."""


class AssistantProviderError(RuntimeError):
    """Raised when the upstream LLM API returns an unexpected/error response."""


class LlmClient:
    def __init__(
        self,
        settings: Settings | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        # Only ever set by tests, to inject a mock transport; production
        # code always talks over the real network.
        self._transport = transport

    @property
    def is_configured(self) -> bool:
        return bool(self._settings.assistant_api_key)

    def _require_configured(self) -> str:
        if not self._settings.assistant_api_key:
            raise AssistantNotConfiguredError(
                "ASSISTANT_API_KEY is not set; the meal-planning assistant is disabled."
            )
        return self._settings.assistant_base_url.rstrip("/")

    def chat_completion(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        """Call the chat-completions endpoint and return the first choice's message.

        Returns the raw ``message`` object from the API response, e.g.
        ``{"role": "assistant", "content": "...", "tool_calls": [...]}``.

        ``model`` overrides ``ASSISTANT_MODEL`` for this call only, used to
        route image-bearing turns to a separate vision-capable model (see
        ``ASSISTANT_VISION_MODEL`` / ``app.assistant.chat``).
        """
        base_url = self._require_configured()
        payload: dict[str, Any] = {
            "model": model or self._settings.assistant_model,
            "messages": messages,
        }
        if tools:
            payload["tools"] = tools

        with httpx.Client(base_url=base_url, timeout=30.0, transport=self._transport) as client:
            response = client.post(
                "/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {self._settings.assistant_api_key}"},
            )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            # Surface the provider's own error message (e.g. Groq's
            # "model_not_found") instead of a bare status code, so a bad
            # model name/account-access issue is distinguishable in logs
            # and in the user-facing error from a plain network failure.
            detail = self._extract_provider_error(response)
            raise AssistantProviderError(
                f"Assistant provider returned {response.status_code} for model "
                f"'{payload['model']}': {detail}"
            ) from exc
        body = response.json()
        try:
            return body["choices"][0]["message"]
        except (KeyError, IndexError) as exc:
            raise AssistantProviderError(
                f"Unexpected response shape from assistant provider: {body!r}"
            ) from exc

    @staticmethod
    def _extract_provider_error(response: httpx.Response) -> str:
        """Best-effort extraction of a human-readable message from an
        OpenAI-compatible error body, e.g. ``{"error": {"message": "..."}}``.
        Falls back to the raw response text if the shape is unexpected.
        """
        try:
            error_body = response.json()
            message = error_body.get("error", {}).get("message")
            if message:
                return str(message)
        except (ValueError, AttributeError):
            pass
        return response.text[:300]
