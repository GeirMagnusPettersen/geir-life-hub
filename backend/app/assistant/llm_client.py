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
    ) -> dict[str, Any]:
        """Call the chat-completions endpoint and return the first choice's message.

        Returns the raw ``message`` object from the API response, e.g.
        ``{"role": "assistant", "content": "...", "tool_calls": [...]}``.
        """
        base_url = self._require_configured()
        payload: dict[str, Any] = {
            "model": self._settings.assistant_model,
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
        response.raise_for_status()
        body = response.json()
        try:
            return body["choices"][0]["message"]
        except (KeyError, IndexError) as exc:
            raise AssistantProviderError(
                f"Unexpected response shape from assistant provider: {body!r}"
            ) from exc
