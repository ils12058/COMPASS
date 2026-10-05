from __future__ import annotations

import json
from datetime import timedelta
from uuid import uuid4

import pytest
from django.utils import timezone

from compass.accounts.models import UserCapabilityOverride
from compass.accounts.services import effective_capabilities, set_user_capability_override
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.good_moral.services import (
    GoodMoralConflict,
    GoodMoralNotPermitted,
    GoodMoralNotReady,
    GoodMoralPreparationChanged,
    InvalidGoodMoralInput,
    cancel_request,
    get_request,
    issue_request,
    list_requests,
    prepare_request,
    update_request,
)
from tests.test_good_moral import (
    auth_client,
    csrf,
    make_current_request,
    make_graduate_request,
    make_user,
    sync_policy,
)


def setup_request(*, graduate=False):
    sync_policy()
    staff = make_user("preparer@example.edu", role="GUIDANCE_SERVICES_STAFF")
    counselor = make_user("issuer@example.edu", role="COUNSELOR")
    student = make_user("applicant@example.edu", lifecycle="GRADUATED" if graduate else "CURRENT")
    item = make_graduate_request(student) if graduate else make_current_request(student)[0]
    return staff, counselor, student, item


def post(client, item, action, payload):
    return client.post(
        f"/api/v1/good-moral/requests/{item.pk}/{action}",
        data=json.dumps(payload),
        content_type="application/json",
        **csrf(client),
    )


@pytest.mark.django_db
def test_gss_baseline_is_clerical_and_reference_only():
    staff, counselor, _, _ = setup_request()
    codes = effective_capabilities(staff)
    assert {
        "academic_years.view",
        "institutional_forms.view",
        "good_moral.view",
        "good_moral.prepare",
    } <= codes
    assert not any(
        code.startswith(
            (
                "counseling.",
                "routine_interviews.",
                "shared_summaries.",
                "inventory.",
                "ecounseling.",
                "exit_interviews.",
            )
        )
        for code in codes
    )
    assert {
        "good_moral.issue",
        "reports.view",
        "student_support.view",
        "accounts.manage",
        "organization.manage",
        "services.manage",
        "availability.manage",
        "academic_years.manage",
    }.isdisjoint(codes)
    assert {"good_moral.prepare", "good_moral.issue"} <= effective_capabilities(counselor)


@pytest.mark.django_db
@pytest.mark.parametrize("graduate", [False, True])
def test_staff_prepares_counselor_issues_and_provenance_remains_real(graduate, monkeypatch):
    staff, counselor, _, item = setup_request(graduate=graduate)
    assert list_requests(actor=staff).items[0].pk == item.pk
    assert get_request(actor=staff, request_id=item.pk).pk == item.pk
    with pytest.raises(GoodMoralNotReady):
        issue_request(actor=counselor, request_id=item.pk, context=AuditContext.user(counselor))
    client = auth_client(staff)
    assert client.get(f"/api/v1/good-moral/requests/{item.pk}/pdf").status_code == 409
    prepared = post(
        client, item, "prepare", {"expected_resource_version": item.updated_at.isoformat()}
    )
    assert prepared.status_code == 200
    body = prepared.json()
    assert body["status"] == "READY_FOR_ISSUANCE"
    assert body["prepared_by"]["id"] == str(staff.pk)
    assert body["actions"]["can_issue"] is False
    assert body["actions"]["can_correct"] is True
    assert body["actions"]["can_cancel"] is False
    issued = post(
        auth_client(counselor),
        item,
        "issue",
        {"expected_preparation_version": body["actions"]["preparation_version"]},
    )
    assert issued.status_code == 200
    assert issued.json()["issued_by"]["id"] == str(counselor.pk)
    assert issued.json()["prepared_by"]["id"] == str(staff.pk)
    assert issued.json()["actions"]["can_download"] is True
    monkeypatch.setattr("compass.good_moral.api.render_certificate_pdf", lambda _: b"%PDF-test")
    released = client.get(f"/api/v1/good-moral/requests/{item.pk}/pdf")
    assert released.status_code == 200
    assert released["Content-Type"] == "application/pdf"
    events = AuditEvent.objects.filter(action="good_moral.prepared", target_id=item.pk)
    assert events.count() == 1
    assert "applicant" not in json.dumps(events.get().metadata)


