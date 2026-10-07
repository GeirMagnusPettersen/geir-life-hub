from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.integrations.kitchenowl import KitchenOwlClient, KitchenOwlNotConfiguredError
from app.models import CoffeeEntry, FluidEntry, HealthObservation, SleepActivitySummary, User, WeightEntry
from app.routers.kitchenowl import get_kitchenowl_client
from app.schemas import (
    AiImportDomain,
    AiImportItem,
    AiImportItemResult,
    AiImportRequest,
    AiImportResult,
    AiImportShoppingListItem,
    CoffeeEntryCreate,
    FluidEntryCreate,
    HealthObservationCreate,
    SleepActivityCreate,
    WeightEntryCreate,
)

router = APIRouter(prefix="/import", tags=["ai-import"])

_MAX_SOURCE_MODEL_LEN = 20  # keeps "ai_import:" + tag within the 32-char source column


def _source_tag(source_model: str) -> str:
    return f"ai_import:{source_model.strip().lower()[:_MAX_SOURCE_MODEL_LEN]}"


def _import_item(
    item: AiImportItem,
    *,
    index: int,
    user: User,
    db: Session,
    source: str,
    kitchenowl: KitchenOwlClient,
) -> AiImportItemResult:
    try:
        if item.domain is AiImportDomain.weight:
            parsed = WeightEntryCreate.model_validate(item.data)
            entry = WeightEntry(
                user_id=user.id,
                weight_kg=parsed.weight_kg,
                note=parsed.note,
                recorded_at=parsed.recorded_at or datetime.now(timezone.utc),
                source=source,
            )
            db.add(entry)
            db.flush()
            return AiImportItemResult(index=index, domain=item.domain, status="created", id=entry.id)

        if item.domain is AiImportDomain.fluid:
            parsed = FluidEntryCreate.model_validate(item.data)
            entry = FluidEntry(
                user_id=user.id,
                amount_ml=parsed.amount_ml,
                fluid_type=parsed.fluid_type,
                recorded_at=parsed.recorded_at or datetime.now(timezone.utc),
                source=source,
            )
            db.add(entry)
            db.flush()
            return AiImportItemResult(index=index, domain=item.domain, status="created", id=entry.id)

        if item.domain is AiImportDomain.coffee:
            parsed = CoffeeEntryCreate.model_validate(item.data)
            entry = CoffeeEntry(
                user_id=user.id,
                cups=parsed.cups,
                note=parsed.note,
                recorded_at=parsed.recorded_at or datetime.now(timezone.utc),
                source=source,
            )
            db.add(entry)
            db.flush()
            return AiImportItemResult(index=index, domain=item.domain, status="created", id=entry.id)

        if item.domain is AiImportDomain.health_observation:
            parsed = HealthObservationCreate.model_validate(item.data)
            entry = HealthObservation(
                user_id=user.id,
                category=parsed.category,
                description=parsed.description,
                severity=parsed.severity,
                recorded_at=parsed.recorded_at or datetime.now(timezone.utc),
                source=source,
            )
            db.add(entry)
            db.flush()
            return AiImportItemResult(index=index, domain=item.domain, status="created", id=entry.id)

        if item.domain is AiImportDomain.sleep_activity:
            parsed = SleepActivityCreate.model_validate(item.data)
            existing = (
                db.query(SleepActivitySummary)
                .filter(
                    SleepActivitySummary.user_id == user.id,
                    SleepActivitySummary.summary_date == parsed.summary_date,
                )
                .one_or_none()
            )
            if existing is not None:
                existing.sleep_minutes = parsed.sleep_minutes
                existing.steps = parsed.steps
                existing.resting_heart_rate = parsed.resting_heart_rate
                existing.avg_heart_rate = parsed.avg_heart_rate
                existing.source = source
                db.flush()
                return AiImportItemResult(index=index, domain=item.domain, status="created", id=existing.id)
            entry = SleepActivitySummary(
                user_id=user.id,
                summary_date=parsed.summary_date,
                sleep_minutes=parsed.sleep_minutes,
                steps=parsed.steps,
                resting_heart_rate=parsed.resting_heart_rate,
                avg_heart_rate=parsed.avg_heart_rate,
                source=source,
            )
            db.add(entry)
            db.flush()
            return AiImportItemResult(index=index, domain=item.domain, status="created", id=entry.id)

        if item.domain is AiImportDomain.shopping_list_item:
            parsed_item = AiImportShoppingListItem.model_validate(item.data)
            try:
                result = kitchenowl.add_shopping_list_item(parsed_item.name, description=parsed_item.description)
            except KitchenOwlNotConfiguredError as exc:
                return AiImportItemResult(index=index, domain=item.domain, status="error", detail=str(exc))
            return AiImportItemResult(
                index=index,
                domain=item.domain,
                status="created",
                id=str(result.get("id")) if isinstance(result, dict) and result.get("id") is not None else None,
            )

        return AiImportItemResult(index=index, domain=item.domain, status="error", detail="Unsupported domain")
    except ValidationError as exc:
        return AiImportItemResult(index=index, domain=item.domain, status="error", detail=str(exc))


@router.post("/ai", response_model=AiImportResult)
def import_ai_data(
    payload: AiImportRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    kitchenowl: KitchenOwlClient = Depends(get_kitchenowl_client),
) -> AiImportResult:
    """Import a batch of items pasted/extracted from another AI assistant
    (e.g. Copilot, ChatGPT). Each item is validated against the same
    Create schema the manual-entry endpoints use, so a bad item never
    corrupts the household's data - it's just recorded as an error and the
    rest of the batch still goes through (partial-success, like
    POST /weight/import).
    """
    source = _source_tag(payload.source_model)
    results: list[AiImportItemResult] = []
    for index, item in enumerate(payload.items):
        results.append(_import_item(item, index=index, user=user, db=db, source=source, kitchenowl=kitchenowl))
    db.commit()

    imported = sum(1 for r in results if r.status == "created")
    skipped = len(results) - imported
    return AiImportResult(imported=imported, skipped=skipped, results=results)
