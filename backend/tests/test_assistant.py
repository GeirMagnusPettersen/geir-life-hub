from __future__ import annotations

import json

import httpx
import pytest

from app.assistant.chat import ChatMessage, run_chat_turn
from app.assistant.llm_client import AssistantNotConfiguredError, AssistantProviderError, LlmClient
from app.config import Settings
from app.integrations.kitchenowl import KitchenOwlClient
from app.main import app
from app.routers.assistant import get_kitchenowl_client, get_llm_client


def _settings_without_assistant(monkeypatch) -> Settings:
    monkeypatch.delenv("ASSISTANT_API_KEY", raising=False)
    monkeypatch.setenv("SESSION_SECRET_KEY", "test-only-secret")
    return Settings()


def _settings_with_assistant(monkeypatch) -> Settings:
    monkeypatch.setenv("SESSION_SECRET_KEY", "test-only-secret")
    monkeypatch.setenv("ASSISTANT_API_KEY", "sk-test-123")
    monkeypatch.setenv("ASSISTANT_BASE_URL", "https://llm.example.test/v1")
    monkeypatch.setenv("ASSISTANT_MODEL", "test-model")
    return Settings()


def _kitchenowl_settings(monkeypatch) -> Settings:
    monkeypatch.setenv("KITCHENOWL_BASE_URL", "https://kitchenowl.example.test")
    monkeypatch.setenv("KITCHENOWL_USERNAME", "geir")
    monkeypatch.setenv("KITCHENOWL_PASSWORD", "hunter2-hunter2")
    monkeypatch.setenv("KITCHENOWL_HOUSEHOLD_ID", "1")
    return Settings()


# --- LlmClient ---------------------------------------------------------


def test_llm_client_reports_not_configured_when_no_api_key(monkeypatch):
    settings = _settings_without_assistant(monkeypatch)
    client = LlmClient(settings=settings)
    assert client.is_configured is False
    with pytest.raises(AssistantNotConfiguredError):
        client.chat_completion([{"role": "user", "content": "hei"}])


def test_llm_client_posts_chat_completion_and_parses_message(monkeypatch):
    settings = _settings_with_assistant(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer sk-test-123"
        body = json.loads(request.content)
        assert body["model"] == "test-model"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"role": "assistant", "content": "Hei!"}}]},
        )

    client = LlmClient(settings=settings, transport=httpx.MockTransport(handler))
    message = client.chat_completion([{"role": "user", "content": "hei"}])

    assert message == {"role": "assistant", "content": "Hei!"}


def test_llm_client_raises_provider_error_on_unexpected_shape(monkeypatch):
    settings = _settings_with_assistant(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": True})

    client = LlmClient(settings=settings, transport=httpx.MockTransport(handler))
    with pytest.raises(AssistantProviderError):
        client.chat_completion([{"role": "user", "content": "hei"}])


# --- run_chat_turn (tool-calling loop) ----------------------------------


class _StubLlmClient:
    """Returns a fixed sequence of chat-completion responses, in order."""

    def __init__(self, responses: list[dict]) -> None:
        self._responses = list(responses)
        self.seen_messages: list[list[dict]] = []

    def chat_completion(self, messages, *, tools=None):
        self.seen_messages.append(messages)
        return self._responses.pop(0)


def _kitchenowl_mock_client(monkeypatch, *, shopping_list_items: list[dict] | None = None) -> KitchenOwlClient:
    settings = _kitchenowl_settings(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth":
            return httpx.Response(200, json={"access_token": "tok-1"})
        if request.url.path == "/household/1":
            return httpx.Response(200, json={"id": 1, "default_shopping_list": {"id": 1}})
        if request.url.path == "/shoppinglist/1/add-item-by-name":
            return httpx.Response(200, json={"id": 1, "name": json.loads(request.content)["name"]})
        if request.url.path == "/shoppinglist/1/items":
            return httpx.Response(200, json=shopping_list_items or [])
        if request.url.path == "/shoppinglist/1/item":
            item_id = json.loads(request.content)["item_id"]
            return httpx.Response(200, json={"id": item_id})
        raise AssertionError(f"unexpected request: {request.method} {request.url.path}")

    return KitchenOwlClient(settings=settings, transport=httpx.MockTransport(handler))


def test_run_chat_turn_returns_plain_reply_when_no_tool_call(monkeypatch):
    llm = _StubLlmClient(
        [{"role": "assistant", "content": "Hva har du lyst på til middag?"}]
    )
    kitchenowl = _kitchenowl_mock_client(monkeypatch)

    result = run_chat_turn(
        [ChatMessage(role="user", content="Hva skal vi ha til middag?")],
        llm=llm,
        kitchenowl=kitchenowl,
    )

    assert result.reply == "Hva har du lyst på til middag?"
    assert result.added_items == []


def test_run_chat_turn_executes_tool_call_and_adds_items(monkeypatch):
    llm = _StubLlmClient(
        [
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "function": {
                            "name": "add_shopping_list_items",
                            "arguments": json.dumps({"items": ["500 g kjøttdeig", "Løk"]}),
                        },
                    }
                ],
            },
            {"role": "assistant", "content": "La til kjøttdeig og løk på handlelisten!"},
        ]
    )
    kitchenowl = _kitchenowl_mock_client(monkeypatch)

    result = run_chat_turn(
        [
            ChatMessage(role="user", content="La oss lage tacogryte"),
            ChatMessage(role="assistant", content="Høres bra ut! Skal jeg legge til ingrediensene?"),
            ChatMessage(role="user", content="Ja, legg det til handlelisten"),
        ],
        llm=llm,
        kitchenowl=kitchenowl,
    )

    assert result.reply == "La til kjøttdeig og løk på handlelisten!"
    assert [item.name for item in result.added_items] == ["500 g kjøttdeig", "Løk"]
    assert all(item.ok for item in result.added_items)

    # The tool-call message and the tool result must both be fed back to the
    # model before it is asked for the final reply.
    second_call_messages = llm.seen_messages[1]
    assert second_call_messages[-2]["tool_calls"][0]["id"] == "call_1"
    assert second_call_messages[-1]["role"] == "tool"
    assert second_call_messages[-1]["tool_call_id"] == "call_1"


