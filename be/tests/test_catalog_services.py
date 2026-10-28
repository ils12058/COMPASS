"""Catalog identity, authorization, mutation, impact, API and Audit contracts."""

from __future__ import annotations

import json
from datetime import timedelta
from uuid import uuid4

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from compass.accounts.models import Role, UserCapabilityOverride
from compass.accounts.policy import (
    CATALOG_ELIGIBLE_ROLES,
    DESIGNATION_CAPABILITY_GRANTS,
    ROLE_CAPABILITY_GRANTS,
)
from compass.accounts.services import set_user_capability_override
from compass.audit.models import AuditEvent
from compass.authentication.models import AuthSession, TOTPFactor
from compass.authentication.sessions import MFASetupRequired, RecentMFARequired
from compass.organization import catalog_services as cs
from compass.organization.models import (
    Campus,
    CatalogInitialization,
    College,
    CounselorResponsibility,
    Program,
    StudentAffiliation,
)
from tests.catalog_test_helpers import authority, client_for, hierarchy, manager, student

pytestmark = pytest.mark.django_db


@pytest.fixture
def setup():
    user, issued = manager()
    return authority(user, issued), hierarchy(), issued


@pytest.mark.parametrize(
    "role", ["IT_ADMIN", "COUNSELOR", "GUIDANCE_SERVICES_STAFF", "STUDENT", "INSTITUTIONAL_OFFICER"]
)
def test_no_role_or_designation_baseline_grants(role):
    user, _ = manager(role, grant=False)
    assert not user.has_capability("organization.catalog.manage")
    assert all(
        "organization.catalog.manage" not in grants
        for grants in (*ROLE_CAPABILITY_GRANTS.values(), *DESIGNATION_CAPABILITY_GRANTS.values())
    )
    if role not in CATALOG_ELIGIBLE_ROLES:
        with pytest.raises(ValueError, match="eligible staff"):
            set_user_capability_override(
                user=user,
                capability="organization.catalog.manage",
                effect="GRANT",
                reason="Synthetic",
            )
        # Even a malformed direct ORM grant cannot produce usable authority.
        from compass.accounts.models import Capability

        UserCapabilityOverride.objects.create(
            user=user,
            capability=Capability.objects.get(code="organization.catalog.manage"),
            effect="GRANT",
            reason="Malformed synthetic fixture",
        )
        assert not user.has_capability("organization.catalog.manage")


@pytest.mark.parametrize("role", sorted(CATALOG_ELIGIBLE_ROLES))
def test_explicit_eligible_authority_and_no_confidential_escalation(role):
    user, issued = manager(role)
    CatalogInitialization.objects.create(source="ADOPTED")
    assert user.has_capability("organization.catalog.manage")
    item = cs.create_campus(
        **authority(user, issued), code=" new-1 ", name=" New Campus ", is_active=False
    )
    assert (item.code, item.name, item.resource_version) == ("NEW-1", "New Campus", 1)
    if role == "IT_ADMIN":
        assert not user.has_capability("counseling.view_assigned")
        assert not user.has_capability("good_moral.view")


@pytest.mark.parametrize(
    "entity,create,extra",
    [
        (Campus, cs.create_campus, {}),
        (College, cs.create_college, {"parent": "campus_id"}),
        (Program, cs.create_program, {"parent": "college_id"}),
    ],
)
def test_create_identity_uniqueness_and_parent_scope(setup, entity, create, extra):
    auth, (c, k, p), _ = setup
    inputs = dict(code=" new-2 ", name=" Official Name ", is_active=True)
    if extra:
        inputs[extra["parent"]] = c.pk if entity is College else k.pk
    if entity is Program:
        inputs.update(
            academic_classification="BACHELORS",
            year_level_policy_status="CONFIGURED",
            applicable_year_levels=[1, 3, 5],
        )
    item = create(**auth, **inputs)
    assert item.resource_version == 1 and item.code == "NEW-2" and item.name == "Official Name"
    with pytest.raises(cs.CatalogError, match="already exists") as error:
        create(**auth, **{**inputs, "code": "NEW-2"})
    assert error.value.code == "catalog_duplicate_code"
    assert entity.objects.filter(code="NEW-2").count() == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("code", ""),
        ("code", "a b"),
        ("code", "a/1"),
        ("code", "é"),
        ("code", "x" * 33),
        ("name", " "),
        ("name", "x" * 161),
        ("name", "bad\x00"),
        ("is_active", 1),
    ],
)
def test_create_rejects_invalid_unbounded_or_control_values(setup, field, value):
    auth, _, _ = setup
    with pytest.raises(cs.CatalogError) as error:
        cs.create_campus(
            **auth, **{**dict(code="VALID", name="Valid", is_active=True), field: value}
        )
    assert error.value.status == 422


