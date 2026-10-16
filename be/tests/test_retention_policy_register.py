"""Code-owned retention policy register and read-only DPO oversight (ADR-115).

All data is synthetic. The canonical baseline has no disposition ledger (CANON-1C); the only
historical marker these tests write is disposed media, through
``tests.historical_outcome_fixtures``. No test exercises a destructive path.
"""

import ast
import dataclasses
import json
import uuid
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from compass.account_management.services import InvalidManagementInput, set_capability_override
from compass.accounts.bootstrap import RETIRED_CAPABILITY_CODES, sync_identity_policy
from compass.accounts.models import (
    Capability,
    Designation,
    DesignationCapability,
    Role,
    RoleCapability,
    UserCapabilityOverride,
)
from compass.accounts.policy import (
    CAPABILITY_CODES,
    CAPABILITY_DEFINITIONS,
    CAPABILITY_DEPENDENCIES,
    DESIGNATION_CAPABILITY_GRANTS,
    ROLE_CAPABILITY_GRANTS,
)
from compass.accounts.services import effective_capabilities
from compass.api.v1.router import api
from compass.audit import actions
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.audit.services import record_event
from compass.graduate_tracer.models import GraduateTracerResponse
from compass.privacy_governance import retention_policy_register as register
from compass.privacy_governance.retention_policy_register import (
    RetentionAdoptionStatus,
    RetentionPolicy,
    RetentionPolicyCategory,
    RetentionPolicyRegisterError,
    validate_register,
)
from tests.historical_outcome_fixtures import historically_disposed_media, legacy_media_source
from tests.test_disposition_decommission import tracer
from tests.test_privacy_governance import (
    auth_client,
    make_dpo,
    make_head,
    make_user,
    patch_json,
    post_json,
    sync_policy,
)

pytestmark = pytest.mark.django_db
POLICIES = "/api/v1/privacy/retention/policies"
VIEW = "privacy_governance.retention.view"
RETIRED = ("privacy_governance.retention.manage", "privacy_governance.retention.approve")
FIELDS = {
    "category_code",
    "category_label",
    "adoption_status",
    "retention_period",
    "policy_reference",
    "effective_date",
}
DPO_AUTHORITY = frozenset(
    {
        "privacy_governance.activity.export",
        "privacy_governance.manage",
        "privacy_governance.retention.view",
        "privacy_governance.view",
    }
)
RETIRED_OPERATIONS = (
    "privacyGovernanceRetentionCategories",
    "privacyGovernanceListRetentionRules",
    "privacyGovernanceCreateRetentionRule",
    "privacyGovernanceGetRetentionRule",
    "privacyGovernanceUpdateRetentionRule",
    "privacyGovernanceActivateRetentionRule",
    "privacyGovernanceRetireRetentionRule",
    "privacyGovernanceRetentionSummary",
    "privacyGovernanceListDispositionCases",
    "privacyGovernanceGetDispositionCase",
    "privacyGovernancePlaceDispositionHold",
    "privacyGovernanceReleaseDispositionHold",
    "privacyGovernanceApproveDispositionCase",
    "privacyGovernanceRetryDispositionCase",
)
RETIRED_SCHEMAS = (
    "RetentionCategoryResponse",
    "RetentionRuleCreate",
    "RetentionRuleUpdate",
    "RetentionRuleResponse",
    "RetentionRulePage",
    "RetentionRevisionRequest",
    "RetentionSummaryResponse",
    "RetentionCategorySummary",
    "DispositionHoldRequest",
    "DispositionHoldResponse",
    "DispositionCaseResponse",
    "DispositionCasePage",
)
BE = Path(__file__).resolve().parents[1]


@pytest.fixture
def dpo():
    sync_policy()
    return make_dpo()


