from __future__ import annotations

from datetime import datetime, timedelta, timezone
from statistics import mean

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
from app.schemas import (
    DashboardReport,
    SleepTrendPoint,
    SleepTrendReport,
    UserReportSummary,
    WeeklyTrendPoint,
)

router = APIRouter(prefix="/reports", tags=["reports"])


def _as_naive(value: datetime) -> datetime:
    """Strip tzinfo for in-Python bucket comparisons.

    SQLite (used in tests/dev) doesn't preserve timezone info on round-trip,
    so values read back from the ORM are naive even though the column is
    declared `DateTime(timezone=True)` (Postgres does preserve it). Comparing
    an aware bucket boundary against a naive row value raises TypeError, so
    both sides are normalized to naive UTC before comparing.
    """
    return value.replace(tzinfo=None) if value.tzinfo is not None else value


def _build_weekly_trend(
    db: Session,
    user_id: str,
    trend_start: datetime,
    weeks: int,
) -> list[WeeklyTrendPoint]:
    """Bucket weight/fluid/coffee/symptom rows into `weeks` week-long buckets.

    Household data volumes here are tiny (two users, manual logging), so
    fetching the window once and bucketing in Python is simpler and clearer
    than hand-rolled per-week SQL grouping while still being plenty fast.
    """
    weight_rows = db.scalars(
        select(WeightEntry).where(
            WeightEntry.user_id == user_id, WeightEntry.recorded_at >= trend_start
        )
    ).all()
    fluid_rows = db.scalars(
        select(FluidEntry).where(
            FluidEntry.user_id == user_id, FluidEntry.recorded_at >= trend_start
        )
    ).all()
    coffee_rows = db.scalars(
        select(CoffeeEntry).where(
            CoffeeEntry.user_id == user_id, CoffeeEntry.recorded_at >= trend_start
        )
    ).all()
    health_rows = db.scalars(
        select(HealthObservation).where(
            HealthObservation.user_id == user_id,
            HealthObservation.recorded_at >= trend_start,
        )
    ).all()
    sleep_rows = db.scalars(
        select(SleepActivitySummary).where(
            SleepActivitySummary.user_id == user_id,
            SleepActivitySummary.summary_date >= trend_start.date(),
        )
    ).all()

    trend: list[WeeklyTrendPoint] = []
    # Sleep summaries are stored as plain calendar dates (no time-of-day), so
    # they can't be bucketed with the same half-open `[bucket_start, bucket_end)`
    # datetime comparison used for timestamped entries above: that range is
    # anchored to the current instant ("now"), which falls partway through
    # today, so a strict "<" on `bucket_end.date()` would incorrectly exclude
    # anything logged for today from the most recent bucket. Instead, bucket
    # sleep rows into inclusive 7-day calendar-date windows anchored on
    # today's date, with the most recent window ending today.
    today = datetime.now(timezone.utc).date()
    for week_index in range(weeks):
        bucket_start = _as_naive(trend_start + timedelta(weeks=week_index))
        bucket_end = bucket_start + timedelta(weeks=1)

        weights_in_week = [
            w.weight_kg for w in weight_rows if bucket_start <= _as_naive(w.recorded_at) < bucket_end
        ]
        fluids_in_week = sum(
            f.amount_ml for f in fluid_rows if bucket_start <= _as_naive(f.recorded_at) < bucket_end
        )
        coffee_in_week = sum(
            c.cups for c in coffee_rows if bucket_start <= _as_naive(c.recorded_at) < bucket_end
        )
        symptom_count = sum(
            1 for h in health_rows if bucket_start <= _as_naive(h.recorded_at) < bucket_end
        )
        weeks_from_end = weeks - 1 - week_index
        sleep_bucket_end_date = today - timedelta(days=7 * weeks_from_end)
        sleep_bucket_start_date = sleep_bucket_end_date - timedelta(days=6)
        sleep_minutes_in_week = [
            s.sleep_minutes
            for s in sleep_rows
            if s.sleep_minutes is not None
            and sleep_bucket_start_date <= s.summary_date <= sleep_bucket_end_date
        ]
        resting_hr_in_week = [
            s.resting_heart_rate
            for s in sleep_rows
            if s.resting_heart_rate is not None
            and sleep_bucket_start_date <= s.summary_date <= sleep_bucket_end_date
        ]

        trend.append(
            WeeklyTrendPoint(
                week_start=bucket_start.date(),
                week_end=(bucket_end - timedelta(days=1)).date(),
                avg_weight_kg=mean(weights_in_week) if weights_in_week else None,
                fluids_ml_per_day=fluids_in_week / 7,
                coffee_cups_per_day=coffee_in_week / 7,
                symptom_count=symptom_count,
                avg_sleep_minutes=mean(sleep_minutes_in_week) if sleep_minutes_in_week else None,
                avg_resting_heart_rate=mean(resting_hr_in_week) if resting_hr_in_week else None,
            )
        )

    return trend


@router.get("/dashboard", response_model=DashboardReport)
def dashboard(
    days: int = 7,
    weeks: int = 4,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> DashboardReport:
    """Aggregate a simple cross-domain household overview.

    This is intentionally a thin aggregation layer: it reads the existing
    per-domain tables and summarizes them, rather than introducing its own
    derived data model. `days` controls the current-snapshot window; `weeks`
    controls how many week-long buckets the trend series covers.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)
    trend_start = datetime.now(timezone.utc) - timedelta(weeks=weeks)
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
                weekly_trend=_build_weekly_trend(db, user.id, trend_start, weeks),
            )
        )

    return DashboardReport(
        period_days=days,
        trend_weeks=weeks,
        generated_at=datetime.now(timezone.utc),
        users=summaries,
    )


@router.get("/sleep-trend", response_model=SleepTrendReport)
def sleep_trend(
    days: int = 30,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> SleepTrendReport:
    """Daily sleep/heart-rate series across all household members.

    Unlike `/dashboard`'s per-user single-window averages, this returns one
    point per user per logged day over the window, so the frontend can draw
    a sleep-duration/heart-rate-over-time graph for both users together
    (shared view - see PROJECT_BRIEF.md section 3, no private/shared split).
    """
    since_date = (datetime.now(timezone.utc) - timedelta(days=days)).date()
    users_by_id = {user.id: user.display_name for user in db.scalars(select(User))}

    rows = db.scalars(
        select(SleepActivitySummary)
        .where(SleepActivitySummary.summary_date >= since_date)
        .order_by(SleepActivitySummary.summary_date)
    ).all()

    points = [
        SleepTrendPoint(
            user_id=row.user_id,
            display_name=users_by_id.get(row.user_id, "Ukjent"),
            summary_date=row.summary_date,
            sleep_minutes=row.sleep_minutes,
            steps=row.steps,
            resting_heart_rate=row.resting_heart_rate,
            avg_heart_rate=row.avg_heart_rate,
        )
        for row in rows
    ]

    return SleepTrendReport(
        period_days=days,
        generated_at=datetime.now(timezone.utc),
        points=points,
    )