@pytest.mark.parametrize(
    "entity,rename",
    [(Campus, cs.rename_campus), (College, cs.rename_college), (Program, cs.rename_program)],
)
def test_rename_preserves_identity_versions_noop_and_audit(setup, entity, rename):
    auth, items, _ = setup
    item = next(i for i in items if isinstance(i, entity))
    original = {
        f.attname: getattr(item, f.attname)
        for f in item._meta.fields
        if f.name not in {"name", "resource_version", "updated_at"}
    }
    updated = rename(**auth, target_id=item.pk, expected_resource_version=1, name=" Renamed ")
    assert updated.pk == item.pk and updated.resource_version == 2
    assert all(getattr(updated, key) == value for key, value in original.items())
    event = AuditEvent.objects.get(target_id=str(item.pk), metadata__catalog_change=1)
    assert event.actor_user_id == auth["actor"].pk and event.metadata["changed_fields"] == ["name"]
    assert (
        event.metadata["before"]["name"] == item.name
        and event.metadata["after"]["name"] == "Renamed"
    )
    rename(**auth, target_id=item.pk, expected_resource_version=2, name=" Renamed ")
    assert (
        AuditEvent.objects.filter(target_id=str(item.pk), metadata__catalog_change=1).count() == 1
    )
    with pytest.raises(cs.CatalogError) as error:
        rename(**auth, target_id=item.pk, expected_resource_version=1, name="Stale")
    assert error.value.code == "catalog_stale_version"


@pytest.mark.parametrize("model", [Campus, College, Program])
@pytest.mark.parametrize("version", [0, -1])
def test_database_rejects_nonpositive_version(setup, model, version):
    _, items, _ = setup
    item = next(i for i in items if isinstance(i, model))
    with pytest.raises(IntegrityError), transaction.atomic():
        model.objects.filter(pk=item.pk).update(resource_version=version)


@pytest.mark.parametrize(
    "defect",
    [
        "inactive",
        "revoked",
        "expired_override",
        "dependency",
        "wrong_role",
        "invalid_session",
        "foreign_session",
        "expired_session",
        "revoked_session",
        "missing_factor",
        "expired_mfa",
        "forged_session",
    ],
)
def test_service_reloads_authentication_and_authority(setup, defect):
    auth, _, issued = setup
    user = auth["actor"]
    session = issued.session
    if defect == "inactive":
        type(user).objects.filter(pk=user.pk).update(is_active=False)
    elif defect == "revoked":
        UserCapabilityOverride.objects.filter(
            user=user, capability__code="organization.catalog.manage"
        ).update(effect="REVOKE")
    elif defect == "expired_override":
        UserCapabilityOverride.objects.filter(user=user).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
    elif defect == "dependency":
        set_user_capability_override(
            user=user, capability="organization.structure.view", effect="REVOKE", reason="Synthetic"
        )
    elif defect == "wrong_role":
        type(user).objects.filter(pk=user.pk).update(role=Role.objects.get(code="STUDENT"))
    elif defect == "invalid_session":
        auth["actor_session"] = None
    elif defect == "foreign_session":
        auth["actor_session"] = manager()[1].session
    elif defect == "forged_session":
        # A constructed object with verified_at set cannot override persisted stale evidence.
        AuthSession.objects.filter(pk=session.pk).update(mfa_verified_at=None)
    elif defect == "expired_session":
        AuthSession.objects.filter(pk=session.pk).update(
            created_at=timezone.now() - timedelta(days=3),
            expires_at=timezone.now() - timedelta(days=1),
        )
    elif defect == "revoked_session":
        AuthSession.objects.filter(pk=session.pk).update(revoked_at=timezone.now())
    elif defect == "missing_factor":
        TOTPFactor.objects.filter(user=user).delete()
    elif defect == "expired_mfa":
        AuthSession.objects.filter(pk=session.pk).update(
            mfa_verified_at=timezone.now() - timedelta(days=1)
        )
    with pytest.raises((cs.CatalogError, MFASetupRequired, RecentMFARequired)):
        cs.create_campus(**auth, code="DENIED", name="Denied", is_active=True)
    assert not Campus.objects.filter(code="DENIED").exists()
    assert not AuditEvent.objects.filter(action="organization.campus.created").exists()


