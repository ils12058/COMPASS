"""Retirement acknowledgement, atomic cascades, retained work and active-only new references."""

import json
from datetime import date, timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from compass.accounts.confidential_profile import (
    AccountProfileConfidentialContent,
    write_account_profile_confidential_content,
)
from compass.accounts.models import Designation, UserDesignation
from compass.accounts.services import projected_capabilities, set_user_capability_override
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.counseling.case_coverage_models import CounselingCaseCoverage
from compass.counseling.case_coverage_work import pending_coverage_work
from compass.counseling.case_models import CounselingCase
from compass.graduate_tracer import services as tracer
from compass.guidance_followups import services as followups
from compass.guidance_followups.recovery import recoverable_queryset
from compass.guidance_messages import services as messages
from compass.organization import catalog_services as cs
from compass.organization.access_scope import resolve_operational_responsibility_scope
from compass.organization.faculty import faculty_affiliation_projection
from compass.organization.models import (
    Campus,
    College,
    CounselorResponsibility,
    FacultyAffiliation,
    Program,
)
from compass.organization.selection import active_programs
from compass.organization.services import (
    list_campuses,
    list_colleges,
    list_programs,
    resolve_default_counselor_for_student,
)
from compass.student_academics.models import StudentAcademicProfile
from compass.student_academics.reads import get_current_placement, student_is_placed_in_colleges
from compass.student_academics.services import StudentAcademicConflict, set_current_placement
from tests.catalog_test_helpers import (
    authority,
    client_for,
    hierarchy,
    manager,
    retirement_preview,
    student,
)
from tests.test_catalog_final_integration import new_work
from tests.test_graduate_tracer import valid_unemployed_payload

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("inventory_psgc")]


@pytest.fixture
def setup():
    user, issued = manager()
    return authority(user, issued), hierarchy(), issued


def retire(auth, item, *, cascade=False, preview=None):
    operation = {
        Campus: cs.set_campus_active,
        College: cs.set_college_active,
        Program: cs.set_program_active,
    }[type(item)]
    return operation(
        **auth,
        target_id=item.pk,
        expected_resource_version=item.resource_version,
        is_active=False,
        cascade=cascade,
        **(preview if preview is not None else retirement_preview(auth, item)),
    )


@pytest.mark.parametrize("kind", [Campus, College, Program])
def test_retire_preserves_operational_relationships_and_audits_each_target(setup, kind, settings):
    from cryptography.fernet import Fernet

    settings.GUIDANCE_FOLLOWUP_ENCRYPTION_KEYS = (Fernet.generate_key().decode(),)
    auth, items, _ = setup
    c, k, p = items
    counselor, _ = manager("COUNSELOR", grant=False)
    faculty, _ = manager("FACULTY", grant=False)
    s = student()
    profile = StudentAcademicProfile.objects.create(student=s, current_college=k)
    affiliation = FacultyAffiliation.objects.create(faculty=faculty, college=k, basis="Synthetic")
    responsibility = CounselorResponsibility.objects.create(counselor=counselor, college=k)
    thread = new_work("office", counselor, s)
    followup = new_work("followup", counselor, s)
    before = [
        type(row).objects.filter(pk=row.pk).values().get()
        for row in (profile, affiliation, responsibility, thread, followup)
    ]
    target = next(row for row in items if isinstance(row, kind))
    observed = cs.get_catalog_impact(actor=auth["actor"], model=kind, target_id=target.pk)
    if kind is not Program:
        assert {i.code for i in observed.warnings} >= {
            "active_student_placements",
            "active_faculty_affiliations",
            "counselor_responsibilities",
            "open_office_threads",
            "pending_operational_followups",
        }
    retire(auth, target, cascade=kind is not Program)
    for row, saved in zip(
        (profile, affiliation, responsibility, thread, followup), before, strict=True
    ):
        assert type(row).objects.filter(pk=row.pk).values().get() == saved
    assert get_current_placement(student_id=s.pk).college.is_usable
    assert student_is_placed_in_colleges(student_id=s.pk, college_ids=[k.pk])
    assert faculty_affiliation_projection(faculty)["active"]
    assert k.pk in resolve_operational_responsibility_scope(counselor).college_ids
    assert resolve_default_counselor_for_student(s).counselor == counselor
    assert messages.get_thread(actor=counselor, thread_id=thread.pk).pk == thread.pk
    assert followups.get_followup(actor=counselor, followup_id=followup.pk).pk == followup.pk
    assert not recoverable_queryset(actor=counselor).filter(pk=followup.pk).exists()
    expected_targets = items if kind is Campus else (k, p) if kind is College else (p,)
    events = AuditEvent.objects.filter(metadata__retirement__acknowledged_impact=True)
    assert events.count() == len(expected_targets)
    for row in expected_targets:
        row.refresh_from_db()
        assert row.is_retired and not row.is_active and row.resource_version == 2
        event = events.get(target_id=str(row.pk))
        assert event.actor_user_id == auth["actor"].pk
        assert event.metadata["retirement"]["cascade"] is (kind is not Program)
        assert "@" not in json.dumps(event.metadata)
    if kind is not Program:
        event = events.get(target_id=str(target.pk))
        assert event.metadata["retirement"]["warning_counts"]["active_student_placements"] == 1


