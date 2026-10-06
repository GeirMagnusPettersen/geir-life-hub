from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import AuthSession, DeviceToken, User
from app.security import hash_device_token

settings = get_settings()


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """Resolve the current user from the session cookie.

    The cookie name is driven by settings.session_cookie_name so it stays in
    sync with whatever name routers/auth.py set on login.
    """
    session_token = request.cookies.get(settings.session_cookie_name)
    if not session_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    auth_session = (
        db.query(AuthSession).filter(AuthSession.token == session_token).one_or_none()
    )
    if auth_session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")

    expires_at = auth_session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        db.delete(auth_session)
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")

    user = db.get(User, auth_session.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def get_current_user_from_device_token(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """Resolve the current user from a bearer device token.

    Used by sync endpoints (e.g. the future Health Connect companion) that
    cannot hold a browser session cookie. Expects
    `Authorization: Bearer <token>`.
    """
    auth_header = request.headers.get("Authorization", "")
    scheme, _, token = auth_header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing device token")

    device_token = (
        db.query(DeviceToken).filter(DeviceToken.token_hash == hash_device_token(token)).one_or_none()
    )
    if device_token is None or device_token.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid device token")

    device_token.last_used_at = datetime.now(timezone.utc)
    db.commit()

    user = db.get(User, device_token.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user