def test_uninitialized_catalog_and_context_mismatch_fail_closed(setup):
    auth, _, _ = setup
    from compass.audit.context import AuditContext

    with pytest.raises(cs.CatalogError) as error:
        cs.create_campus(
            **{**auth, "context": AuditContext.system()}, code="A", name="A", is_active=True
        )
    assert error.value.status == 403


def test_without_receipt_refuses_mutation():
    user, issued = manager()
    with pytest.raises(cs.CatalogError) as error:
        cs.create_campus(**authority(user, issued), code="A", name="A", is_active=True)
    assert error.value.code == "catalog_not_initialized"


@pytest.mark.parametrize(
    "entity,status",
    [
        (Campus, cs.set_campus_active),
        (College, cs.set_college_active),
        (Program, cs.set_program_active),
    ],
)
def test_inactive_drafts_and_parent_activation_rules(setup, entity, status):
    auth, (c, k, p), _ = setup
    # Fixture intentionally inconsistent, proving active ancestry checks independent of child flag.
    Campus.objects.filter(pk=c.pk).update(is_active=False)
    College.objects.filter(pk=k.pk).update(is_active=False)
    Program.objects.filter(pk=p.pk).update(is_active=False)
    item = {Campus: c, College: k, Program: p}[entity]
    if entity is not Campus:
        with pytest.raises(cs.CatalogError) as error:
            status(**auth, target_id=item.pk, expected_resource_version=1, is_active=True)
        assert error.value.code == "catalog_inactive_parent"
    else:
        updated = status(**auth, target_id=item.pk, expected_resource_version=1, is_active=True)
        assert updated.resource_version == 2
        assert not College.objects.get(pk=k.pk).is_active


def test_incomplete_draft_policy_requires_deliberate_configured_activation(setup):
    auth, (c, k, p), _ = setup
    args = dict(
        college_id=k.pk,
        code="DRAFT",
        name="Unknown",
        is_active=False,
        academic_classification=None,
        year_level_policy_status="PENDING_POLICY",
        applicable_year_levels=None,
    )
    draft = cs.create_program(**auth, **args)
    with pytest.raises(cs.CatalogError) as error:
        cs.set_program_active(
            **auth, target_id=draft.pk, expected_resource_version=1, is_active=True
        )
    assert error.value.code == "catalog_policy_approval_required"
    with pytest.raises(cs.CatalogError):
        cs.create_program(**auth, **{**args, "code": "BAD", "is_active": True})
    cs.update_program_policy(
        **auth,
        target_id=draft.pk,
        expected_resource_version=1,
        academic_classification="BACHELORS",
        year_level_policy_status="CONFIGURED",
        applicable_year_levels=[1, 2, 3, 4, 5],
    )
    updated = cs.set_program_active(
        **auth, target_id=draft.pk, expected_resource_version=2, is_active=True
    )
    assert updated.resource_version == 3


