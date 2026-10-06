from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.deps import get_current_user
from app.integrations.kitchenowl import KitchenOwlClient, KitchenOwlNotConfiguredError
from app.models import User

router = APIRouter(prefix="/integrations/kitchenowl", tags=["integrations-kitchenowl"])


def get_kitchenowl_client() -> KitchenOwlClient:
    return KitchenOwlClient()


@router.get("/status")
def kitchenowl_status(
    client: KitchenOwlClient = Depends(get_kitchenowl_client),
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    return {"configured": client.is_configured}


@router.get("/shopping-list")
def kitchenowl_shopping_list(
    client: KitchenOwlClient = Depends(get_kitchenowl_client),
    _user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    try:
        return client.get_shopping_list_items()
    except KitchenOwlNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/recipes")
def kitchenowl_recipes(
    client: KitchenOwlClient = Depends(get_kitchenowl_client),
    _user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    try:
        return client.get_recipes()
    except KitchenOwlNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
