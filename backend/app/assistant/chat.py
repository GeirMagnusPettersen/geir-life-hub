"""Meal-planning assistant: turns a conversation about a dish into shopping
list writes.

This is the "core product goal" feature: the user discusses a meal/recipe
with an AI assistant, and when they decide on ingredients, the assistant
calls a tool to push those items straight into the household's KitchenOwl
shopping list via the existing adapter (``app.integrations.kitchenowl``) -
no local recipe/ingredient model is introduced, per the project brief's
"don't duplicate KitchenOwl's data model" rule.

Design (chosen autonomously, no chat UI/provider was specified by the
user): a single stateless ``POST /assistant/chat`` endpoint. The frontend
keeps the conversation history client-side and resends the full list of
messages each turn; the backend has no per-conversation server-side state
to manage. The assistant only writes to the shopping list when the model
itself decides to call the ``add_shopping_list_items`` tool (per the system
prompt, that should only happen once the user has actually asked for it),
so the user stays in control of what gets added.
"""
from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.assistant.llm_client import AssistantProviderError, LlmClient
from app.integrations.kitchenowl import KitchenOwlClient, KitchenOwlNotConfiguredError

SYSTEM_PROMPT = (
    "Du er en hjelpsom matlagingsassistent i Geir Life Hub, en husholdnings-app for "
    "Geir og Kristin. Diskuter middagsideer, oppskrifter og ingredienser med "
    "brukeren på en uformell, kortfattet måte.\n\n"
    "Når brukeren har bestemt seg for en rett og eksplisitt ber om å legge "
    "ingrediensene til handlelisten (f.eks. 'legg det til handlelisten', "
    "'putt dette på listen'), kall funksjonen add_shopping_list_items med en "
    "liste av konkrete, handlelisteklare varenavn på norsk. Inkluder mengde når "
    "det er naturlig (f.eks. '500 g kjøttdeig', '1 boks hermetiske tomater'). "
    "Ikke kall funksjonen før brukeren faktisk har bedt om det, og ikke "
    "dupliser varer brukeren allerede har nevnt at de har hjemme.\n\n"
    "Etter at du har kalt funksjonen, bekreft kort på norsk hvilke varer som "
    "ble lagt til."
)

_ADD_ITEMS_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "add_shopping_list_items",
        "description": (
            "Legg en eller flere ingredienser/varer til husholdningens "
            "KitchenOwl-handleliste."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Varenavn, ev. med mengde, klare for handlelisten.",
                },
            },
            "required": ["items"],
        },
    },
}

_TOOL_NAME = "add_shopping_list_items"
_MAX_TOOL_ITERATIONS = 3


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class AddedShoppingListItem(BaseModel):
    name: str
    ok: bool
    detail: str | None = None


class ChatReply(BaseModel):
    reply: str
    added_items: list[AddedShoppingListItem] = Field(default_factory=list)


def _add_items_to_shopping_list(
    kitchenowl: KitchenOwlClient, items: list[str]
) -> list[AddedShoppingListItem]:
    added: list[AddedShoppingListItem] = []
    for raw_name in items:
        name = raw_name.strip()
        if not name:
            continue
        try:
            kitchenowl.add_shopping_list_item(name)
            added.append(AddedShoppingListItem(name=name, ok=True))
        except KitchenOwlNotConfiguredError as exc:
            added.append(AddedShoppingListItem(name=name, ok=False, detail=str(exc)))
        except Exception as exc:  # noqa: BLE001 - surface any adapter failure per item
            added.append(AddedShoppingListItem(name=name, ok=False, detail=str(exc)))
    return added


def run_chat_turn(
    history: list[ChatMessage],
    *,
    llm: LlmClient,
    kitchenowl: KitchenOwlClient,
) -> ChatReply:
    """Run one turn of the meal-planning assistant conversation.

    Sends the conversation to the LLM with the shopping-list tool available,
    executes any tool call(s) the model makes against the live KitchenOwl
    shopping list, feeds the tool results back, and returns the model's
    final natural-language reply plus a record of what was actually added.
    """
    messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend({"role": m.role, "content": m.content} for m in history)

    added_items: list[AddedShoppingListItem] = []

    for _ in range(_MAX_TOOL_ITERATIONS):
        message = llm.chat_completion(messages, tools=[_ADD_ITEMS_TOOL])
        tool_calls = message.get("tool_calls") or []

        if not tool_calls:
            return ChatReply(reply=message.get("content") or "", added_items=added_items)

        # Echo the assistant's tool-call message back into the transcript
        # (required by the OpenAI-compatible protocol) before answering it.
        messages.append(message)

        for call in tool_calls:
            function = call.get("function", {})
            name = function.get("name")
            try:
                arguments = json.loads(function.get("arguments") or "{}")
            except json.JSONDecodeError:
                arguments = {}

            if name == _TOOL_NAME:
                items = [str(i) for i in arguments.get("items", [])]
                result = _add_items_to_shopping_list(kitchenowl, items)
                added_items.extend(result)
                tool_content = json.dumps(
                    {"added": [a.model_dump() for a in result]}, ensure_ascii=False
                )
            else:
                tool_content = json.dumps({"error": f"unknown tool '{name}'"})

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.get("id"),
                    "content": tool_content,
                }
            )

    raise AssistantProviderError(
        "Assistant did not produce a final reply after multiple tool-call rounds."
    )