@pytest.mark.django_db
def test_safe_corrections_preserve_sources_and_ready_requires_reconfirmation():
    staff, counselor, student, item = setup_request()
    inventory_id, year_id, applicant = (
        item.inventory_id,
        item.academic_year_id,
        item.applicant_name_snapshot,
    )
    first = prepare_request(actor=staff, request_id=item.pk, context=AuditContext.user(staff))
    assert (
        update_request(
            actor=staff,
            request_id=item.pk,
            changes={"course_snapshot": item.course_snapshot},
            context=AuditContext.user(staff),
        ).status
        == "READY_FOR_ISSUANCE"
    )
    changed = update_request(
        actor=staff,
        request_id=item.pk,
        changes={
            "year_level_snapshot": "Third",
            "course_snapshot": "BS Computing",
            "official_receipt_number": "OR-123",
        },
        context=AuditContext.user(staff),
    )
    assert changed.status == "REQUESTED"
    assert changed.prepared_at is None and changed.prepared_by_id is None
    assert (
        changed.inventory_id,
        changed.academic_year_id,
        changed.applicant_name_snapshot,
        changed.student_id,
    ) == (inventory_id, year_id, applicant, student.pk)
    with pytest.raises(GoodMoralNotReady):
        issue_request(
            actor=counselor,
            request_id=item.pk,
            context=AuditContext.user(counselor),
            expected_preparation_version=first.prepared_at.isoformat(),
        )
    second = prepare_request(
        actor=counselor, request_id=item.pk, context=AuditContext.user(counselor)
    )
    with pytest.raises(GoodMoralPreparationChanged):
        issue_request(
            actor=counselor,
            request_id=item.pk,
            context=AuditContext.user(counselor),
            expected_preparation_version=first.prepared_at.isoformat(),
        )
    assert second.prepared_by_id == counselor.pk
    assert (
        AuditEvent.objects.filter(
            action="good_moral.returned_to_preparation", target_id=item.pk
        ).count()
        == 1
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "field",
    [
        "student_id",
        "variant",
        "inventory_id",
        "academic_year_id",
        "applicant_name_snapshot",
        "college_snapshot",
    ],
)
def test_gss_cannot_change_protected_fields(field):
    staff, _, _, item = setup_request()
    before = getattr(item, field)
    with pytest.raises(InvalidGoodMoralInput):
        update_request(
            actor=staff,
            request_id=item.pk,
            changes={field: "changed"},
            context=AuditContext.user(staff),
        )
    item.refresh_from_db()
    assert getattr(item, field) == before


@pytest.mark.django_db
def test_gss_cannot_rewrite_graduation_facts_but_counselor_can_correct_them():
    staff, counselor, _, item = setup_request(graduate=True)
    with pytest.raises(InvalidGoodMoralInput):
        update_request(
            actor=staff,
            request_id=item.pk,
            changes={"degree_snapshot": "Changed"},
            context=AuditContext.user(staff),
        )
    assert (
        update_request(
            actor=counselor,
            request_id=item.pk,
            changes={"degree_snapshot": "Corrected degree"},
            context=AuditContext.user(counselor),
        ).degree_snapshot
        == "Corrected degree"
    )