def adopted(**changes):
    values = {
        "category_code": RetentionPolicyCategory.GRADUATE_TRACER,
        "category_label": "Synthetic category",
        "adoption_status": RetentionAdoptionStatus.ADOPTED,
        "retention_period": "SYNTHETIC TEST WORDING - not institutional policy",
        "policy_reference": "SYNTHETIC-REFERENCE - not institutional policy",
        "effective_date": date(2030, 1, 1),
    }
    return RetentionPolicy(**(values | changes))


def not_adopted(**changes):
    values = {
        "category_code": RetentionPolicyCategory.GRADUATE_TRACER,
        "category_label": "Synthetic category",
        "adoption_status": RetentionAdoptionStatus.NOT_ADOPTED,
    }
    return RetentionPolicy(**(values | changes))


def ledger_snapshot():
    """The audit trail plus the records whose identifiers must never be served."""
    return (
        list(GraduateTracerResponse.objects.order_by("pk").values("pk", "status")),
        list(AuditEvent.objects.order_by("occurred_at", "pk").values("pk", "action", "metadata")),
    )


def legacy_world(actor):
    """A submitted tracer source and disposed media, with identifiers a retired route once used."""
    source = tracer("legacy-queued@example.edu")
    capture, _ = legacy_media_source("RECORDING")
    historically_disposed_media(capture)
    return (
        SimpleNamespace(pk=uuid.uuid4()),
        SimpleNamespace(pk=uuid.uuid4(), source_id=source.pk, rule_id=uuid.uuid4()),
        SimpleNamespace(pk=uuid.uuid4(), source_id=capture.pk),
    )


def module_imports(path, *, names=False):
    """Imported modules; with ``names``, also each ``from x import y`` target as ``x.y``."""
    found = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = ("." * node.level) + (node.module or "")
            found.add(module)
            if names:
                found.update(f"{module}.{alias.name}" for alias in node.names)
    return found


# --- Code-owned register ------------------------------------------------------------------------


def test_register_defines_each_former_category_once_in_a_fixed_order():
    codes = [entry.category_code for entry in register.REGISTER]
    assert codes == [
        RetentionPolicyCategory.GRADUATE_TRACER,
        RetentionPolicyCategory.ECOUNSELING_RECORDING,
        RetentionPolicyCategory.ECOUNSELING_TRANSCRIPT,
    ]
    assert len(set(codes)) == len(codes)
    assert set(codes) == set(RetentionPolicyCategory)
    assert [entry.category_label for entry in register.REGISTER] == [
        "Graduate Tracer responses",
        "E-Counseling recordings",
        "E-Counseling transcripts",
    ]
    projected = [register.project(entry) for entry in register.REGISTER]
    assert projected == [register.project(entry) for entry in register.REGISTER]
    assert all(set(item) == FIELDS for item in projected)


def test_initial_entries_are_not_adopted_and_record_no_invented_terms():
    for entry in register.REGISTER:
        assert entry.adoption_status is RetentionAdoptionStatus.NOT_ADOPTED
        assert entry.retention_period is None
        assert entry.policy_reference is None
        assert entry.effective_date is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("retention_period", "5 years"),
        ("retention_period", "0 days"),
        ("retention_period", ""),
        ("retention_period", "N/A"),
        ("policy_reference", "Legacy rule TEST"),
        ("policy_reference", ""),
        ("effective_date", date(2026, 10, 16)),
    ],
)
def test_a_not_adopted_entry_rejects_any_period_reference_or_date(field, value):
    with pytest.raises(RetentionPolicyRegisterError):
        not_adopted(**{field: value})


@pytest.mark.parametrize("field", ["retention_period", "policy_reference", "effective_date"])
def test_an_adopted_entry_requires_its_complete_institutional_terms(field):
    assert adopted().adoption_status is RetentionAdoptionStatus.ADOPTED
    with pytest.raises(RetentionPolicyRegisterError):
        adopted(**{field: None})


