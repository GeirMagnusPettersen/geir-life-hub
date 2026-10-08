from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.integrations.kitchenowl import KitchenOwlClient, KitchenOwlNotConfiguredError
from app.models import CoffeeEntry, FluidEntry, HealthObservation, SleepActivitySummary, User, WeightEntry
from app.routers.kitchenowl import get_kitchenowl_client
from app.schemas import (
    AiImportDomain,
    AiImportDomainSchema,
    AiImportItem,
    AiImportItemResult,
    AiImportRequest,
    AiImportResult,
    AiImportSchemaResponse,
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


# --- Self-describing schema (GET /import/ai/schema) ------------------------
#
# Every `json_schema` entry below is generated via `model_json_schema()`
# straight off the *same* Create model `_import_item()` validates against -
# never hand-duplicated - so this endpoint can't drift from what POST
# /import/ai actually accepts, even as domains/fields change over time.

_DOMAIN_MODELS: dict[AiImportDomain, type[BaseModel]] = {
    AiImportDomain.weight: WeightEntryCreate,
    AiImportDomain.fluid: FluidEntryCreate,
    AiImportDomain.coffee: CoffeeEntryCreate,
    AiImportDomain.health_observation: HealthObservationCreate,
    AiImportDomain.sleep_activity: SleepActivityCreate,
    AiImportDomain.shopping_list_item: AiImportShoppingListItem,
}

_DOMAIN_EXAMPLES: dict[AiImportDomain, dict[str, Any]] = {
    AiImportDomain.weight: {"weight_kg": 81.5, "note": "from a bathroom scale photo"},
    AiImportDomain.fluid: {"amount_ml": 500, "fluid_type": "water"},
    AiImportDomain.coffee: {"cups": 2},
    AiImportDomain.health_observation: {
        "category": "headache",
        "description": "Mild headache after lunch",
        "severity": 2,
    },
    AiImportDomain.sleep_activity: {
        "summary_date": "2025-01-01",
        "sleep_minutes": 420,
        "steps": 8000,
        "resting_heart_rate": 58,
        "avg_heart_rate": 70,
    },
    AiImportDomain.shopping_list_item: {"name": "Melk", "description": "lettmelk, 1L"},
}

_DOMAIN_NOTES: dict[AiImportDomain, str] = {
    AiImportDomain.sleep_activity: (
        "Upserted per summary_date: a second item for a date already present "
        "overwrites that day's row instead of creating a duplicate (same "
        "semantics as the Health Connect sync)."
    ),
    AiImportDomain.shopping_list_item: (
        "Forwarded to the household's configured KitchenOwl instance rather "
        "than stored locally; returns a per-item error if KitchenOwl isn't "
        "configured."
    ),
}

_EXCLUDED_GUIDANCE: dict[str, str] = {
    "food_meal_calorie_tracking": (
        "There is intentionally no domain here for food, meals, calories, or "
        "macro/nutrition tracking. VG Vektklubb remains the household's "
        "authoritative diet and calorie tracker - Life Hub must not become a "
        "worse copy of Vektklubb (diet/calories) or Garmin (fitness). Do not "
        "force food or calorie data into any of the domains below. If a user "
        "explicitly wants a qualitative, free-text note about diet or a "
        "related symptom recorded (not structured nutrition data), use the "
        "`health_observation` domain as a fallback, e.g. "
        '{"category": "kosthold", "description": "..."}.'
    ),
}


def _build_domain_schema(domain: AiImportDomain) -> AiImportDomainSchema:
    model = _DOMAIN_MODELS[domain]
    return AiImportDomainSchema(
        domain=domain,
        model=model.__name__,
        json_schema=model.model_json_schema(),
        example=_DOMAIN_EXAMPLES[domain],
        notes=_DOMAIN_NOTES.get(domain),
    )


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


def _build_schema_response() -> AiImportSchemaResponse:
    return AiImportSchemaResponse(
        endpoint="POST /import/ai",
        source_model_convention=(
            "`source_model` is a free-text tag identifying the originating AI "
            f'assistant (e.g. "copilot", "chatgpt"), 1-{_MAX_SOURCE_MODEL_LEN} '
            "characters. It is lowercased and truncated to "
            f"{_MAX_SOURCE_MODEL_LEN} characters, then stored on every row "
            'created by this import as source="ai_import:<source_model>" for '
            "traceability back to the assistant that produced the data."
        ),
        request_envelope=AiImportRequest.model_json_schema(),
        result_envelope=AiImportResult.model_json_schema(),
        domains=[_build_domain_schema(domain) for domain in AiImportDomain],
        excluded=_EXCLUDED_GUIDANCE,
    )


@router.get("/ai/schema", response_model=AiImportSchemaResponse)
def import_ai_schema() -> AiImportSchemaResponse:
    """Self-describing, machine-discoverable contract for POST /import/ai.

    Intentionally unauthenticated: the point is that an *external* AI
    assistant (e.g. Microsoft Copilot web chat, ChatGPT) - which may not
    have a Life Hub session - can fetch this URL directly (or have it
    pasted into its chat) and derive the exact request shape on its own,
    without a human writing/relaying a hand-authored spec. Every
    `json_schema` below comes straight from `model_json_schema()` on the
    real Pydantic model each domain validates against, so it can never
    drift from what POST /import/ai actually accepts.
    """
    return _build_schema_response()


@router.get("/ai/schema.html", response_class=HTMLResponse, include_in_schema=False)
def import_ai_schema_html() -> HTMLResponse:
    """HTML wrapper around the exact same contract as GET /import/ai/schema.

    Some AI web-browsing tools (e.g. Microsoft Copilot's browser tool) only
    render pages served as `text/html`, not raw `application/json`. This
    endpoint returns the identical data as GET /import/ai/schema - no
    reformatting, no hand-duplication - just that same payload serialized
    and wrapped in a minimal HTML page so such a client can read it. There
    is no styling here on purpose; the content is the point.
    """
    payload = _build_schema_response().model_dump(mode="json")
    body = html.escape(json.dumps(payload, indent=2))
    page = (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        "<title>POST /import/ai schema</title></head>"
        f"<body><pre>{body}</pre></body></html>"
    )
    return HTMLResponse(content=page)


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

    Don't know the exact shape to send? An external AI assistant should
    fetch GET /import/ai/schema (unauthenticated) first - it returns the
    exact JSON Schema for every `AiImportDomain`, generated live from this
    API's own Pydantic models, plus guidance on what's intentionally out of
    scope here (e.g. food/calorie data - see Vektklubb instead). If your
    browsing tool can only render HTML pages, GET /import/ai/schema.html
    returns the identical payload wrapped in a plain HTML page instead of
    raw JSON.
    """
    source = _source_tag(payload.source_model)
    results: list[AiImportItemResult] = []
    for index, item in enumerate(payload.items):
        results.append(_import_item(item, index=index, user=user, db=db, source=source, kitchenowl=kitchenowl))
    db.commit()

    imported = sum(1 for r in results if r.status == "created")
    skipped = len(results) - imported
    return AiImportResult(imported=imported, skipped=skipped, results=results)