@pytest.mark.django_db
def test_it_admin_revoke_and_expiry_control_preparation_without_removing_view():
    staff, _, _, item = setup_request()
    admin = make_user("it@example.edu", role="IT_ADMIN")
    expiry = timezone.now() + timedelta(minutes=10)
    override = set_user_capability_override(
        user=staff,
        capability="good_moral.prepare",
        effect="REVOKE",
        reason="Temporary restriction",
        expires_at=expiry,
        created_by=admin,
    )
    assert override.created_by_id == admin.pk
    assert staff.has_capability("good_moral.view") and not staff.has_capability(
        "good_moral.prepare"
    )
    with pytest.raises(GoodMoralNotPermitted):
        prepare_request(actor=staff, request_id=item.pk, context=AuditContext.user(staff))
    body = auth_client(staff).get(f"/api/v1/good-moral/requests/{item.pk}").json()
    assert body["actions"]["can_prepare"] is False
    assert body["actions"]["can_correct"] is False
    assert body["actions"]["correction_fields"] == []
    assert "good_moral.prepare" in effective_capabilities(staff, at=expiry + timedelta(seconds=1))
    override.expires_at = timezone.now() - timedelta(seconds=1)
    override.save(update_fields=["expires_at"])
    assert staff.has_capability("good_moral.prepare")
    set_user_capability_override(
        user=staff,
        capability="good_moral.view",
        effect="REVOKE",
        reason="Access removed",
        created_by=admin,
    )
    assert not staff.has_capability("good_moral.prepare")
    assert auth_client(staff).get(f"/api/v1/good-moral/requests/{item.pk}").status_code == 403


@pytest.mark.django_db
def test_issue_override_does_not_qualify_staff_or_admin_as_counselor():
    staff, counselor, _, item = setup_request()
    admin = make_user("override-it@example.edu", role="IT_ADMIN")
    other_admin = make_user("governance-it@example.edu", role="IT_ADMIN")
    ready = prepare_request(actor=staff, request_id=item.pk, context=AuditContext.user(staff))
    set_user_capability_override(
        user=staff,
        capability="good_moral.issue",
        effect=UserCapabilityOverride.Effect.GRANT,
        reason="Accidental issue grant",
        created_by=admin,
    )
    assert staff.has_capability("good_moral.issue")
    with pytest.raises(GoodMoralNotPermitted):
        issue_request(actor=staff, request_id=item.pk, context=AuditContext.user(staff))
    assert (
        post(
            auth_client(staff),
            item,
            "issue",
            {"expected_preparation_version": ready.prepared_at.isoformat()},
        ).status_code
        == 403
    )
    for code in ("good_moral.view", "good_moral.prepare", "good_moral.issue"):
        set_user_capability_override(
            user=admin,
            capability=code,
            effect="GRANT",
            reason="Test role qualification",
            created_by=other_admin,
        )
    with pytest.raises(GoodMoralNotPermitted):
        get_request(actor=admin, request_id=item.pk)


@pytest.mark.django_db
def test_prepare_validates_completeness_and_rejects_stale_review():
    staff, _, _, item = setup_request()
    with pytest.raises(GoodMoralPreparationChanged):
        prepare_request(
            actor=staff,
            request_id=item.pk,
            context=AuditContext.user(staff),
            expected_resource_version=(item.updated_at - timedelta(seconds=1)).isoformat(),
        )
    update_request(
        actor=staff,
        request_id=item.pk,
        changes={"semester_snapshot": ""},
        context=AuditContext.user(staff),
    )
    with pytest.raises(GoodMoralConflict):
        prepare_request(actor=staff, request_id=item.pk, context=AuditContext.user(staff))
    item.refresh_from_db()
    assert item.status == "REQUESTED" and item.prepared_at is None


@pytest.mark.django_db
def test_ready_request_can_be_cancelled_and_terminal_records_remain_immutable():
    staff, counselor, student, item = setup_request()
    prepare_request(actor=staff, request_id=item.pk, context=AuditContext.user(staff))
    cancelled = cancel_request(
        actor=student,
        request_id=item.pk,
        reason="No longer needed",
        self_service=True,
        context=AuditContext.user(student),
    )
    assert cancelled.status == "CANCELLED"
    assert cancelled.prepared_by_id == staff.pk
    with pytest.raises(GoodMoralConflict):
        prepare_request(actor=counselor, request_id=item.pk, context=AuditContext.user(counselor))


@pytest.mark.django_db
def test_gss_keeps_denial_for_exit_interview_answers_and_reopen():
    staff, _, _, _ = setup_request()
    client = auth_client(staff)
    record_id = uuid4()
    assert client.get(f"/api/v1/exit-interviews/{record_id}").status_code == 403
    assert (
        client.post(
            f"/api/v1/exit-interviews/{record_id}/reopen",
            data=json.dumps({"reason": "Test"}),
            content_type="application/json",
            **csrf(client),
        ).status_code
        == 403
    )