@pytest.mark.parametrize(
    "changes",
    [
        {"adoption_status": "NOT_ADOPTED"},
        {"adoption_status": None},
        {"category_code": "GRADUATE_TRACER"},
        {"category_label": ""},
        {"category_label": " Padded"},
        {"category_label": None},
        {"category_label": "x" * 161},
        {"retention_period": 30},
        {"retention_period": "  "},
        {"retention_period": "x" * 501},
        {"policy_reference": " padded"},
        {"effective_date": "2030-01-01"},
        {"effective_date": datetime(2030, 1, 1, tzinfo=UTC)},
    ],
)
def test_register_entries_reject_malformed_or_coerced_values(changes):
    with pytest.raises(RetentionPolicyRegisterError):
        adopted(**changes)


def test_register_rejects_duplicates_empty_and_untyped_collections():
    entry = not_adopted()
    assert validate_register((entry,)) == (entry,)
    for entries in ((entry, entry), (), [entry], (register.project(entry),)):
        with pytest.raises(RetentionPolicyRegisterError):
            validate_register(entries)


def test_register_entries_are_immutable():
    with pytest.raises(dataclasses.FrozenInstanceError):
        register.REGISTER[0].adoption_status = RetentionAdoptionStatus.ADOPTED
    with pytest.raises(TypeError):
        register.REGISTER[0] = adopted()


def test_register_has_no_enforcement_path():
    module = BE / "compass/privacy_governance/retention_policy_register.py"
    assert module_imports(module) == {"__future__", "dataclasses", "datetime", "enum"}
    consumers = {
        path.relative_to(BE).as_posix()
        for path in (BE / "compass").rglob("*.py")
        if any("retention_policy_register" in name for name in module_imports(path, names=True))
    }
    # Only the read-only oversight route consumes the register: no task, executor or schedule.
    assert consumers == {"compass/privacy_governance/retention_api.py"}


# --- Read-only oversight API --------------------------------------------------------------------


def test_dpo_reads_the_minimized_register_without_reading_domain_records(dpo):
    _, queued, completed = legacy_world(dpo)
    before = ledger_snapshot()
    client = auth_client(dpo)
    with (
        CaptureQueriesContext(connection) as queries,
        patch("celery.app.task.Task.apply_async") as dispatch,
    ):
        response = client.get(POLICIES)
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"items"}
    assert body["items"] == [
        {
            "category_code": entry.category_code.value,
            "category_label": entry.category_label,
            "adoption_status": "NOT_ADOPTED",
            "retention_period": None,
            "policy_reference": None,
            "effective_date": None,
        }
        for entry in register.REGISTER
    ]
    # Nothing a retired ledger once referenced is served, and no duration is implied.
    serialized = json.dumps(body)
    for value in (queued.source_id, completed.source_id, queued.pk, queued.rule_id, "30"):
        assert str(value) not in serialized
    sql = " ".join(query["sql"].lower() for query in queries.captured_queries)
    for table in ("privacy_governance_", "ecounseling_", "graduate_tracer_"):
        assert table not in sql
    dispatch.assert_not_called()
    assert ledger_snapshot() == before


def test_an_adopted_entry_is_projected_verbatim(dpo, monkeypatch):
    entry = adopted(category_code=RetentionPolicyCategory.ECOUNSELING_TRANSCRIPT)
    monkeypatch.setattr(register, "REGISTER", validate_register((entry,)))
    item = auth_client(dpo).get(POLICIES).json()["items"][0]
    assert item == {
        "category_code": "ECOUNSELING_TRANSCRIPT",
        "category_label": "Synthetic category",
        "adoption_status": "ADOPTED",
        "retention_period": "SYNTHETIC TEST WORDING - not institutional policy",
        "policy_reference": "SYNTHETIC-REFERENCE - not institutional policy",
        "effective_date": "2030-01-01",
    }


def test_retention_oversight_requires_authentication():
    sync_policy()
    response = Client().get(POLICIES)
    assert response.status_code == 401


