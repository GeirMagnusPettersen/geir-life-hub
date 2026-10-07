from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, get_current_user_from_device_token
from app.models import User, WorkoutSession
from app.schemas import WorkoutOut, WorkoutSyncRequest, WorkoutSyncResult

router = APIRouter(prefix="/workouts", tags=["workouts"])


@router.get("", response_model=list[WorkoutOut])
def list_workouts(
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[WorkoutSession]:
    # Shared household data, like the other logs - not filtered by user.
    stmt = select(WorkoutSession).order_by(WorkoutSession.start_time.desc()).limit(limit)
    return list(db.scalars(stmt))


@router.post("/sync", response_model=WorkoutSyncResult)
def sync_workouts(
    payload: WorkoutSyncRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_from_device_token),
) -> WorkoutSyncResult:
    """Bulk upsert for a device-token-authenticated sync client.

    Idempotent per user + source + external_id: re-syncing the same Health
    Connect ExerciseSessionRecord (e.g. after a retry) updates the existing
    row instead of creating a duplicate. Rows are always stamped
    source="health_connect" and synced_at, same as `/sleep-activity/sync`.
    """
    now = datetime.now(timezone.utc)
    synced = 0
    for item in payload.sessions:
        existing = (
            db.query(WorkoutSession)
            .filter(
                WorkoutSession.user_id == user.id,
                WorkoutSession.source == "health_connect",
                WorkoutSession.external_id == item.external_id,
            )
            .one_or_none()
        )
        if existing is not None:
            existing.activity_type = item.activity_type
            existing.start_time = item.start_time
            existing.end_time = item.end_time
            existing.duration_minutes = item.duration_minutes
            existing.calories = item.calories
            existing.avg_heart_rate = item.avg_heart_rate
            existing.distance_meters = item.distance_meters
            existing.synced_at = now
        else:
            db.add(
                WorkoutSession(
                    user_id=user.id,
                    external_id=item.external_id,
                    activity_type=item.activity_type,
                    start_time=item.start_time,
                    end_time=item.end_time,
                    duration_minutes=item.duration_minutes,
                    calories=item.calories,
                    avg_heart_rate=item.avg_heart_rate,
                    distance_meters=item.distance_meters,
                    source="health_connect",
                    synced_at=now,
                )
            )
        synced += 1
    db.commit()
    return WorkoutSyncResult(synced=synced)