def test_impact_rechecks_stale_preview_all_student_lifecycles_and_stale_responsibility(setup):
    auth, (c, k, p), _ = setup
    Program.objects.filter(pk=p.pk).update(is_active=False)
    preview = cs.get_catalog_impact(actor=auth["actor"], model=College, target_id=k.pk)
    assert preview.can_deactivate
    s = student()
    StudentAffiliation.objects.create(student=s, college=k)
    for lifecycle in ("CURRENT", "GRADUATED", "FORMER"):
        type(s).objects.filter(pk=s.pk).update(student_lifecycle_status=lifecycle)
        impact = cs.get_catalog_impact(actor=auth["actor"], model=College, target_id=k.pk)
        assert impact.counts["active_student_affiliations"] == 1
        with pytest.raises(cs.CatalogError, match="active_student_affiliations"):
            cs.set_college_active(
                **auth,
                target_id=k.pk,
                expected_resource_version=preview.resource_version,
                is_active=False,
            )
    type(s).objects.filter(pk=s.pk).update(is_active=False)
    CounselorResponsibility.objects.create(college=k, counselor=auth["actor"])
    with pytest.raises(cs.CatalogError, match="counselor_responsibilities"):
        cs.set_college_active(**auth, target_id=k.pk, expected_resource_version=1, is_active=False)
    CounselorResponsibility.objects.filter(college=k).delete()
    impact = cs.get_catalog_impact(actor=auth["actor"], model=College, target_id=k.pk)
    assert impact.can_deactivate and impact.warnings[0].code == "inactive_account_affiliations"
    cs.set_college_active(**auth, target_id=k.pk, expected_resource_version=1, is_active=False)
    assert StudentAffiliation.objects.filter(student=s, college=k).exists()


def test_campus_blockers_include_inconsistent_inactive_child_affiliations(setup):
    auth, (c, k, p), _ = setup
    College.objects.filter(pk=k.pk).update(is_active=False)
    s = student()
    StudentAffiliation.objects.create(student=s, college=k)
    with pytest.raises(cs.CatalogError, match="active_student_affiliations"):
        cs.set_campus_active(**auth, target_id=c.pk, expected_resource_version=1, is_active=False)


@pytest.mark.parametrize("operation", ["rename", "status", "policy", "create"])
def test_audit_failure_rolls_back_entity_and_version(setup, monkeypatch, operation):
    auth, (c, k, p), _ = setup

    def fail(**kwargs):
        raise RuntimeError("Synthetic Audit persistence failure")

    monkeypatch.setattr(cs, "record_event", fail)
    with pytest.raises(RuntimeError, match="Audit"):
        if operation == "rename":
            cs.rename_program(**auth, target_id=p.pk, expected_resource_version=1, name="Changed")
        elif operation == "status":
            cs.set_program_active(
                **auth, target_id=p.pk, expected_resource_version=1, is_active=False
            )
        elif operation == "policy":
            cs.update_program_policy(
                **auth,
                target_id=p.pk,
                expected_resource_version=1,
                academic_classification="BACHELORS",
                year_level_policy_status="CONFIGURED",
                applicable_year_levels=[1, 2],
            )
        else:
            cs.create_campus(**auth, code="ROLLED", name="Rolled", is_active=True)
    p.refresh_from_db()
    assert (
        p.resource_version == 1
        and p.is_active
        and p.name == "Program"
        and p.applicable_year_levels == [1, 2, 3, 4]
    )
    assert not Campus.objects.filter(code="ROLLED").exists()


def test_history_is_bounded_target_specific_safe_projection(setup):
    auth, (c, k, p), _ = setup
    for version in (1, 2, 3):
        cs.rename_program(
            **auth, target_id=p.pk, expected_resource_version=version, name=f"Name {version}"
        )
    cs.rename_campus(**auth, target_id=c.pk, expected_resource_version=1, name="Other target")
    history = cs.get_catalog_history(
        actor=auth["actor"], model=Program, target_id=p.pk, page_size=2
    )
    assert history["has_next"] and len(history["items"]) == 2
    assert history["items"][0]["resource_version_after"] == 4
    assert all(i["actor_id"] == auth["actor"].pk for i in history["items"])
    assert (
        not {"metadata", "ip_address", "user_agent_summary", "request_id", "actor_email"}
        & history["items"][0].keys()
    )
    assert (
        len(
            cs.get_catalog_history(
                actor=auth["actor"], model=Program, target_id=p.pk, page=2, page_size=2
            )["items"]
        )
        == 1
    )
    with pytest.raises(cs.CatalogError):
        cs.get_catalog_history(actor=auth["actor"], model=Program, target_id=p.pk, page_size=51)