@pytest.mark.parametrize(
    "role",
    ["STUDENT", "GUIDANCE_SERVICES_STAFF", "COUNSELOR", "IT_ADMIN", "INSTITUTIONAL_OFFICER"],
)
def test_retention_oversight_rejects_accounts_without_the_view_capability(dpo, role):
    other = make_user(f"{role.lower()}@example.edu", role=role)
    response = auth_client(other).get(POLICIES)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "permission_denied"
    assert auth_client(make_head()).get(POLICIES).status_code == 403


def test_view_follows_effective_capability_overrides(dpo):
    view = Capability.objects.get(code=VIEW)
    UserCapabilityOverride.objects.create(
        user=dpo, capability=view, effect="REVOKE", reason="Synthetic revoke"
    )
    assert auth_client(dpo).get(POLICIES).status_code == 403
    reader = make_user("exceptional-reader@example.edu")
    UserCapabilityOverride.objects.create(
        user=reader, capability=view, effect="GRANT", reason="Synthetic exceptional view"
    )
    assert auth_client(reader).get(POLICIES).status_code == 200


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_the_register_route_accepts_no_mutation(dpo, method):
    client = auth_client(dpo, recent_mfa=True)
    response = getattr(client, method)(POLICIES, data="{}", content_type="application/json")
    assert response.status_code == 405


# --- Legacy API retirement ----------------------------------------------------------------------


def retired_requests(rule, case):
    root = "/api/v1/privacy/retention"
    revision = {"expected_revision": 1}
    return [
        ("GET", f"{root}/categories", None),
        ("GET", f"{root}/summary", None),
        ("GET", f"{root}/rules", None),
        ("POST", f"{root}/rules", {"code": "SYNTHETIC"}),
        ("GET", f"{root}/rules/{rule.pk}", None),
        ("PATCH", f"{root}/rules/{rule.pk}", revision),
        ("POST", f"{root}/rules/{rule.pk}/activate", revision),
        ("POST", f"{root}/rules/{rule.pk}/retire", revision),
        ("GET", f"{root}/cases", None),
        ("GET", f"{root}/cases/{case.pk}", None),
        ("POST", f"{root}/cases/{case.pk}/hold", revision | {"reason": "Synthetic"}),
        ("POST", f"{root}/cases/{case.pk}/release-hold", revision),
        ("POST", f"{root}/cases/{case.pk}/approve", revision),
        ("POST", f"{root}/cases/{case.pk}/retry", revision),
    ]


@pytest.mark.parametrize("holder", ["dpo", "override"])
def test_retired_retention_routes_are_unreachable_for_any_authority(
    dpo, holder, django_capture_on_commit_callbacks
):
    rule, queued, _ = legacy_world(dpo)
    actor = dpo
    if holder == "override":
        actor = make_user("exceptional-authority@example.edu")
        UserCapabilityOverride.objects.create(
            user=actor,
            capability=Capability.objects.get(code=VIEW),
            effect="GRANT",
            reason="Synthetic exceptional view",
        )
    client = auth_client(actor, recent_mfa=True)
    before = ledger_snapshot()
    with (
        patch("celery.app.task.Task.apply_async") as dispatch,
        django_capture_on_commit_callbacks(execute=True) as callbacks,
    ):
        for method, path, payload in retired_requests(rule, queued):
            if method == "GET":
                response = client.get(path)
            else:
                response = (post_json if method == "POST" else patch_json)(client, path, payload)
            assert response.status_code == 404, (method, path, response.status_code)
            assert str(queued.source_id) not in response.content.decode()
    dispatch.assert_not_called()
    assert callbacks == []
    assert ledger_snapshot() == before


