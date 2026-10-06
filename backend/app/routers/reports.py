from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import (
    CoffeeEntry,
    FluidEntry,
    HealthObservation,
    SleepActivitySummary,
    User,
    WeightEntry,
)
from app.schemas import DashboardReport, UserReportSummary

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/dashboard", response_model=DashboardReport)
def dashboard(
    days: int = 7,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> DashboardReport:
    """Aggregate a simple cross-domain household overview.

    This is intentionally a thin aggregation layer: it reads the existing
    per-domain tables and summarizes them, rather than introducing its own
    derived data model.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)
    users = list(db.scalars(select(User).order_by(User.display_name)))

    summaries: list[UserReportSummary] = []
    for user in users:
        latest_weight = (
            db.query(WeightEntry)
            .filter(WeightEntry.user_id == user.id)
            .order_by(WeightEntry.recorded_at.desc())
            .first()
        )

        fluids_total = (
            db.query(func.coalesce(func.sum(FluidEntry.amount_ml), 0))
            .filter(FluidEntry.user_id == user.id, FluidEntry.recorded_at >= since)
            .scalar()
        )

        coffee_total = (
            db.query(func.coalesce(func.sum(CoffeeEntry.cups), 0.0))
            .filter(CoffeeEntry.user_id == user.id, CoffeeEntry.recorded_at >= since)
            .scalar()
        )

        health_obs_count = (
            db.query(func.count(HealthObservation.id))
            .filter(HealthObservation.user_id == user.id, HealthObservation.recorded_at >= since)
            .scalar()
        )

        sleep_minutes_avg = (
            db.query(func.avg(SleepActivitySummary.sleep_minutes))
            .filter(
                SleepActivitySummary.user_id == user.id,
                SleepActivitySummary.summary_date >= since.date(),
                SleepActivitySummary.sleep_minutes.is_not(None),
            )
            .scalar()
        )

        steps_avg = (
            db.query(func.avg(SleepActivitySummary.steps))
            .filter(
                SleepActivitySummary.user_id == user.id,
                SleepActivitySummary.summary_date >= since.date(),
                SleepActivitySummary.steps.is_not(None),
            )
            .scalar()
        )

        summaries.append(
            UserReportSummary(
                user_id=user.id,
                display_name=user.display_name,
                latest_weight_kg=latest_weight.weight_kg if latest_weight else None,
                latest_weight_at=latest_weight.recorded_at if latest_weight else None,
                fluids_ml_total=int(fluids_total or 0),
                coffee_cups_total=float(coffee_total or 0.0),
                health_observation_count=int(health_obs_count or 0),
                sleep_minutes_avg=float(sleep_minutes_avg) if sleep_minutes_avg is not None else None,
                steps_avg=float(steps_avg) if steps_avg is not None else None,
            )
        )

    return DashboardReport(period_days=days, generated_at=datetime.now(timezone.utc), users=summaries)