@pytest.mark.parametrize(
    "extra",
    [
        {"code": "CHANGED"},
        {"campus_id": str(uuid4())},
        {"college_id": str(uuid4())},
        {"mfa_verified": True},
        {"can_deactivate": True},
    ],
)
def test_strict_api_rejects_structural_and_security_fields(setup, extra):
    auth, (_, _, p), issued = setup
    client, headers = client_for(issued)
    response = client.put(
        f"/api/v1/organization/programs/{p.pk}/name",
        data=json.dumps(
            dict(name="Rename", expected_resource_version=1, basis="Synthetic", **extra)
        ),
        content_type="application/json",
        **headers,
    )
    assert response.status_code == 422
    p.refresh_from_db()
    assert p.resource_version == 1


def test_api_mfa_csrf_status_history_and_errors(setup):
    auth, (c, k, p), issued = setup
    client, headers = client_for(issued)
    path = f"/api/v1/organization/programs/{p.pk}/name"
    payload = dict(name="New", expected_resource_version=1, basis="Synthetic")
    response = client.put(path, data=json.dumps(payload), content_type="application/json")
    assert response.status_code == 403
    response = client.put(
        path, data=json.dumps(payload), content_type="application/json", **headers
    )
    assert response.status_code == 200 and response.json()["resource_version"] == 2
    assert client.get(f"/api/v1/organization/programs/{p.pk}/impact").json()["target_id"] == str(
        p.pk
    )
    history = client.get(f"/api/v1/organization/programs/{p.pk}/history").json()
    assert history["items"][0]["actor_id"] == str(auth["actor"].pk)
    response = client.put(
        path, data=json.dumps(payload), content_type="application/json", **headers
    )
    assert (
        response.status_code == 409 and response.json()["error"]["code"] == "catalog_stale_version"
    )
    AuthSession.objects.filter(pk=issued.session.pk).update(mfa_verified_at=None)
    response = client.put(
        path, data=json.dumps(payload), content_type="application/json", **headers
    )
    assert response.status_code == 403 and response.json()["error"]["code"] == "recent_mfa_required"
    TOTPFactor.objects.filter(user=auth["actor"]).delete()
    response = client.put(
        path, data=json.dumps(payload), content_type="application/json", **headers
    )
    assert response.json()["error"]["code"] == "mfa_setup_required"


@pytest.mark.parametrize(
    "role", ["IT_ADMIN", "COUNSELOR", "GUIDANCE_SERVICES_STAFF", "STUDENT", "INSTITUTIONAL_OFFICER"]
)
def test_http_catalog_permission_is_separate_from_role_and_relationship_management(role):
    user, issued = manager(role, grant=False)
    c, k, p = hierarchy()
    client, headers = client_for(issued)
    payload = dict(code="DENIED", name="Denied", is_active=False, basis="Synthetic")
    response = client.post(
        "/api/v1/organization/campuses",
        data=json.dumps(payload),
        content_type="application/json",
        **headers,
    )
    assert response.status_code == 403
    for route in ("impact", "history"):
        assert client.get(f"/api/v1/organization/programs/{p.pk}/{route}").status_code == 403
    assert not Campus.objects.filter(code="DENIED").exists()


@pytest.mark.parametrize("entity", ["campus", "college", "program"])
def test_http_create_and_status_operations_return_persisted_versions(setup, entity):
    auth, (c, k, p), issued = setup
    client, headers = client_for(issued)
    payload = dict(code="API", name="API record", is_active=False, basis="Synthetic")
    plural = "campuses" if entity == "campus" else entity + "s"
    if entity == "college":
        payload["campus_id"] = str(c.pk)
    if entity == "program":
        payload.update(
            college_id=str(k.pk),
            academic_classification="BACHELORS",
            year_level_policy_status="CONFIGURED",
            applicable_year_levels=[1, 2, 3, 4],
        )
    response = client.post(
        f"/api/v1/organization/{plural}",
        data=json.dumps(payload),
        content_type="application/json",
        **headers,
    )
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["resource_version"] == 1 and not body["is_active"]
    response = client.put(
        f"/api/v1/organization/{plural}/{body['id']}/active",
        data=json.dumps(dict(is_active=True, expected_resource_version=1, basis="Synthetic")),
        content_type="application/json",
        **headers,
    )
    assert response.status_code == 200, response.content
    assert response.json()["resource_version"] == 2


