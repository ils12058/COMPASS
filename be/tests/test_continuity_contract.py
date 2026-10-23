"""DB-free assertions of foundation and selected-read wire boundaries."""

import json
from pathlib import Path

from compass.counseling.continuity_policy import get_approved_policy

CONTRACT = Path(__file__).resolve().parents[2] / "contracts/openapi.json"


def test_continuity_contract_preserves_seven_metadata_operations():
    contract = json.loads(CONTRACT.read_text())
    prefix = "/api/v1/counseling/continuity-grants"
    paths = {k: v for k, v in contract["paths"].items() if k.startswith(prefix)}
    selected = {
        prefix + "/{grant_id}/encounters/{encounter_id}/metadata",
        prefix + "/{grant_id}/routine-evaluations/{routine_interview_id}",
    }
    assert selected <= set(paths)
    metadata_paths = {
        k: v
        for k, v in paths.items()
        if k not in selected and "/handoff/" not in k and "/workflow/" not in k
    }
    assert set(metadata_paths) == {
        prefix,
        prefix + "/{grant_id}",
        *[prefix + "/{grant_id}/" + a for a in ["approve", "decline", "cancel", "revoke"]],
    }
    assert sum(len(v) for v in metadata_paths.values()) == 7
    assert sum(len(v) for v in paths.values()) == 16
    schemas = contract["components"]["schemas"]
    assert schemas["ContinuitySourceKind"]["enum"] == ["ENCOUNTER", "ROUTINE_EVALUATION"]
    assert set(schemas["ContinuityProjection"]["enum"]) == {
        "ENCOUNTER_METADATA_V1",
        "FINALIZED_EVALUATION_V1",
    }
    props = schemas["ContinuityGrantMetadata"]["properties"]
    assert not set(props) & {
        "content",
        "body",
        "ciphertext",
        "intake",
        "evaluation",
        "token",
        "url",
    }
    assert schemas["ContinuityRequestInput"]["additionalProperties"] is False
    for route in paths.values():
        for operation in route.values():
            assert operation["security"] == [{"OpaqueSessionAuth": []}]


def test_deployed_policy_provider_has_no_approved_policy():
    assert get_approved_policy() is None


def test_selected_read_contract_has_fixed_typed_fields_and_default_denial():
    from compass.counseling.continuity_disclosure import get_approved_disclosure_policy

    contract = json.loads(CONTRACT.read_text())
    schemas = contract["components"]["schemas"]
    assert set(schemas["SelectedEncounterFields"]["properties"]) == {
        "id",
        "started_at",
        "ended_at",
        "entry_mode",
        "delivery_mode",
        "counselor_id",
    }
    assert set(schemas["SelectedEvaluationFields"]["properties"]) == {
        "academic_adjustment_rating",
        "physical_adjustment_rating",
        "social_adjustment_rating",
        "spiritual_adjustment_rating",
        "financial_adjustment_rating",
        "emotional_adjustment_rating",
        "other_adjustment",
        "special_concern",
        "recommendations",
    }
    assert not schemas["SelectedEvaluationFields"].get("required")
    assert schemas["SelectedEvaluationFields"]["additionalProperties"] is False
    assert get_approved_disclosure_policy() is None
    for path, route in contract["paths"].items():
        if "continuity-grants" in path and (
            "/encounters/" in path or "/routine-evaluations/" in path
        ):
            assert set(route) == {"get"}
            query = [p for p in route["get"]["parameters"] if p["in"] == "query"]
            assert [p["name"] for p in query] == ["expected_version"]
            assert query[0]["required"] is True
