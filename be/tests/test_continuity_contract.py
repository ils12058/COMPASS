"""DB-free assertions of the checked-in metadata-only wire boundary."""

import json
from pathlib import Path

from compass.counseling.continuity_policy import get_approved_policy

CONTRACT = Path(__file__).resolve().parents[2] / "contracts/openapi.json"


def test_continuity_contract_has_seven_metadata_only_operations():
    contract = json.loads(CONTRACT.read_text())
    prefix = "/api/v1/counseling/continuity-grants"
    paths = {k: v for k, v in contract["paths"].items() if k.startswith(prefix)}
    assert set(paths) == {
        prefix,
        prefix + "/{grant_id}",
        *[prefix + "/{grant_id}/" + a for a in ["approve", "decline", "cancel", "revoke"]],
    }
    assert sum(len(v) for v in paths.values()) == 7
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