@pytest.mark.parametrize("levels", [[], [True], [1.0], ["1"], [2, 1], [1, 1], [0], [11], [None]])
def test_policy_operations_share_org1_strict_validator(setup, levels):
    auth, (_, _, p), _ = setup
    with pytest.raises(cs.CatalogError) as error:
        cs.update_program_policy(
            **auth,
            target_id=p.pk,
            expected_resource_version=1,
            academic_classification="BACHELORS",
            year_level_policy_status="CONFIGURED",
            applicable_year_levels=levels,
        )
    assert error.value.status == 422
    p.refresh_from_db()
    assert p.resource_version == 1


def test_noop_policy_and_status_preserve_version_audit_and_timestamp(setup):
    auth, (_, _, p), _ = setup
    original = p.updated_at
    cs.set_program_active(**auth, target_id=p.pk, expected_resource_version=1, is_active=True)
    cs.update_program_policy(
        **auth,
        target_id=p.pk,
        expected_resource_version=1,
        academic_classification="BACHELORS",
        year_level_policy_status="CONFIGURED",
        applicable_year_levels=[1, 2, 3, 4],
    )
    p.refresh_from_db()
    assert p.resource_version == 1 and p.updated_at == original
    assert not AuditEvent.objects.filter(target_id=str(p.pk), metadata__catalog_change=1).exists()


def test_policy_and_retirement_preserve_submitted_inventory_and_pending_f4_facts(setup):
    from compass.good_moral.models import GoodMoralRequest
    from tests.test_catalog_concurrency import f4, inventory_fixture

    auth, (_, _, p), _ = setup
    s, inventory = inventory_fixture(auth, p, submit=True)
    item = f4(s)
    impact = cs.get_catalog_impact(actor=auth["actor"], model=Program, target_id=p.pk)
    assert impact.can_deactivate and impact.counts["pending_f4"] == 1
    assert impact.counts["submitted_inventories"] == 1
    with pytest.raises(cs.CatalogError) as error:
        cs.update_program_policy(
            **auth,
            target_id=p.pk,
            expected_resource_version=1,
            academic_classification="MASTERS",
            year_level_policy_status="CONFIGURED",
            applicable_year_levels=[1],
        )
    assert error.value.code == "catalog_pending_f4_policy_decision_required"
    cs.rename_program(**auth, target_id=p.pk, expected_resource_version=1, name="New official name")
    cs.set_program_active(**auth, target_id=p.pk, expected_resource_version=2, is_active=False)
    inventory.refresh_from_db()
    item.refresh_from_db()
    assert inventory.course_currently_enrolled == "Program" and item.course_snapshot == "Program"
    assert item.status == "REQUESTED" and item.year_level_snapshot == "1st Year"
    assert GoodMoralRequest.objects.filter(pk=item.pk, inventory=inventory).exists()


def test_unknown_target_and_malformed_versions_have_stable_errors(setup):
    auth, (_, _, p), _ = setup
    with pytest.raises(cs.CatalogError) as error:
        cs.rename_program(**auth, target_id=uuid4(), expected_resource_version=1, name="Missing")
    assert error.value.status == 404
    for value in (None, True, 0, -1, "1"):
        with pytest.raises(cs.CatalogError) as error:
            cs.rename_program(
                **auth, target_id=p.pk, expected_resource_version=value, name="Bad version"
            )
        assert error.value.status == 422


def test_impact_open_office_work_is_blocked_and_history_is_counted_without_contents(setup):
    from compass.guidance_messages.models import GuidanceThread

    auth, (_, k, p), _ = setup
    Program.objects.filter(pk=p.pk).update(is_active=False)
    s = student()
    type(s).objects.filter(pk=s.pk).update(is_active=False)
    thread = GuidanceThread.objects.create(
        student=s, kind="OFFICE", routing_college=k, created_by=auth["actor"]
    )
    impact = cs.get_catalog_impact(actor=auth["actor"], model=College, target_id=k.pk)
    assert impact.counts["open_office_threads"] == 1 and not impact.can_deactivate
    with pytest.raises(cs.CatalogError, match="open_office_threads"):
        cs.set_college_active(**auth, target_id=k.pk, expected_resource_version=1, is_active=False)
    GuidanceThread.objects.filter(pk=thread.pk).update(
        status="RESOLVED", resolved_at=timezone.now(), resolved_by=auth["actor"]
    )
    impact = cs.get_catalog_impact(actor=auth["actor"], model=College, target_id=k.pk)
    assert impact.counts["resolved_threads"] == 1 and impact.can_deactivate
    assert not {"student", "messages", "body", "student_id"} & impact.counts.keys()


