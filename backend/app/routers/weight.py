from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import User, WeightEntry
from app.schemas import WeightEntryCreate, WeightEntryOut

router = APIRouter(prefix="/weight", tags=["weight"])


@router.post("", response_model=WeightEntryOut, status_code=201)
def create_weight_entry(
    payload: WeightEntryCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> WeightEntry:
    entry = WeightEntry(
        user_id=user.id,
        weight_kg=payload.weight_kg,
        recorded_at=payload.recorded_at or datetime.now(timezone.utc),
        note=payload.note,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.get("", response_model=list[WeightEntryOut])
def list_weight_entries(
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[WeightEntry]:
    # All household data is shared, so entries are not filtered by user here -
    # every signed-in household member can see everyone's log, per the brief.
    stmt = select(WeightEntry).order_by(WeightEntry.recorded_at.desc()).limit(limit)
    return list(db.scalars(stmt))