@pytest.mark.parametrize("change", ["placement", "child_name", "child_replacement"])
def test_stale_preview_rejects_counts_or_child_changes_without_partial_retirement(setup, change):
    auth, (c, k, p), _ = setup
    preview = retirement_preview(auth, c)
    if change == "placement":
        StudentAcademicProfile.objects.create(student=student(), current_college=k)
    elif change == "child_name":
        cs.rename_program(**auth, target_id=p.pk, expected_resource_version=1, name="Updated child")
    else:
        p.delete()
        Program.objects.create(
            college=k,
            code="PROG",
            name="Program",
            academic_classification="BACHELORS",
            year_level_policy_status="CONFIGURED",
            applicable_year_levels=[1, 2, 3, 4],
        )
    with pytest.raises(cs.CatalogError) as error:
        retire(auth, c, cascade=True, preview=preview)
    assert error.value.code == "catalog_stale_impact"
    assert str(error.value) == "The impact changed. Review it again."
    assert Campus.objects.get(pk=c.pk).is_active
    assert College.objects.get(pk=k.pk).is_active
    assert not AuditEvent.objects.filter(metadata__retirement__acknowledged_impact=True).exists()


@pytest.mark.parametrize("kind", [Campus, College])
def test_parent_requires_cascade_and_preview_lists_children(setup, kind):
    auth, (c, k, p), _ = setup
    target = c if kind is Campus else k
    impact = cs.get_catalog_impact(actor=auth["actor"], model=kind, target_id=target.pk)
    assert {child.id for child in impact.active_children} == (
        {k.pk, p.pk} if kind is Campus else {p.pk}
    )
    with pytest.raises(cs.CatalogError) as error:
        retire(auth, target)
    assert error.value.code == "catalog_deactivation_blocked"
    assert not AuditEvent.objects.filter(metadata__retirement__acknowledged_impact=True).exists()


