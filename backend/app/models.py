"""SQLAlchemy models for the Life Hub core domains.

Scope note: we deliberately do NOT model full nutrition/calorie tracking
(owned by VG Vektklubb) or full workout logs (owned by Garmin). Weight is
logged here manually because the brief wants Life Hub able to show/aggregate
it even though Vektklubb is the primary source. Sleep/activity is a thin
placeholder filled by the Health Connect companion sync job (see
app/routers/sleep_activity.py and app/routers/workouts.py).
`WorkoutSession` is an aggregated overview of sessions synced from Health
Connect (start/end, type, calories, heart rate) - not a full training log
with routes/sets/splits, which stays Garmin's job. Recipes/shopping lists
are intentionally NOT modeled here; see app/integrations/kitchenowl.py for
the adapter approach instead.
"""
from __future__ import annotations

import enum
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid_str() -> str:
    return str(uuid.uuid4())


class User(Base):
    """A household member. The household is fixed at 2 users (Geir + Kristin);
    there is no open self-registration endpoint, accounts are provisioned via
    the management CLI (see app/cli.py)."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    sessions: Mapped[list["AuthSession"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class AuthSession(Base):
    """Server-side session record backing the session cookie. Kept simple
    (opaque random token, DB-backed expiry) rather than JWT-in-cookie, since
    this is a small trusted household deployment."""

    __tablename__ = "auth_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    token: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user: Mapped["User"] = relationship(back_populates="sessions")


class DeviceToken(Base):
    """Long-lived API token for a background sync client.

    This is the auth mechanism the future Health Connect Android companion
    will use to push data: distinct from the browser AuthSession (no cookie,
    no fixed expiry), and scoped to sync endpoints only. Only the sha256
    hash is stored; the plaintext token is shown once at creation time."""

    __tablename__ = "device_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship()


class WeightEntry(Base):
    """`source` distinguishes how the entry got here: "manual" (typed into
    the UI, the default) vs "vektklubb_import" (bulk-loaded from a Vektklubb
    CSV export via the /weight/import fallback endpoint - see
    app/routers/weight.py). This is a manual/periodic import fallback only;
    there is no live Vektklubb API integration (none exists, per
    PROJECT_BRIEF.md)."""

    __tablename__ = "weight_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    weight_kg: Mapped[float] = mapped_column(Float, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="manual", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class FluidType(str, enum.Enum):
    water = "water"
    other = "other"


class FluidEntry(Base):
    """`source` follows the same convention as `WeightEntry`/
    `SleepActivitySummary`: "manual" (typed into the UI, the default) vs an
    import tag such as "ai_import:copilot" for entries brought in via the
    AI-assistant import endpoint (see app/routers/ai_import.py)."""

    __tablename__ = "fluid_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    amount_ml: Mapped[int] = mapped_column(Integer, nullable=False)
    fluid_type: Mapped[FluidType] = mapped_column(Enum(FluidType, native_enum=False), default=FluidType.water)
    source: Mapped[str] = mapped_column(String(32), default="manual", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class CoffeeEntry(Base):
    """See `FluidEntry.source` docstring - same convention applies here."""

    __tablename__ = "coffee_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    cups: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="manual", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class HealthObservation(Base):
    """Free-form health observations / symptoms log. Not a diagnosis tool -
    just a shared household log of notable health events. See
    `FluidEntry.source` docstring for the `source` convention."""

    __tablename__ = "health_observations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1 (mild) - 5 (severe)
    source: Mapped[str] = mapped_column(String(32), default="manual", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class SleepActivitySummary(Base):
    """Daily sleep/activity placeholder. `source` defaults to "manual" today;
    the Health Connect companion sync writes rows with
    source="health_connect" via the same model (no schema change needed).
    `resting_heart_rate`/`avg_heart_rate` are daily aggregates (bpm); per-
    workout heart rate lives on `WorkoutSession` instead."""

    __tablename__ = "sleep_activity_summaries"
    __table_args__ = (UniqueConstraint("user_id", "summary_date", name="uq_sleep_activity_user_date"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    summary_date: Mapped[date] = mapped_column(Date, nullable=False)
    sleep_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    steps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resting_heart_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_heart_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="manual", nullable=False)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class WorkoutSession(Base):
    """A single workout/training session, pushed by the Health Connect
    companion sync (source="health_connect"). Kept as its own table rather
    than folded into `SleepActivitySummary` because workouts are discrete,
    timestamped events (possibly several per day) rather than a daily
    rollup - but it is part of the same sync/placeholder domain, not a
    parallel data model.

    `external_id` is the source system's stable record id (e.g. Health
    Connect's ExerciseSessionRecord.metadata.id) and, together with
    `user_id`/`source`, is what makes repeated syncs idempotent.
    """

    __tablename__ = "workout_sessions"
    __table_args__ = (
        UniqueConstraint("user_id", "source", "external_id", name="uq_workout_user_source_external_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    activity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    calories: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_heart_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    distance_meters: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="health_connect", nullable=False)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

