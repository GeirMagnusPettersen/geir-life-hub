from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.assistant.chat import ChatMessage, ChatReply, run_chat_turn
from app.assistant.llm_client import AssistantNotConfiguredError, AssistantProviderError, LlmClient
from app.deps import get_current_user
from app.integrations.kitchenowl import KitchenOwlClient
from app.models import User

router = APIRouter(prefix="/assistant", tags=["assistant"])


class ChatRequest(BaseModel):
    # Full conversation so far, oldest first; the backend is stateless and
    # keeps no server-side conversation history between requests.
    messages: list[ChatMessage] = Field(min_length=1, max_length=50)


def get_llm_client() -> LlmClient:
    return LlmClient()


def get_kitchenowl_client() -> KitchenOwlClient:
    return KitchenOwlClient()


@router.get("/status")
def assistant_status(
    llm: LlmClient = Depends(get_llm_client),
    _user: User = Depends(get_current_user),
) -> dict[str, bool]:
    return {"configured": llm.is_configured}


@router.post("/chat", response_model=ChatReply)
def assistant_chat(
    request: ChatRequest,
    llm: LlmClient = Depends(get_llm_client),
    kitchenowl: KitchenOwlClient = Depends(get_kitchenowl_client),
    _user: User = Depends(get_current_user),
) -> ChatReply:
    try:
        return run_chat_turn(request.messages, llm=llm, kitchenowl=kitchenowl)
    except AssistantNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AssistantProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
