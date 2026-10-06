from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import HealthObservation, User
from app.schemas import HealthObservationCreate, HealthObservationOut

router = APIRouter(prefix="/health-observations", tags=["health-observations"])


@router.post("", response_model=HealthObservationOut, status_code=201)
def create_health_observation(
    payload: HealthObservationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> HealthObservation:
    entry = HealthObservation(
        user_id=user.id,
        category=payload.category,
        description=payload.description,
        severity=payload.severity,
        recorded_at=payload.recorded_at or datetime.now(timezone.utc),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.get("", response_model=list[HealthObservationOut])
def list_health_observations(
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[HealthObservation]:
    stmt = select(HealthObservation).order_by(HealthObservation.recorded_at.desc()).limit(limit)
    return list(db.scalars(stmt))
