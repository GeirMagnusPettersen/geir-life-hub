from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import SleepActivitySummary, User
from app.schemas import SleepActivityCreate, SleepActivityOut

router = APIRouter(prefix="/sleep-activity", tags=["sleep-activity"])


@router.post("", response_model=SleepActivityOut, status_code=201)
def upsert_sleep_activity(
    payload: SleepActivityCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SleepActivitySummary:
    """Create or update today's (or a given date's) manual placeholder entry.

    This endpoint is the manual-fallback path; a future Health Connect sync
    job will write rows with source="health_connect" via the same model.
    """
    existing = (
        db.query(SleepActivitySummary)
        .filter(
            SleepActivitySummary.user_id == user.id,
            SleepActivitySummary.summary_date == payload.summary_date,
        )
        .one_or_none()
    )
    if existing is not None:
        existing.sleep_minutes = payload.sleep_minutes
        existing.steps = payload.steps
        existing.source = payload.source
        db.commit()
        db.refresh(existing)
        return existing

    entry = SleepActivitySummary(
        user_id=user.id,
        summary_date=payload.summary_date,
        sleep_minutes=payload.sleep_minutes,
        steps=payload.steps,
        source=payload.source,
    )
    db.add(entry)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Entry for this date already exists") from exc
    db.refresh(entry)
    return entry


@router.get("", response_model=list[SleepActivityOut])
def list_sleep_activity(
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[SleepActivitySummary]:
    stmt = (
        select(SleepActivitySummary)
        .order_by(SleepActivitySummary.summary_date.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt))
