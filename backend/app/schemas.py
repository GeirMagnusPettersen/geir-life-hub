from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import FluidType


# --- Auth ---------------------------------------------------------------


class LoginRequest(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    display_name: str


# --- Weight ---------------------------------------------------------------


class WeightEntryCreate(BaseModel):
    weight_kg: float = Field(gt=0, lt=500)
    recorded_at: datetime | None = None
    note: str | None = None


class WeightEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    weight_kg: float
    recorded_at: datetime
    note: str | None


# --- Fluids ---------------------------------------------------------------


class FluidEntryCreate(BaseModel):
    amount_ml: int = Field(gt=0, le=5000)
    fluid_type: FluidType = FluidType.water
    recorded_at: datetime | None = None


class FluidEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    amount_ml: int
    fluid_type: FluidType
    recorded_at: datetime


# --- Coffee ---------------------------------------------------------------


class CoffeeEntryCreate(BaseModel):
    cups: float = Field(gt=0, le=20)
    recorded_at: datetime | None = None
    note: str | None = None


class CoffeeEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    cups: float
    recorded_at: datetime
    note: str | None


# --- Health observations ---------------------------------------------------


class HealthObservationCreate(BaseModel):
    category: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=1)
    severity: int | None = Field(default=None, ge=1, le=5)
    recorded_at: datetime | None = None


class HealthObservationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    category: str
    description: str
    severity: int | None
    recorded_at: datetime


# --- Sleep / activity -------------------------------------------------------


class SleepActivityCreate(BaseModel):
    summary_date: date
    sleep_minutes: int | None = Field(default=None, ge=0, le=1440)
    steps: int | None = Field(default=None, ge=0)
    resting_heart_rate: int | None = Field(default=None, ge=20, le=250)
    avg_heart_rate: int | None = Field(default=None, ge=20, le=250)
    source: str = "manual"


class SleepActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    summary_date: date
    sleep_minutes: int | None
    steps: int | None
    resting_heart_rate: int | None
    avg_heart_rate: int | None
    source: str


# --- Device tokens / Health Connect sync -----------------------------------
#
# Auth contract for the future Health Connect Android companion (see
# PROJECT_BRIEF.md section 2/4): a device token is minted via the session-
# authenticated /devices endpoints, then the companion authenticates sync
# requests with `Authorization: Bearer <token>` instead of a cookie.


class DeviceTokenCreate(BaseModel):
    label: str = Field(min_length=1, max_length=128)


class DeviceTokenCreated(BaseModel):
    """Returned only once, at creation time. The plaintext token is never
    retrievable again after this response."""

    id: str
    label: str
    token: str


class DeviceTokenOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    label: str
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None


class HealthConnectSyncItem(BaseModel):
    summary_date: date
    sleep_minutes: int | None = Field(default=None, ge=0, le=1440)
    steps: int | None = Field(default=None, ge=0)
    resting_heart_rate: int | None = Field(default=None, ge=20, le=250)
    avg_heart_rate: int | None = Field(default=None, ge=20, le=250)


class HealthConnectSyncRequest(BaseModel):
    entries: list[HealthConnectSyncItem] = Field(min_length=1, max_length=366)


class HealthConnectSyncResult(BaseModel):
    synced: int


# --- Workouts (Health Connect sync) -----------------------------------------
#
# Discrete workout/training sessions, as opposed to the daily rollup above.
# Same auth contract: synced via a device token minted through /devices.


class WorkoutSyncItem(BaseModel):
    external_id: str = Field(min_length=1, max_length=128)
    activity_type: str = Field(min_length=1, max_length=64)
    start_time: datetime
    end_time: datetime
    duration_minutes: int | None = Field(default=None, ge=0)
    calories: float | None = Field(default=None, ge=0)
    avg_heart_rate: int | None = Field(default=None, ge=20, le=250)
    distance_meters: float | None = Field(default=None, ge=0)


class WorkoutSyncRequest(BaseModel):
    sessions: list[WorkoutSyncItem] = Field(min_length=1, max_length=366)


class WorkoutSyncResult(BaseModel):
    synced: int


class WorkoutOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    external_id: str
    activity_type: str
    start_time: datetime
    end_time: datetime
    duration_minutes: int | None
    calories: float | None
    avg_heart_rate: int | None
    distance_meters: float | None
    source: str


# --- Reports ----------------------------------------------------------------


class WeeklyTrendPoint(BaseModel):
    """One week's worth of aggregated data, oldest-to-newest in the trend list."""

    week_start: date
    week_end: date
    avg_weight_kg: float | None = None
    fluids_ml_per_day: float | None = None
    coffee_cups_per_day: float | None = None
    symptom_count: int = 0
    avg_sleep_minutes: float | None = None
    avg_resting_heart_rate: float | None = None


class UserReportSummary(BaseModel):
    user_id: str
    display_name: str
    latest_weight_kg: float | None = None
    latest_weight_at: datetime | None = None
    fluids_ml_total: int = 0
    coffee_cups_total: float = 0
    health_observation_count: int = 0
    sleep_minutes_avg: float | None = None
    steps_avg: float | None = None
    weekly_trend: list[WeeklyTrendPoint] = []


class DashboardReport(BaseModel):
    period_days: int
    trend_weeks: int
    generated_at: datetime
    users: list[UserReportSummary]


class SleepTrendPoint(BaseModel):
    """One day's sleep/heart-rate reading for one user.

    Returned as a flat, per-user/per-day list (not bucketed) so the frontend
    can plot a combined time series for both household members on one shared
    graph, consistent with the no private/shared split data model.
    """

    user_id: str
    display_name: str
    summary_date: date
    sleep_minutes: int | None = None
    steps: int | None = None
    resting_heart_rate: int | None = None
    avg_heart_rate: int | None = None


class SleepTrendReport(BaseModel):
    period_days: int
    generated_at: datetime
    points: list[SleepTrendPoint]
