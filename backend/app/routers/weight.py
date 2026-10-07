from __future__ import annotations

import csv
import io
from datetime import date, datetime, time, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import User, WeightEntry
from app.schemas import WeightEntryCreate, WeightEntryOut, WeightImportError, WeightImportResult

router = APIRouter(prefix="/weight", tags=["weight"])

# Manual CSV import is the fallback for Vektklubb weight data, since
# Vektklubb has no public API (see PROJECT_BRIEF.md) - the user exports a
# CSV from the Vektklubb UI and uploads it here. Column names are matched
# loosely (case-insensitive, Norwegian or English) since we don't control
# Vektklubb's export format and it may change.
_DATE_COLUMN_ALIASES = {"date", "dato", "recorded_at", "tidspunkt", "dag"}
_WEIGHT_COLUMN_ALIASES = {"weight_kg", "weight", "vekt", "vekt (kg)", "vekt(kg)", "kg"}
_NOTE_COLUMN_ALIASES = {"note", "notat", "kommentar", "comment"}

_DATE_FORMATS = ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y")

_MAX_IMPORT_ROWS = 2000
_MAX_IMPORT_BYTES = 1_000_000


def _normalize_header(name: str) -> str:
    return name.strip().lower()


def _parse_recorded_at(raw: str) -> datetime:
    raw = raw.strip()
    for fmt in _DATE_FORMATS:
        try:
            parsed = datetime.strptime(raw, fmt)
            return datetime.combine(parsed.date(), time.min, tzinfo=timezone.utc)
        except ValueError:
            continue
    # Fall back to full ISO datetime parsing (e.g. "2026-01-01T07:30:00").
    try:
        parsed_dt = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(f"Could not parse date '{raw}'") from exc
    if parsed_dt.tzinfo is None:
        parsed_dt = parsed_dt.replace(tzinfo=timezone.utc)
    return parsed_dt


def _parse_weight(raw: str) -> float:
    # Norwegian exports commonly use a comma as the decimal separator.
    normalized = raw.strip().replace(",", ".")
    value = float(normalized)
    if not (0 < value < 500):
        raise ValueError(f"Weight '{raw}' out of plausible range")
    return value


@router.post("", response_model=WeightEntryOut, status_code=201)
def create_weight_entry(
    payload: WeightEntryCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> WeightEntry:
    entry = WeightEntry(
        user_id=user.id,
        weight_kg=payload.weight_kg,
        recorded_at=payload.recorded_at or datetime.now(timezone.utc),
        note=payload.note,
        source="manual",
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.get("", response_model=list[WeightEntryOut])
def list_weight_entries(
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[WeightEntry]:
    # All household data is shared, so entries are not filtered by user here -
    # every signed-in household member can see everyone's log, per the brief.
    stmt = select(WeightEntry).order_by(WeightEntry.recorded_at.desc()).limit(limit)
    return list(db.scalars(stmt))


@router.post("/import", response_model=WeightImportResult, status_code=201)
async def import_weight_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> WeightImportResult:
    """Bulk-import weight entries from a Vektklubb (or similar) CSV export.

    This is the manual fallback described in issue #7: Life Hub has no live
    Vektklubb integration, so historical/periodic weight data is brought in
    by hand via a CSV file rather than an API sync. Expected columns (any
    case, Norwegian or English): a date column and a weight column, plus an
    optional note column. Unparseable rows are skipped and reported rather
    than failing the whole import, since real-world exports are messy.
    """
    raw_bytes = await file.read()
    if len(raw_bytes) > _MAX_IMPORT_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="CSV file is too large",
        )

    try:
        text = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw_bytes.decode("latin-1")

    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel

    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if reader.fieldnames is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="CSV file has no header row")

    header_map = {_normalize_header(name): name for name in reader.fieldnames if name}
    date_column = next((header_map[alias] for alias in _DATE_COLUMN_ALIASES if alias in header_map), None)
    weight_column = next((header_map[alias] for alias in _WEIGHT_COLUMN_ALIASES if alias in header_map), None)
    note_column = next((header_map[alias] for alias in _NOTE_COLUMN_ALIASES if alias in header_map), None)

    if date_column is None or weight_column is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="CSV must have a date column (e.g. 'date'/'dato') and a weight column (e.g. 'weight_kg'/'vekt')",
        )

    imported = 0
    skipped = 0
    errors: list[WeightImportError] = []
    entries: list[WeightEntry] = []

    for row_number, row in enumerate(reader, start=1):
        if row_number > _MAX_IMPORT_ROWS:
            errors.append(WeightImportError(row=row_number, reason="Import row limit exceeded; remaining rows ignored"))
            skipped += 1
            continue

        raw_date = (row.get(date_column) or "").strip()
        raw_weight = (row.get(weight_column) or "").strip()
        if not raw_date and not raw_weight:
            # Silently ignore fully blank rows (common at the end of exports).
            continue

        try:
            recorded_at = _parse_recorded_at(raw_date)
            weight_kg = _parse_weight(raw_weight)
        except ValueError as exc:
            skipped += 1
            errors.append(WeightImportError(row=row_number, reason=str(exc)))
            continue

        note = (row.get(note_column) or "").strip() or None if note_column else None
        entries.append(
            WeightEntry(
                user_id=user.id,
                weight_kg=weight_kg,
                recorded_at=recorded_at,
                note=note,
                source="vektklubb_import",
            )
        )
        imported += 1

    if entries:
        db.add_all(entries)
        db.commit()

    return WeightImportResult(imported=imported, skipped=skipped, errors=errors)