def test_run_chat_turn_executes_clear_list_tool_call(monkeypatch):
    llm = _StubLlmClient(
        [
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "function": {"name": "clear_shopping_list", "arguments": "{}"},
                    }
                ],
            },
            {"role": "assistant", "content": "Tømte handlelisten!"},
        ]
    )
    kitchenowl = _kitchenowl_mock_client(
        monkeypatch,
        shopping_list_items=[{"id": 1, "name": "Melk"}, {"id": 2, "name": "Brød"}],
    )

    result = run_chat_turn(
        [ChatMessage(role="user", content="Tøm handlelisten")],
        llm=llm,
        kitchenowl=kitchenowl,
    )

    assert result.reply == "Tømte handlelisten!"
    assert result.cleared_list is True
    assert result.added_items == []

    second_call_messages = llm.seen_messages[1]
    assert second_call_messages[-2]["tool_calls"][0]["id"] == "call_1"
    assert second_call_messages[-1]["role"] == "tool"
    assert second_call_messages[-1]["tool_call_id"] == "call_1"


def test_run_chat_turn_raises_when_model_never_stops_calling_tools(monkeypatch):
    tool_call_message = {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "call_x",
                "function": {
                    "name": "add_shopping_list_items",
                    "arguments": json.dumps({"items": ["Melk"]}),
                },
            }
        ],
    }
    llm = _StubLlmClient([tool_call_message, tool_call_message, tool_call_message])
    kitchenowl = _kitchenowl_mock_client(monkeypatch)

    with pytest.raises(AssistantProviderError):
        run_chat_turn(
            [ChatMessage(role="user", content="Legg til melk")],
            llm=llm,
            kitchenowl=kitchenowl,
        )


# --- HTTP endpoints ------------------------------------------------------


def test_assistant_status_endpoint_reports_disabled(auth_client, monkeypatch):
    _settings_without_assistant(monkeypatch)
    response = auth_client.get("/assistant/status")
    assert response.status_code == 200
    assert response.json() == {"configured": False}


def test_assistant_chat_endpoint_returns_503_when_not_configured(auth_client, monkeypatch):
    _settings_without_assistant(monkeypatch)
    response = auth_client.post(
        "/assistant/chat", json={"messages": [{"role": "user", "content": "hei"}]}
    )
    assert response.status_code == 503


def test_assistant_chat_endpoint_adds_items_via_overridden_clients(auth_client, monkeypatch):
    llm = _StubLlmClient(
        [
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "function": {
                            "name": "add_shopping_list_items",
                            "arguments": json.dumps({"items": ["Pasta"]}),
                        },
                    }
                ],
            },
            {"role": "assistant", "content": "La til pasta!"},
        ]
    )
    kitchenowl = _kitchenowl_mock_client(monkeypatch)

    app.dependency_overrides[get_llm_client] = lambda: llm
    app.dependency_overrides[get_kitchenowl_client] = lambda: kitchenowl
    try:
        response = auth_client.post(
            "/assistant/chat",
            json={"messages": [{"role": "user", "content": "Legg til pasta på handlelisten"}]},
        )
    finally:
        del app.dependency_overrides[get_llm_client]
        del app.dependency_overrides[get_kitchenowl_client]

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "La til pasta!"
    assert body["added_items"] == [{"name": "Pasta", "ok": True, "detail": None}]
