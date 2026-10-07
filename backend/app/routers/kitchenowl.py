from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.deps import get_current_user
from app.integrations.kitchenowl import KitchenOwlClient, KitchenOwlNotConfiguredError
from app.models import User

router = APIRouter(prefix="/integrations/kitchenowl", tags=["integrations-kitchenowl"])


class ShoppingListItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None


class ShoppingListItemUpdate(BaseModel):
    checked: bool


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


@router.post("/shopping-list", status_code=201)
def kitchenowl_add_shopping_list_item(
    item: ShoppingListItemCreate,
    client: KitchenOwlClient = Depends(get_kitchenowl_client),
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        return client.add_shopping_list_item(item.name, description=item.description)
    except KitchenOwlNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.put("/shopping-list/{item_id}")
def kitchenowl_update_shopping_list_item(
    item_id: int,
    update: ShoppingListItemUpdate,
    client: KitchenOwlClient = Depends(get_kitchenowl_client),
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        return client.set_shopping_list_item_checked(item_id, update.checked)
    except KitchenOwlNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except NotImplementedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/shopping-list")
def kitchenowl_clear_shopping_list(
    client: KitchenOwlClient = Depends(get_kitchenowl_client),
    _user: User = Depends(get_current_user),
) -> dict[str, int]:
    try:
        removed = client.clear_shopping_list()
    except KitchenOwlNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"removed": removed}


@router.get("/recipes")
def kitchenowl_recipes(
    client: KitchenOwlClient = Depends(get_kitchenowl_client),
    _user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    try:
        return client.get_recipes()
    except KitchenOwlNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
