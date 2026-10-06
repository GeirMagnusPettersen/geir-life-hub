from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import CoffeeEntry, User
from app.schemas import CoffeeEntryCreate, CoffeeEntryOut

router = APIRouter(prefix="/coffee", tags=["coffee"])


@router.post("", response_model=CoffeeEntryOut, status_code=201)
def create_coffee_entry(
    payload: CoffeeEntryCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CoffeeEntry:
    entry = CoffeeEntry(
        user_id=user.id,
        cups=payload.cups,
        recorded_at=payload.recorded_at or datetime.now(timezone.utc),
        note=payload.note,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.get("", response_model=list[CoffeeEntryOut])
def list_coffee_entries(
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[CoffeeEntry]:
    stmt = select(CoffeeEntry).order_by(CoffeeEntry.recorded_at.desc()).limit(limit)
    return list(db.scalars(stmt))
