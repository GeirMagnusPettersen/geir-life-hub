from __future__ import annotations

# These tests cover the manual CSV import/fallback for Vektklubb weight data
# described in issue #7: Life Hub has no live Vektklubb API integration, so
# historical/periodic weight data is brought in by hand via a CSV export
# instead of an automatic sync.


def _upload(auth_client, content: str, filename: str = "weights.csv"):
    return auth_client.post(
        "/weight/import",
        files={"file": (filename, content.encode("utf-8"), "text/csv")},
    )


def test_weight_import_requires_authentication(client):
    response = client.post(
        "/weight/import",
        files={"file": ("weights.csv", b"date,weight_kg\n2026-01-01,80\n", "text/csv")},
    )
    assert response.status_code == 401


def test_weight_import_happy_path_english_headers(auth_client):
    csv_content = (
        "date,weight_kg,note\n"
        "2026-01-01,82.5,morning weigh-in\n"
        "2026-01-08,81.9,\n"
    )
    response = _upload(auth_client, csv_content)
    assert response.status_code == 201
    body = response.json()
    assert body["imported"] == 2
    assert body["skipped"] == 0
    assert body["errors"] == []

    entries = auth_client.get("/weight").json()
    assert len(entries) == 2
    assert all(entry["source"] == "vektklubb_import" for entry in entries)
    notes = {entry["weight_kg"]: entry["note"] for entry in entries}
    assert notes[82.5] == "morning weigh-in"
    assert notes[81.9] is None


def test_weight_import_accepts_norwegian_headers_and_comma_decimal(auth_client):
    # Norwegian exports commonly use semicolons as the field delimiter so
    # that a comma can be used as the decimal separator within a field.
    csv_content = "dato;vekt (kg);kommentar\n" "01.02.2026;83,5;etter ferie\n"
    response = _upload(auth_client, csv_content)
    assert response.status_code == 201
    body = response.json()
    assert body["imported"] == 1
    assert body["skipped"] == 0

    entry = auth_client.get("/weight").json()[0]
    assert entry["weight_kg"] == 83.5
    assert entry["note"] == "etter ferie"
    assert entry["source"] == "vektklubb_import"


def test_weight_import_accepts_semicolon_delimited_csv(auth_client):
    csv_content = "dato;vekt\n01.03.2026;79,2\n08.03.2026;78,8\n"
    response = _upload(auth_client, csv_content)
    assert response.status_code == 201
    body = response.json()
    assert body["imported"] == 2
    assert body["skipped"] == 0


def test_weight_import_reports_partial_failures(auth_client):
    csv_content = (
        "date,weight_kg\n"
        "2026-01-01,82.5\n"
        "not-a-date,80\n"
        "2026-01-03,not-a-number\n"
        "2026-01-04,999\n"
    )
    response = _upload(auth_client, csv_content)
    assert response.status_code == 201
    body = response.json()
    assert body["imported"] == 1
    assert body["skipped"] == 3
    assert len(body["errors"]) == 3
    # Row numbers are 1-indexed relative to the data rows (excluding header).
    assert {error["row"] for error in body["errors"]} == {2, 3, 4}

    entries = auth_client.get("/weight").json()
    assert len(entries) == 1
    assert entries[0]["weight_kg"] == 82.5


def test_weight_import_rejects_missing_required_columns(auth_client):
    csv_content = "some_column,other_column\nfoo,bar\n"
    response = _upload(auth_client, csv_content)
    assert response.status_code == 422


def test_weight_import_rejects_empty_file_without_header(auth_client):
    response = _upload(auth_client, "")
    assert response.status_code == 422


def test_weight_import_ignores_blank_trailing_rows(auth_client):
    csv_content = "date,weight_kg\n2026-01-01,82.5\n,\n"
    response = _upload(auth_client, csv_content)
    assert response.status_code == 201
    body = response.json()
    assert body["imported"] == 1
    assert body["skipped"] == 0