def test_openapi_omits_every_retired_operation_schema_and_capability():
    schema = api.get_openapi_schema()
    operation_ids = {
        operation["operationId"]
        for item in schema["paths"].values()
        for operation in item.values()
        if isinstance(operation, dict) and "operationId" in operation
    }
    assert operation_ids.isdisjoint(RETIRED_OPERATIONS)
    retention_paths = {
        path: set(item) for path, item in schema["paths"].items() if "/privacy/retention" in path
    }
    assert retention_paths == {POLICIES: {"get"}}
    operation = schema["paths"][POLICIES]["get"]
    assert operation["operationId"] == "privacyGovernanceListRetentionPolicies"
    assert operation["security"] == [{"OpaqueSessionAuth": []}]
    assert {str(status) for status in operation["responses"]} == {"200", "401", "403"}
    schemas = schema["components"]["schemas"]
    assert set(schemas).isdisjoint(RETIRED_SCHEMAS)
    entry = schemas["RetentionPolicyEntryResponse"]
    assert set(entry["properties"]) == FIELDS and set(entry["required"]) == FIELDS
    assert entry["additionalProperties"] is False
    assert schemas["RetentionAdoptionStatus"]["enum"] == ["NOT_ADOPTED", "ADOPTED"]
    capability_enum = set(schemas["CapabilityCode"]["enum"])
    assert VIEW in capability_enum and capability_enum.isdisjoint(RETIRED)


def test_every_registered_operation_is_documented_and_none_reaches_disposition():
    registered = []
    for _, router in api._routers:
        for path, view in router.path_operations.items():
            for operation in view.operations:
                registered.append((path, operation))
    assert all(operation.include_in_schema for _, operation in registered)
    schema = api.get_openapi_schema()
    methods = {"get", "post", "put", "patch", "delete"}
    documented = sum(len(methods & set(item)) for item in schema["paths"].values())
    assert len(registered) == documented
    retention_routes = [
        (path, tuple(operation.methods), operation.view_func.__name__)
        for path, operation in registered
        if operation.view_func.__module__ == "compass.privacy_governance.retention_api"
    ]
    assert retention_routes == [("/retention/policies", ("GET",), "retention_policies")]
    # The fail-closed services from PG-1A PR 1 have no production caller left.
    services = {"create_rule", "update_rule", "transition_rule", "change_hold", "approve_case"}
    for path in (BE / "compass").rglob("*.py"):
        if path.name == "retention.py" and path.parent.name == "privacy_governance":
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Attribute) and node.attr in services:
                assert not (isinstance(node.value, ast.Name) and node.value.id == "retention"), path


# --- Capability retirement ----------------------------------------------------------------------


def test_retired_capabilities_leave_the_canonical_identity_policy():
    assert set(RETIRED) <= set(RETIRED_CAPABILITY_CODES)
    assert {
        "institutional_forms.manage",
        "document_branding.view",
        "document_branding.manage",
    } <= set(RETIRED_CAPABILITY_CODES)
    assert set(RETIRED).isdisjoint(CAPABILITY_CODES)
    for grants in (*ROLE_CAPABILITY_GRANTS.values(), *DESIGNATION_CAPABILITY_GRANTS.values()):
        assert set(RETIRED).isdisjoint(grants)
    for code, required in CAPABILITY_DEPENDENCIES.items():
        assert code not in RETIRED and set(RETIRED).isdisjoint(required)
    assert DESIGNATION_CAPABILITY_GRANTS["DPO"] == DPO_AUTHORITY
    (view,) = [item for item in CAPABILITY_DEFINITIONS if item.code == VIEW]
    assert view.name == "View retention policy oversight"
    assert "code-owned retention policy register" in view.description
    assert "no rule, hold, approval, or disposition authority" in view.description
    assert VIEW not in CAPABILITY_DEPENDENCIES


def persisted_grants():
    return (
        set(RoleCapability.objects.values_list("role__code", "capability__code")),
        set(DesignationCapability.objects.values_list("designation__code", "capability__code")),
        set(
            UserCapabilityOverride.objects.values_list("user__email", "capability__code", "effect")
        ),
    )