def test_account_management_rejects_unsupported_catalog_delegation(setup):
    from compass.account_management.services import InvalidManagementInput, set_capability_override

    auth, _, issued = setup
    target = student()
    with pytest.raises(InvalidManagementInput, match="eligible staff"):
        set_capability_override(
            actor=auth["actor"],
            actor_session=issued.session,
            target_id=target.pk,
            context=auth["context"],
            capability="organization.catalog.manage",
            effect="GRANT",
            reason="Synthetic role fence test",
        )
    assert not UserCapabilityOverride.objects.filter(
        user=target, capability__code="organization.catalog.manage"
    ).exists()


def test_rotated_credential_cannot_reuse_a_previously_resolved_session(setup):
    auth, (c, _, _), issued = setup
    from compass.authentication.sessions import rotate_auth_session_credential

    rotate_auth_session_credential(session_id=issued.session.pk)
    with pytest.raises(cs.CatalogError) as error:
        cs.rename_campus(**auth, target_id=c.pk, expected_resource_version=1, name="Denied")
    assert error.value.code == "invalid_session"


@pytest.mark.parametrize("role", sorted(CATALOG_ELIGIBLE_ROLES))
def test_explicit_catalog_grant_adds_only_catalog_authority(role):
    from compass.accounts.services import effective_capabilities

    user, _ = manager(role, grant=False)
    before = effective_capabilities(user)
    set_user_capability_override(
        user=user,
        capability="organization.catalog.manage",
        effect="GRANT",
        reason="Synthetic permission composition",
    )
    assert effective_capabilities(user) - before == {"organization.catalog.manage"}


def test_service_created_bachelor_supports_inventory_and_f4_without_seed_registration(setup):
    from tests.test_catalog_concurrency import f4, inventory_fixture

    auth, (_, k, _), _ = setup
    program = cs.create_program(
        **auth,
        college_id=k.pk,
        code="ADDITIONAL",
        name="Approved Synthetic Degree",
        is_active=True,
        academic_classification="BACHELORS",
        year_level_policy_status="CONFIGURED",
        applicable_year_levels=[1, 4, 5],
    )
    s, inventory = inventory_fixture(auth, program, submit=True)
    item = f4(s)
    assert (
        inventory.program_id == program.pk and inventory.course_currently_enrolled == program.name
    )
    assert item.course_snapshot == program.name and item.year_level_snapshot == "1st Year"
    from compass.good_moral.services import F4AcademicEligibility, _f4_academic_context

    assert (
        _f4_academic_context(program=program, year_level=5).status
        == F4AcademicEligibility.UNSUPPORTED_YEAR_LEVEL
    )


def test_adopted_unchanged_identity_and_names_are_not_normalized_or_falsely_audited(setup):
    auth, (_, _, p), _ = setup
    # Deliberate adoption sentinel, inserted before ordinary protected maintenance.
    Program.objects.filter(pk=p.pk).update(code="retained-code", name=" Retained name ")
    result = cs.rename_program(
        **auth, target_id=p.pk, expected_resource_version=1, name="Retained name"
    )
    assert result.resource_version == 1 and result.name == " Retained name "
    result = cs.set_program_active(
        **auth, target_id=p.pk, expected_resource_version=1, is_active=False
    )
    p.refresh_from_db()
    assert result.code == p.code == "retained-code" and result.name == p.name == " Retained name "
    event = AuditEvent.objects.get(target_id=str(p.pk), metadata__catalog_change=1)
    assert event.metadata["code"] == "retained-code"
    assert event.metadata["changed_fields"] == ["is_active"]
    assert event.metadata["before"]["name"] == event.metadata["after"]["name"] == " Retained name "
