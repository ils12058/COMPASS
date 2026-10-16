"""Read-only retention policy oversight from the code-owned register (ADR-115).

The former rule, case, hold and approval routes are retired (ADR-114, ADR-115). Their tables stay
internal historical evidence; this router never reads or serializes them, and it never mutates.
"""

from datetime import date

from ninja import Router, Schema
from pydantic import ConfigDict

from compass.authentication.api import session_auth
from compass.common.api import response_with_errors

from . import retention_policy_register as register
from .api import _require

router = Router(tags=["privacy-governance"], auth=session_auth)
VIEW = "privacy_governance.retention.view"


class RetentionStrictSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class RetentionPolicyEntryResponse(RetentionStrictSchema):
    category_code: register.RetentionPolicyCategory
    category_label: str
    adoption_status: register.RetentionAdoptionStatus
    retention_period: str | None
    policy_reference: str | None
    effective_date: date | None


class RetentionPolicyRegisterResponse(RetentionStrictSchema):
    items: list[RetentionPolicyEntryResponse]


@router.get(
    "/retention/policies",
    response=response_with_errors(RetentionPolicyRegisterResponse, 401, 403),
    operation_id="privacyGovernanceListRetentionPolicies",
)
def retention_policies(request):
    _require(request, VIEW)
    return {"items": [register.project(entry) for entry in register.REGISTER]}
