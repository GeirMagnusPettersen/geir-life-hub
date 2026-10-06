from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import FluidEntry, User
from app.schemas import FluidEntryCreate, FluidEntryOut

router = APIRouter(prefix="/fluids", tags=["fluids"])


@router.post("", response_model=FluidEntryOut, status_code=201)
def create_fluid_entry(
    payload: FluidEntryCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FluidEntry:
    entry = FluidEntry(
        user_id=user.id,
        amount_ml=payload.amount_ml,
        fluid_type=payload.fluid_type,
        recorded_at=payload.recorded_at or datetime.now(timezone.utc),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.get("", response_model=list[FluidEntryOut])
def list_fluid_entries(
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[FluidEntry]:
    stmt = select(FluidEntry).order_by(FluidEntry.recorded_at.desc()).limit(limit)
    return list(db.scalars(stmt))
