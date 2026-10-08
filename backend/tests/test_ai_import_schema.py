from __future__ import annotations

from app.routers.ai_import import _DOMAIN_MODELS
from app.schemas import AiImportDomain


def test_schema_endpoint_is_unauthenticated(client):
    """GET /import/ai/schema has no auth dependency: an external AI assistant
    without a Life Hub session must be able to fetch it directly."""
    response = client.get("/import/ai/schema")
    assert response.status_code == 200


def test_schema_endpoint_covers_every_domain(client):
    """Every AiImportDomain value must have a corresponding schema entry, so
    a new domain added later to the enum can't be forgotten here."""
    body = client.get("/import/ai/schema").json()
    documented_domains = {entry["domain"] for entry in body["domains"]}
    assert documented_domains == {domain.value for domain in AiImportDomain}


def test_schema_entries_match_live_model_json_schema(client):
    """Guards against drift: each domain's `json_schema` must be exactly
    what `model_json_schema()` produces for the Create model POST /import/ai
    actually validates against - not a hand-duplicated copy."""
    body = client.get("/import/ai/schema").json()
    by_domain = {entry["domain"]: entry for entry in body["domains"]}

    for domain, model in _DOMAIN_MODELS.items():
        entry = by_domain[domain.value]
        assert entry["model"] == model.__name__
        assert entry["json_schema"] == model.model_json_schema()


def test_schema_entries_have_examples_and_valid_schema_shape(client):
    body = client.get("/import/ai/schema").json()
    for entry in body["domains"]:
        assert entry["example"], f"domain {entry['domain']} is missing an example"
        json_schema = entry["json_schema"]
        # A real JSON Schema document always carries one of these.
        assert "properties" in json_schema or "type" in json_schema


def test_schema_response_has_request_and_result_envelopes(client):
    body = client.get("/import/ai/schema").json()
    assert body["endpoint"] == "POST /import/ai"
    assert "properties" in body["request_envelope"]
    assert "source_model" in body["request_envelope"]["properties"]
    assert "items" in body["request_envelope"]["properties"]
    assert "properties" in body["result_envelope"]


def test_schema_response_documents_source_model_convention(client):
    body = client.get("/import/ai/schema").json()
    convention = body["source_model_convention"].lower()
    assert "source_model" in convention
    assert "ai_import:" in convention


def test_schema_response_excludes_food_and_points_to_vektklubb(client):
    """An external AI must be steered away from forcing food/calorie data
    into these domains, and told Vektklubb is authoritative for that."""
    body = client.get("/import/ai/schema").json()
    excluded_text = " ".join(body["excluded"].values()).lower()
    assert "vektklubb" in excluded_text
    assert "food" in excluded_text or "calorie" in excluded_text
    assert "health_observation" in excluded_text


def test_post_import_ai_docs_reference_schema_endpoint():
    """The POST endpoint's own OpenAPI docstring must point readers (human
    or AI) at GET /import/ai/schema so the contract is discoverable from
    the endpoint itself, not just from out-of-band documentation."""
    from app.routers.ai_import import import_ai_data

    assert import_ai_data.__doc__ is not None
    assert "/import/ai/schema" in import_ai_data.__doc__