def test_sync_purges_persisted_retired_authority_and_is_idempotent():
    sync_policy()
    dpo = make_dpo()
    officer = make_user("legacy-override@example.edu")
    head = make_head()
    UserCapabilityOverride.objects.create(
        user=head,
        capability=Capability.objects.get(code="reports.view"),
        effect="REVOKE",
        reason="Unrelated synthetic override",
    )
    record_event(
        context=AuditContext.system(),
        action=actions.DISPOSITION_APPROVED,
        outcome="SUCCESS",
        target_type="privacy.disposition.case",
        target_id="00000000-0000-0000-0000-000000000001",
        metadata={"category": "GRADUATE_TRACER", "rule_revision": 2},
    )
    unrelated = persisted_grants()
    # Pre-ADR-115 persisted state: retired rows, DPO grants, a role grant and an override.
    Capability.objects.filter(code=VIEW).update(name="View retention and disposition")
    for code in RETIRED:
        capability = Capability.objects.create(code=code, name=f"Legacy {code}")
        DesignationCapability.objects.create(
            designation=Designation.objects.get(code="DPO"), capability=capability
        )
        RoleCapability.objects.create(
            role=Role.objects.get(code="INSTITUTIONAL_OFFICER"), capability=capability
        )
        UserCapabilityOverride.objects.create(
            user=officer, capability=capability, effect="GRANT", reason="Legacy override"
        )
    history = list(AuditEvent.objects.order_by("pk").values())

    first = sync_identity_policy()
    assert (
        first.retired_role_grants_deleted,
        first.retired_designation_grants_deleted,
        first.retired_overrides_deleted,
        first.retired_capabilities_deleted,
    ) == (2, 2, 2, 2)
    assert first.capabilities_updated == 1
    assert not Capability.objects.filter(code__in=RETIRED).exists()
    assert persisted_grants() == unrelated
    assert Capability.objects.get(code=VIEW).name == "View retention policy oversight"
    assert effective_capabilities(dpo) == DPO_AUTHORITY
    assert effective_capabilities(officer) == frozenset()
    for code in RETIRED:
        assert not dpo.has_capability(code) and not officer.has_capability(code)

    second = sync_identity_policy()
    assert all(getattr(second, field.name) == 0 for field in dataclasses.fields(second))
    assert persisted_grants() == unrelated
    # Historical events are untouched; each sync only appends its own summary event.
    kept = [event["id"] for event in history]
    assert list(AuditEvent.objects.filter(pk__in=kept).order_by("pk").values()) == history
    appended = AuditEvent.objects.exclude(pk__in=kept).values_list("action", flat=True)
    assert set(appended) == {actions.IDENTITY_POLICY_SYNCED}


@pytest.mark.parametrize("code", RETIRED)
def test_an_override_cannot_restore_a_retired_capability(dpo, code):
    admin = make_user("identity-admin@example.edu", role="IT_ADMIN")
    assert admin.has_capability("accounts.manage")
    with pytest.raises(InvalidManagementInput):
        set_capability_override(
            actor=admin,
            actor_session=None,
            target_id=dpo.pk,
            context=AuditContext.system(),
            capability=code,
            effect="GRANT",
            reason="Attempt to restore retired authority",
        )
    assert not UserCapabilityOverride.objects.filter(capability__code=code).exists()


@pytest.mark.parametrize(
    "role", ["IT_ADMIN", "COUNSELOR", "GUIDANCE_SERVICES_STAFF", "STUDENT", "INSTITUTIONAL_OFFICER"]
)
def test_no_role_gains_retention_or_disposition_authority(dpo, role):
    other = make_user(f"baseline-{role.lower()}@example.edu", role=role)
    for actor in (other, make_head(f"head-{role.lower()}@example.edu")):
        assert not any(
            code.startswith("privacy_governance.") for code in effective_capabilities(actor)
        )
    assert effective_capabilities(dpo) == DPO_AUTHORITY


def test_dpo_keeps_notices_and_activity_alongside_read_only_oversight(dpo):
    client = auth_client(dpo)
    assert client.get(POLICIES).status_code == 200
    assert client.get("/api/v1/privacy/notices").status_code == 200
    assert client.get("/api/v1/privacy/activity").status_code == 200
    assert client.get("/api/v1/graduate-tracer/responses").status_code == 403