def test_cascade_audit_failure_rolls_back_parent_children_versions_and_audit(setup, monkeypatch):
    auth, (c, k, p), _ = setup
    original = cs.record_event
    calls = 0

    def fail_second(**kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("Synthetic audit failure")
        return original(**kwargs)

    monkeypatch.setattr(cs, "record_event", fail_second)
    with pytest.raises(RuntimeError, match="audit failure"):
        retire(auth, c, cascade=True)
    for row in (c, k, p):
        row.refresh_from_db()
        assert row.is_active and not row.is_retired and row.resource_version == 1
    assert not AuditEvent.objects.filter(metadata__retirement__acknowledged_impact=True).exists()


@pytest.mark.parametrize(
    "payload",
    [{}, {"acknowledged_impact": True}, {"acknowledged_impact": True, "impact_token": "forged"}],
)
def test_http_retirement_requires_authentic_acknowledgement(setup, payload):
    _, (_, _, p), issued = setup
    client, headers = client_for(issued)
    response = client.put(
        f"/api/v1/organization/programs/{p.pk}/active",
        data=json.dumps(
            {"expected_resource_version": 1, "is_active": False, "basis": "Synthetic", **payload}
        ),
        content_type="application/json",
        **headers,
    )
    assert response.status_code in {409, 422}
    p.refresh_from_db()
    assert p.is_active


def test_head_designation_has_usable_default_catalog_authority_and_revocation(setup):
    _, (c, _, _), _ = setup
    head, issued = manager("COUNSELOR", grant=False)
    UserDesignation.objects.create(
        user=head, designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR")
    )
    assert head.has_capability("organization.catalog.manage")
    assert "organization.catalog.manage" in projected_capabilities(head)
    auth = authority(head, issued)
    retire(auth, c, cascade=True)
    set_user_capability_override(
        user=head, capability="organization.catalog.manage", effect="REVOKE", reason="Synthetic"
    )
    with pytest.raises(cs.CatalogError) as error:
        cs.get_catalog_impact(actor=head, model=Campus, target_id=c.pk)
    assert error.value.status == 403


def test_retired_definitions_are_excluded_from_new_reference_choices_and_validators(setup):
    auth, (c, k, p), _ = setup
    retire(auth, c, cascade=True)
    assert not list_campuses(is_active=True)
    assert not list_colleges(is_active=True)
    assert not list_programs(is_active=True)
    assert not active_programs().exists()  # Inventory and Good Moral share this selector.
    assert tracer.get_classification_options() == ((), ())
    assert list_colleges()[0].pk == k.pk  # History/browse remains available.
    with pytest.raises(StudentAcademicConflict):
        set_current_placement(student_id=student().pk, college_id=k.pk, context=auth["context"])
    from compass.account_management.faculty import validate_faculty_college
    from compass.account_management.services import InvalidManagementInput

    with pytest.raises(InvalidManagementInput):
        validate_faculty_college(role="FACULTY", college_id=k.pk)


def test_tracer_refuses_new_retired_references_but_preserves_an_existing_draft(setup):
    auth, (_, k, p), _ = setup
    graduate = student()
    type(graduate).objects.filter(pk=graduate.pk).update(student_lifecycle_status="GRADUATED")
    graduate.refresh_from_db()
    write_account_profile_confidential_content(graduate, AccountProfileConfidentialContent())
    graduate.save(update_fields=["profile_confidential_content_ciphertext"])
    tracer.ensure_my_response(student=graduate, context=AuditContext.user(graduate))
    values = {
        **{
            key: value
            for key, value in valid_unemployed_payload().items()
            if key
            not in {
                "name",
                "email",
                "permanent_address",
                "telephone_contact_numbers",
                "mobile_number",
            }
        },
        "birth_date": date(2000, 1, 15),
        "graduated_college_id": str(k.pk),
        "graduated_program_id": str(p.pk),
    }
    draft = tracer.replace_my_draft(student=graduate, values=values)
    retire(auth, k, cascade=True)
    assert tracer.replace_my_draft(student=graduate, values=values).graduated_program_id == p.pk
    other = student()
    type(other).objects.filter(pk=other.pk).update(student_lifecycle_status="GRADUATED")
    other.refresh_from_db()
    write_account_profile_confidential_content(other, AccountProfileConfidentialContent())
    other.save(update_fields=["profile_confidential_content_ciphertext"])
    tracer.ensure_my_response(student=other, context=AuditContext.user(other))
    with pytest.raises(tracer.InvalidGraduateTracerInput, match="active college"):
        tracer.replace_my_draft(student=other, values=values)
    assert tracer.get_my_response(graduate).pk == draft.pk


def test_active_selectors_reject_inconsistent_inactive_ancestry(setup):
    _, (c, _, _), _ = setup
    Campus.objects.filter(pk=c.pk).update(is_active=False)
    assert not list_colleges(is_active=True)
    assert not list_programs(is_active=True)
    assert tracer.get_classification_options() == ((), ())


def test_http_preview_cascade_and_nonmanager_retirement_denial(setup):
    auth, (c, k, p), issued = setup
    client, headers = client_for(issued)
    preview = client.get(f"/api/v1/organization/campuses/{c.pk}/impact").json()
    assert {child["id"] for child in preview["active_children"]} == {str(k.pk), str(p.pk)}
    response = client.put(
        f"/api/v1/organization/campuses/{c.pk}/active",
        data=json.dumps(
            {
                "expected_resource_version": 1,
                "is_active": False,
                "basis": "Synthetic",
                "acknowledged_impact": True,
                "impact_token": preview["impact_token"],
                "cascade": True,
            }
        ),
        content_type="application/json",
        **headers,
    )
    assert response.status_code == 200 and response.json()["resource_version"] == 2
    nonmanager, session = manager("COUNSELOR", grant=False)
    _, _, fresh = hierarchy()
    token = retirement_preview(auth, fresh)["impact_token"]
    other, other_headers = client_for(session)
    response = other.put(
        f"/api/v1/organization/programs/{fresh.pk}/active",
        data=json.dumps(
            {
                "expected_resource_version": 1,
                "is_active": False,
                "basis": "Synthetic",
                "acknowledged_impact": True,
                "impact_token": token,
            }
        ),
        content_type="application/json",
        **other_headers,
    )
    assert response.status_code == 403
    fresh.refresh_from_db()
    assert fresh.is_active


def test_reactivation_preserves_parent_and_program_policy_requirements(setup):
    auth, (c, k, p), _ = setup
    retire(auth, c, cascade=True)
    with pytest.raises(cs.CatalogError) as error:
        cs.set_program_active(**auth, target_id=p.pk, expected_resource_version=2, is_active=True)
    assert error.value.code == "catalog_inactive_parent"
    cs.set_campus_active(**auth, target_id=c.pk, expected_resource_version=2, is_active=True)
    cs.set_college_active(**auth, target_id=k.pk, expected_resource_version=2, is_active=True)
    cs.set_program_active(**auth, target_id=p.pk, expected_resource_version=2, is_active=True)
    for row in (c, k, p):
        row.refresh_from_db()
        assert row.is_active and row.is_retired is False and row.resource_version == 3


@pytest.mark.parametrize("head", [False, True])
def test_retired_college_keeps_bounded_coverage_work_and_independent_authority(setup, head):
    auth, (_, college, _), _ = setup
    owner, _ = manager("COUNSELOR", grant=False)
    actor, _ = manager("COUNSELOR", grant=False)
    other, _ = manager("COUNSELOR", grant=False)
    authorizer, _ = manager("COUNSELOR", grant=False)
    UserDesignation.objects.create(
        user=authorizer, designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR")
    )
    if head:
        UserDesignation.objects.create(
            user=actor, designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR")
        )
    now = timezone.now()

    def arrangement(label, *, receiver=None, preparer=None, state="AUTHORIZED", **changes):
        person = student()
        StudentAcademicProfile.objects.create(student=person, current_college=college)
        case = CounselingCase.objects.create(
            reference_code=f"CAT-CASE-{label}",
            student=person,
            primary_counselor=owner,
            opened_by=owner,
            origin="INTAKE",
        )
        values = dict(
            reference_code=f"CAT-COVER-{label}",
            case=case,
            primary_counselor=owner,
            receiving_counselor=receiver or actor,
            prepared_by=preparer or owner,
            communication_recorded_by=owner,
            reason="TEMPORARY_SUPPORT",
            starts_at=now - timedelta(minutes=1),
            expires_at=now + timedelta(days=2),
            submitted_at=now - timedelta(minutes=1),
            state=state,
            authorized_by=authorizer if state == "AUTHORIZED" else None,
            authorized_at=now if state == "AUTHORIZED" else None,
            authorized_version=1 if state == "AUTHORIZED" else None,
            authorization_route="INDEPENDENT_HEAD" if state == "AUTHORIZED" else "",
            review_expires_at=now + timedelta(days=1) if state == "AUTHORIZED" else None,
        )
        values.update(changes)
        return CounselingCaseCoverage.objects.create(**values)

    incoming = arrangement("incoming")
    independent = arrangement("independent", receiver=other, state="PREPARED")
    arrangement("foreign", receiver=other)
    arrangement("self-prepared", receiver=other, preparer=actor, state="PREPARED")
    arrangement("self-receiving", state="PREPARED")
    arrangement("expired", review_expires_at=now - timedelta(seconds=1))
    arrangement("stale-authorization", authorized_version=2)
    obsolete = arrangement("obsolete")
    CounselingCase.objects.filter(pk=obsolete.case_id).update(primary_counselor=other)
    closed = arrangement("closed")
    CounselingCase.objects.filter(pk=closed.case_id).update(status="CLOSED")
    expected = {incoming.pk} | ({independent.pk} if head else set())

    for retired in (False, True):
        if retired:
            retire(auth, college, cascade=True)
        # A small operational projection must finish without the detail selector's role joins.
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '5s'")
        with CaptureQueriesContext(connection) as queries:
            work = pending_coverage_work(actor=actor, limit=21, now=now)
        assert {item.source_id for item in work} == expected
        assert next(item for item in work if item.source_id == incoming.pk).kind.value == (
            "CASE_COVERAGE_ACCEPTANCE"
        )
        if head:
            assert next(item for item in work if item.source_id == independent.pk).kind.value == (
                "CASE_COVERAGE_AUTHORIZATION"
            )
        projection = [
            query["sql"]
            for query in queries
            if f'FROM "{CounselingCaseCoverage._meta.db_table}"' in query["sql"]
            and '"review_expires_at" ASC' in query["sql"]
        ]
        assert len(projection) == 1
        assert 'JOIN "accounts_role"' not in projection[0]
