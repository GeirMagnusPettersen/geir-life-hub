"""Device token management for sync clients.

These endpoints are session-authenticated (used from the browser, e.g. a
"Connect my phone" button in the PWA) and mint/revoke bearer tokens that a
background sync client authenticates with instead. The first and currently
only intended consumer is the future Health Connect Android companion
described in PROJECT_BRIEF.md; the sync endpoint itself lives alongside the
sleep/activity router (app/routers/sleep_activity.py).
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import DeviceToken, User
from app.schemas import DeviceTokenCreate, DeviceTokenCreated, DeviceTokenOut
from app.security import generate_device_token, hash_device_token

router = APIRouter(prefix="/devices", tags=["devices"])


@router.post("", response_model=DeviceTokenCreated, status_code=201)
def create_device_token(
    payload: DeviceTokenCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DeviceTokenCreated:
    plaintext = generate_device_token()
    device_token = DeviceToken(
        user_id=user.id,
        label=payload.label,
        token_hash=hash_device_token(plaintext),
    )
    db.add(device_token)
    db.commit()
    db.refresh(device_token)
    return DeviceTokenCreated(id=device_token.id, label=device_token.label, token=plaintext)


@router.get("", response_model=list[DeviceTokenOut])
def list_device_tokens(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[DeviceToken]:
    return (
        db.query(DeviceToken)
        .filter(DeviceToken.user_id == user.id)
        .order_by(DeviceToken.created_at.desc())
        .all()
    )


@router.delete("/{token_id}", status_code=204)
def revoke_device_token(
    token_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    device_token = (
        db.query(DeviceToken)
        .filter(DeviceToken.id == token_id, DeviceToken.user_id == user.id)
        .one_or_none()
    )
    if device_token is None:
        raise HTTPException(status_code=404, detail="Device token not found")
    if device_token.revoked_at is None:
        device_token.revoked_at = datetime.now(timezone.utc)
        db.commit()
