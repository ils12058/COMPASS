from __future__ import annotations

import json
from datetime import timedelta
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from django.core.management import call_command
from django.test import Client
from django.utils import timezone

from compass.accounts.bootstrap import sync_identity_policy
from compass.accounts.models import (
    Capability,
    Designation,
    Role,
    RoleCapability,
    User,
    UserCapabilityOverride,
    UserDesignation,
)
from compass.accounts.policy import GOA_FORBIDDEN_CAPABILITIES, ROLE_CAPABILITY_GRANTS
from compass.accounts.services import effective_capabilities, set_user_capability_override
from compass.audit.context import AuditContext
from compass.authentication.sessions import create_auth_session
from compass.call_slips.models import CallSlip, CallSlipApprovalStatus, CallSlipLifecycleState
from compass.counseling import (
    case_coverage_services as coverage_services,
)
from compass.counseling import (
    case_handoff_services as handoff_services,
)
from compass.counseling import (
    case_transfer_services as transfer_services,
)
from compass.counseling import (
    continuity_services as legacy_continuity_services,
)
from compass.counseling.case_coverage_models import CounselingCaseCoverage
from compass.counseling.case_transfer_models import CounselingCaseTransfer
from compass.counseling.continuity_models import (
    CounselorCaseContinuityGrant,
    CounselorCaseContinuityScope,
)
from compass.counseling.continuity_sources import SelectedSource, resolve_source
from compass.counseling.models import CounselingEncounter
from compass.guidance_followups import services as followup_services
from compass.guidance_followups.models import FollowUpCategory, FollowUpVisibility
from compass.institutional_forms.models import FormRevision
from compass.notifications.delivery import render_notification_email
from compass.notifications.email_presentation import resolve_notification_email_presentation
from compass.notifications.models import Notification
from compass.notifications.policy import NotificationEvent
from compass.organization.counselor_about import STAFF_CAPABILITIES
from compass.organization.models import Campus, College, CounselorResponsibility, StaffSupervision
from compass.organization.services import set_staff_supervisor
from compass.student_academics.models import StudentAcademicProfile
from tests.test_counseling import create_counseling_service
from tests.test_counseling_cases import intake


def sync_policy() -> None:
    call_command("sync_identity_policy", verbosity=0)


def make_user(email: str, role: str, *, first_name: str = "Test", last_name: str = "User") -> User:
    return User.objects.create_user(
        email=email,
        institutional_id=f"UCN-{uuid4().hex[:10].upper()}",
        password="a-test-password",
        role=Role.objects.get(code=role),
        first_name=first_name,
        last_name=last_name,
    )


def auth_client(user: User) -> Client:
    now = timezone.now()
    issued = create_auth_session(user, now=now, mfa_verified_at=now)
    client = Client()
    client.cookies["compass_session"] = issued.token
    return client


def csrf(client: Client) -> dict[str, str]:
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    return {"HTTP_X_CSRFTOKEN": response.json()["csrf_token"]}


def ensure_call_slip_form() -> FormRevision:
    call_command("sync_institutional_forms", verbosity=0)
    return FormRevision.objects.get(family__key="call_slip", status="ACTIVE")


@pytest.mark.django_db
def test_goa_continuity_removed_from_policy_and_overrides_blocked_and_sync_prunes():
    sync_policy()
    assert "counseling.continuity.view" not in ROLE_CAPABILITY_GRANTS["GUIDANCE_OFFICE_ASSISTANT"]
    assert (
        "counseling.continuity.request" not in ROLE_CAPABILITY_GRANTS["GUIDANCE_OFFICE_ASSISTANT"]
    )
    assert "counseling.continuity.view" in ROLE_CAPABILITY_GRANTS["COUNSELOR"]
    assert "counseling.continuity.request" in ROLE_CAPABILITY_GRANTS["COUNSELOR"]
    assert "counseling.continuity.view" not in STAFF_CAPABILITIES
    assert "counseling.continuity.request" not in STAFF_CAPABILITIES

    goa_role = Role.objects.get(code="GUIDANCE_OFFICE_ASSISTANT")
    # Simulate a pre-change database row where GOA still had the role capability grant.
    RoleCapability.objects.get_or_create(
        role=goa_role,
        capability=Capability.objects.get(code="counseling.continuity.view"),
    )
    result = sync_identity_policy()
    assert result.role_grants_removed == 1
    assert not RoleCapability.objects.filter(
        role=goa_role,
        capability__code__in=GOA_FORBIDDEN_CAPABILITIES,
    ).exists()

    goa = make_user("goa-policy@example.edu", "GUIDANCE_OFFICE_ASSISTANT")
    admin = make_user("admin-policy@example.edu", "IT_ADMIN")
    assert GOA_FORBIDDEN_CAPABILITIES.isdisjoint(effective_capabilities(goa))

    for cap_code in sorted(GOA_FORBIDDEN_CAPABILITIES):
        with pytest.raises(ValueError, match="Guidance Office Assistant Role"):
            set_user_capability_override(
                user=goa,
                capability=cap_code,
                effect=UserCapabilityOverride.Effect.GRANT,
                reason="Attempted continuity override",
                created_by=admin,
            )

    admin_client = auth_client(admin)
    api_attempt = admin_client.put(
        f"/api/v1/accounts/{goa.pk}/capability-overrides/counseling.continuity.view",
        data=json.dumps({"effect": "GRANT", "reason": "Attempted override via API"}),
        content_type="application/json",
        **csrf(admin_client),
    )
    assert api_attempt.status_code == 422

    # Even a raw DB override row cannot grant continuity capabilities to a GOA.
    UserCapabilityOverride.objects.create(
        user=goa,
        capability=Capability.objects.get(code="counseling.continuity.view"),
        effect=UserCapabilityOverride.Effect.GRANT,
        reason="Raw DB row",
        created_by=admin,
    )
    assert "counseling.continuity.view" not in effective_capabilities(goa)


@pytest.mark.django_db
def test_goa_denied_on_every_continuity_endpoint_and_pending_goa_prepared_requests_still_decided(
    settings,
):
    settings.GUIDANCE_FOLLOWUP_ENCRYPTION_KEYS = (Fernet.generate_key().decode(),)
    settings.COUNSELOR_HANDOFF_SUMMARY_ENCRYPTION_KEYS = (Fernet.generate_key().decode(),)
    sync_policy()

    campus = Campus.objects.create(code="MAIN", name="Main Campus", is_active=True)
    college = College.objects.create(
        campus=campus, code="CCMS", name="CCMS College", is_active=True
    )
    counselor_a = make_user(
        "cont-a@example.edu", "COUNSELOR", first_name="Alice", last_name="Counselor"
    )
    service = create_counseling_service(counselor_a)
    counselor_b = make_user(
        "cont-b@example.edu", "COUNSELOR", first_name="Bob", last_name="Counselor"
    )
    head = make_user("cont-head@example.edu", "COUNSELOR", first_name="Head", last_name="Counselor")
    UserDesignation.objects.create(
        user=head,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )
    goa = make_user(
        "cont-goa@example.edu",
        "GUIDANCE_OFFICE_ASSISTANT",
        first_name="Gina",
        last_name="Assistant",
    )
    student = make_user(
        "cont-student@example.edu", "STUDENT", first_name="Sam", last_name="Student"
    )
    StudentAcademicProfile.objects.create(student=student, current_college=college)
    CounselorResponsibility.objects.create(college=college, counselor=counselor_a)
    StaffSupervision.objects.create(staff=goa, supervisor=counselor_a)

    case = intake(counselor_a, student)
    now = timezone.now()

    # Historical pending GOA-prepared coverage request (prepared before this change).
    pending_coverage = CounselingCaseCoverage.objects.create(
        case=case,
        primary_counselor=counselor_a,
        receiving_counselor=counselor_b,
        prepared_by=goa,
        state="PREPARED",
        reason="TEMPORARY_SUPPORT",
        office_preparation_reason="OWNER_UNAVAILABLE",
        starts_at=now - timedelta(minutes=1),
        expires_at=now + timedelta(days=3),
        student_communication="NO",
        communication_recorded_by=goa,
        submitted_at=now,
        independent_authorization=True,
        authorization_route="INDEPENDENT_HEAD",
    )

    # Historical pending GOA-prepared transfer request.
    pending_transfer = CounselingCaseTransfer.objects.create(
        case=case,
        outgoing_counselor=counselor_a,
        receiving_counselor=counselor_b,
        prepared_by=goa,
        state="PREPARED",
        reason="UNEXPECTED_ABSENCE",
        office_preparation_reason="OWNER_UNAVAILABLE",
        student_communication="NO",
        communication_recorded_by=goa,
        handoff_required_at=now,
        independent_authorization=True,
        authorization_route="INDEPENDENT_HEAD",
    )
    handoff_services.operate(
        actor=head,
        transfer_id=pending_transfer.pk,
        operation="exception",
        expected_transfer_version=pending_transfer.version,
        exception_reason="OWNER_UNAVAILABLE",
    )
    pending_transfer.refresh_from_db()
    pending_transfer.submitted_at = now
    pending_transfer.save(update_fields=["submitted_at"])

    # Historical pending GOA-prepared legacy continuity grant.
    from django.db import transaction

    encounter = CounselingEncounter.objects.create(
        student=student,
        counselor=counselor_a,
        service=service,
        entry_mode="WALK_IN",
        delivery_mode="IN_PERSON",
        started_at=now - timedelta(hours=2),
        ended_at=now - timedelta(hours=1),
    )
    placement = StudentAcademicProfile.objects.get(student=student)
    marker = f"{placement.current_college_id}:{placement.updated_at.isoformat()}"
    with transaction.atomic():
        revision = resolve_source(
            selection=SelectedSource("ENCOUNTER", encounter.pk, "ENCOUNTER_METADATA_V1"),
            student_id=student.pk,
            requester=counselor_a,
            original_counselor_id=counselor_a.pk,
        )
    pending_grant = CounselorCaseContinuityGrant(
        student=student,
        original_counselor=counselor_a,
        receiving_counselor=counselor_b,
        coverage_kind="TEMPORARY_COVERAGE",
        reason_category="PLANNED_ABSENCE",
        requested_by=goa,
        requested_at=now,
        starts_at=now - timedelta(minutes=1),
        expires_at=now + timedelta(hours=2),
        student_placement_marker=marker,
        request_id=uuid4(),
    )
    scope_row = CounselorCaseContinuityScope(
        grant=pending_grant,
        resource_kind="ENCOUNTER",
        source_id=encounter.pk,
        projection="ENCOUNTER_METADATA_V1",
        source_revision=revision,
    )
    pending_grant.snapshot_digest = legacy_continuity_services._digest(pending_grant, [scope_row])
    pending_grant.save(force_insert=True)
    scope_row.save(force_insert=True)

    # 1. GOA is denied on every continuity endpoint, including the historical records they prepared.
    goa_client = auth_client(goa)
    goa_headers = csrf(goa_client)
    for method, path, payload in (
        ("get", "/api/v1/counseling/continuity-grants", None),
        ("get", f"/api/v1/counseling/continuity-grants/{pending_grant.pk}", None),
        (
            "post",
            f"/api/v1/counseling/continuity-grants/{pending_grant.pk}/cancel",
            {"expected_version": pending_grant.version},
        ),
        ("get", "/api/v1/counseling/continuity-grants/workflow/configuration", None),
        (
            "get",
            f"/api/v1/counseling/continuity-grants/workflow/selection?student_id={student.pk}&original_counselor_id={counselor_a.pk}",
            None,
        ),
        ("get", "/api/v1/counseling/continuity/office-cases", None),
        ("get", f"/api/v1/counseling/continuity/cases/{case.pk}/coverage-context", None),
        ("get", f"/api/v1/counseling/continuity/coverages/{pending_coverage.pk}", None),
        (
            "post",
            f"/api/v1/counseling/continuity/coverages/{pending_coverage.pk}/cancel",
            {"expected_version": pending_coverage.version, "reason": "REQUEST_WITHDRAWN"},
        ),
        ("get", f"/api/v1/counseling/continuity/cases/{case.pk}/transfer-context", None),
        ("get", f"/api/v1/counseling/continuity/transfers/{pending_transfer.pk}", None),
        (
            "post",
            f"/api/v1/counseling/continuity/transfers/{pending_transfer.pk}/cancel",
            {"expected_version": pending_transfer.version, "reason": "REQUEST_WITHDRAWN"},
        ),
    ):
        if method == "get":
            response = goa_client.get(path)
        else:
            response = goa_client.post(
                path,
                data=json.dumps(payload),
                content_type="application/json",
                HTTP_IDEMPOTENCY_KEY=str(uuid4()),
                **goa_headers,
            )
        assert response.status_code == 403, (
            f"Expected 403 for GOA on {method} {path}, got {response.status_code}"
        )

    # 2. Counselors and Head can still review and decide all pending GOA-prepared requests,
    # and prepared_by + office_preparation_reason remain intact as history.
    approved_grant = legacy_continuity_services.decide_coverage(
        actor=head,
        grant_id=pending_grant.pk,
        decision="APPROVED",
        expected_version=pending_grant.version,
        context=AuditContext.user(head),
    )
    assert approved_grant["effective_status"] == "ACTIVE"
    assert approved_grant["requested_by_id"] == goa.pk

    # End the approved legacy grant so the CW-3 case coverage can be accepted cleanly.
    legacy_continuity_services.decide_coverage(
        actor=head,
        grant_id=approved_grant["id"],
        decision="REVOKED",
        expected_version=approved_grant["version"],
        revocation_reason="COVERAGE_ENDED",
        context=AuditContext.user(head),
    )

    authorized_cov = coverage_services.decide_coverage(
        actor=head,
        coverage_id=pending_coverage.pk,
        expected_version=pending_coverage.version,
        action="authorize",
        context=AuditContext.user(head),
    )
    accepted_cov = coverage_services.decide_coverage(
        actor=counselor_b,
        coverage_id=authorized_cov.pk,
        expected_version=authorized_cov.version,
        action="accept",
        context=AuditContext.user(counselor_b),
    )
    assert accepted_cov.state == "ACCEPTED"
    assert accepted_cov.prepared_by_id == goa.pk
    assert accepted_cov.office_preparation_reason == "OWNER_UNAVAILABLE"

    # End coverage so transfer can be accepted.
    coverage_services.decide_coverage(
        actor=counselor_a,
        coverage_id=accepted_cov.pk,
        expected_version=accepted_cov.version,
        action="revoke",
        reason="REQUEST_WITHDRAWN",
        context=AuditContext.user(counselor_a),
    )

    authorized_tr = transfer_services.decide_transfer(
        actor=head,
        transfer_id=pending_transfer.pk,
        expected_version=pending_transfer.version,
        action="authorize",
        context=AuditContext.user(head),
    )
    accepted_tr = transfer_services.decide_transfer(
        actor=counselor_b,
        transfer_id=authorized_tr.pk,
        expected_version=authorized_tr.version,
        action="accept",
        context=AuditContext.user(counselor_b),
    )
    assert accepted_tr.state == "ACCEPTED"
    assert accepted_tr.prepared_by_id == goa.pk
    assert accepted_tr.office_preparation_reason == "OWNER_UNAVAILABLE"


@pytest.mark.django_db
def test_goa_sees_only_operational_followups_never_counselor_confidential(settings):
    settings.GUIDANCE_FOLLOWUP_ENCRYPTION_KEYS = (Fernet.generate_key().decode(),)
    sync_policy()

    campus = Campus.objects.create(code="FUP-MAIN", name="Main Campus", is_active=True)
    college = College.objects.create(
        campus=campus, code="FUP-CCMS", name="CCMS College", is_active=True
    )
    counselor = make_user("fup-counselor@example.edu", "COUNSELOR")
    create_counseling_service(counselor)
    goa = make_user("fup-goa@example.edu", "GUIDANCE_OFFICE_ASSISTANT")
    student = make_user("fup-student@example.edu", "STUDENT")
    StudentAcademicProfile.objects.create(student=student, current_college=college)
    CounselorResponsibility.objects.create(college=college, counselor=counselor)
    StaffSupervision.objects.create(staff=goa, supervisor=counselor)
    case = intake(counselor, student)

    now = timezone.now()
    operational = followup_services.create_followup(
        actor=counselor,
        student_id=student.pk,
        assigned_to_id=goa.pk,
        category=FollowUpCategory.ADMINISTRATIVE,
        visibility=FollowUpVisibility.OPERATIONAL,
        source_kind=None,
        source_id=None,
        due_at=now + timedelta(days=2),
        description="Operational follow-up visible to GOA",
        idempotency_key="fup-operational-key-01",
        request_fingerprint="a" * 64,
        context=AuditContext.user(counselor),
    )
    confidential = followup_services.create_followup(
        actor=counselor,
        student_id=student.pk,
        assigned_to_id=counselor.pk,
        category=FollowUpCategory.COUNSELING,
        visibility=FollowUpVisibility.COUNSELOR_CONFIDENTIAL,
        source_kind=None,
        source_id=None,
        case_id=case.pk,
        due_at=now + timedelta(days=2),
        description="Confidential counselor follow-up hidden from GOA",
        idempotency_key="fup-confidential-key-01",
        request_fingerprint="b" * 64,
        context=AuditContext.user(counselor),
    )

    goa_client = auth_client(goa)
    listed = goa_client.get("/api/v1/guidance-followups")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["items"]] == [str(operational.pk)]

    assert goa_client.get(f"/api/v1/guidance-followups/{operational.pk}").status_code == 200
    assert goa_client.get(f"/api/v1/guidance-followups/{confidential.pk}").status_code == 404

    forbidden_create = goa_client.post(
        "/api/v1/guidance-followups",
        data=json.dumps(
            {
                "student_id": str(student.pk),
                "assigned_to_id": str(counselor.pk),
                "category": "COUNSELING",
                "visibility": "COUNSELOR_CONFIDENTIAL",
                "case_id": str(case.pk),
                "due_at": (now + timedelta(days=3)).isoformat(),
                "description": "GOA must not create confidential follow-ups",
            }
        ),
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY=str(uuid4()),
        **csrf(goa_client),
    )
    assert forbidden_create.status_code in {403, 404}


@pytest.mark.django_db
def test_goa_call_slip_approval_lifecycle_supervisor_change_and_printout(settings, monkeypatch):
    settings.COMPASS_PORTAL_ORIGIN = "https://portal.example"
    monkeypatch.setattr("compass.notifications.services._safe_kick_email_delivery", lambda _: None)
    monkeypatch.setattr("compass.notifications.services._safe_kick_push_delivery", lambda _: None)
    sync_policy()
    ensure_call_slip_form()

    campus = Campus.objects.create(code="CS-MAIN", name="Main Campus", is_active=True)
    college = College.objects.create(
        campus=campus, code="CS-CCMS", name="CCMS College", is_active=True
    )
    counselor_a = make_user(
        "cs-counselor-a@example.edu", "COUNSELOR", first_name="Clara", last_name="SupervisorA"
    )
    counselor_b = make_user(
        "cs-counselor-b@example.edu", "COUNSELOR", first_name="Daniel", last_name="SupervisorB"
    )
    head = make_user("cs-head@example.edu", "COUNSELOR", first_name="Helena", last_name="Head")
    UserDesignation.objects.create(
        user=head,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )
    goa = make_user(
        "cs-goa@example.edu", "GUIDANCE_OFFICE_ASSISTANT", first_name="Grace", last_name="Assistant"
    )
    student = make_user(
        "cs-student@example.edu", "STUDENT", first_name="Student", last_name="PrivateName"
    )
    StudentAcademicProfile.objects.create(student=student, current_college=college)
    CounselorResponsibility.objects.create(college=college, counselor=counselor_a)
    college_b = College.objects.create(
        campus=campus, code="CS-CEA", name="CEA College", is_active=True
    )
    CounselorResponsibility.objects.create(college=college_b, counselor=counselor_b)

    goa_client = auth_client(goa)
    student_client = auth_client(student)
    counselor_a_client = auth_client(counselor_a)
    counselor_b_client = auth_client(counselor_b)
    report_at = (timezone.now() + timedelta(days=2)).replace(second=0, microsecond=0)

    # 1. Without an active supervising Counselor, GOA creation is blocked.
    unsupervised = goa_client.post(
        "/api/v1/call-slips",
        data=json.dumps(
            {
                "student_id": str(student.pk),
                "course_year": "BSIT 3A",
                "destination_type": "GUIDANCE_OFFICE",
                "report_at": report_at.isoformat(),
                "notify_student": True,
            }
        ),
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY=str(uuid4()),
        **csrf(goa_client),
    )
    assert unsupervised.status_code == 403

    # 2. Assign counselor_a as supervisor; GOA creates a Call Slip -> waits in PENDING_APPROVAL.
    StaffSupervision.objects.create(staff=goa, supervisor=counselor_a)
    created = goa_client.post(
        "/api/v1/call-slips",
        data=json.dumps(
            {
                "student_id": str(student.pk),
                "course_year": "BSIT 3A",
                "destination_type": "GUIDANCE_OFFICE",
                "report_at": report_at.isoformat(),
                "notify_student": True,
            }
        ),
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY=str(uuid4()),
        **csrf(goa_client),
    )
    assert created.status_code == 201, created.content
    slip_data = created.json()
    slip_id = slip_data["id"]
    assert slip_data["state"] == CallSlipLifecycleState.PENDING_APPROVAL
    assert (
        CallSlip.objects.get(pk=slip_id).approval_status == CallSlipApprovalStatus.PENDING_APPROVAL
    )
    assert slip_data["issued_by"]["id"] == str(counselor_a.pk)
    assert slip_data["recorded_by"]["id"] == str(goa.pk)

    # 3. Student does not see it anywhere, and no student notice was sent.
    assert student_client.get("/api/v1/call-slips/me").json()["items"] == []
    assert student_client.get(f"/api/v1/call-slips/me/{slip_id}").status_code == 404
    assert student_client.get(f"/api/v1/call-slips/me/{slip_id}/pdf").status_code == 404
    assert student_client.get("/api/v1/overview").json()["student"]["active_call_slip_count"] == 0
    assert student_client.get("/api/v1/student-actions").json()["items"] == []
    assert student_client.get("/api/v1/me/activity").json()["items"] == []
    assert not Notification.objects.filter(
        recipient=student,
        event_code=NotificationEvent.CALL_SLIP_ISSUED,
    ).exists()
    # Staff PDF printout is blocked while waiting for approval.
    assert goa_client.get(f"/api/v1/call-slips/{slip_id}/pdf").status_code == 503

    # 4. Supervising Counselor sees it in work queue, with in-app notice and content-free email.
    work_a = counselor_a_client.get("/api/v1/work").json()["items"]
    assert any(
        item["kind"] == "CALL_SLIP_APPROVAL" and item["source_id"] == slip_id for item in work_a
    )
    approval_notice = Notification.objects.get(
        recipient=counselor_a,
        event_code=NotificationEvent.CALL_SLIP_APPROVAL_REQUESTED,
        target_id=slip_id,
    )
    plan = resolve_notification_email_presentation(approval_notice)
    rendered = render_notification_email(approval_notice.event_code, presentation=plan)
    assert "A Call Slip is waiting for your approval" in rendered.text_body
    assert f"https://portal.example/portal/call-slips/{slip_id}" in rendered.text_body
    assert "PrivateName" not in rendered.text_body and "PrivateName" not in rendered.html_body

    # 5. Supervisor changes from counselor_a to counselor_b while request is waiting.
    set_staff_supervisor(
        staff_id=goa.pk,
        supervisor_id=counselor_b.pk,
        context=AuditContext.user(head),
    )
    assert not any(
        item["kind"] == "CALL_SLIP_APPROVAL" and item["source_id"] == slip_id
        for item in counselor_a_client.get("/api/v1/work").json()["items"]
    )
    assert any(
        item["kind"] == "CALL_SLIP_APPROVAL" and item["source_id"] == slip_id
        for item in counselor_b_client.get("/api/v1/work").json()["items"]
    )
    old_supervisor_attempt = counselor_a_client.post(
        f"/api/v1/call-slips/{slip_id}/approve",
        HTTP_IDEMPOTENCY_KEY=str(uuid4()),
        **csrf(counselor_a_client),
    )
    assert old_supervisor_attempt.status_code == 403

    # 6. New supervising Counselor returns the Call Slip with a note -> GOA edits and resubmits.
    returned = counselor_b_client.post(
        f"/api/v1/call-slips/{slip_id}/return",
        data=json.dumps({"note": "Please move report time to the afternoon."}),
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY=str(uuid4()),
        **csrf(counselor_b_client),
    )
    assert returned.status_code == 200, returned.content
    assert returned.json()["state"] == CallSlipLifecycleState.RETURNED
    assert returned.json()["return_note"] == "Please move report time to the afternoon."
    assert returned.json()["returned_by"]["id"] == str(counselor_b.pk)
    assert Notification.objects.filter(
        recipient=goa,
        event_code=NotificationEvent.CALL_SLIP_RETURNED,
        target_id=slip_id,
    ).exists()

    updated_report_at = report_at + timedelta(hours=3)
    resubmitted = goa_client.post(
        f"/api/v1/call-slips/{slip_id}/resubmit",
        data=json.dumps(
            {
                "course_year": "BSIT 3B",
                "destination_type": "GUIDANCE_OFFICE",
                "report_at": updated_report_at.isoformat(),
                "notify_student": True,
            }
        ),
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY=str(uuid4()),
        **csrf(goa_client),
    )
    assert resubmitted.status_code == 200, resubmitted.content
    assert resubmitted.json()["state"] == CallSlipLifecycleState.PENDING_APPROVAL
    assert resubmitted.json()["course_year_snapshot"] == "BSIT 3B"
    assert resubmitted.json()["return_note"] == ""

    # 7. Supervising Counselor approves -> becomes ACTIVE, issuer is Counselor.
    approved = counselor_b_client.post(
        f"/api/v1/call-slips/{slip_id}/approve",
        HTTP_IDEMPOTENCY_KEY=str(uuid4()),
        **csrf(counselor_b_client),
    )
    assert approved.status_code == 200, approved.content
    approved_json = approved.json()
    assert approved_json["state"] == CallSlipLifecycleState.ACTIVE
    assert CallSlip.objects.get(pk=slip_id).approval_status == CallSlipApprovalStatus.ISSUED
    assert approved_json["approved_by"]["id"] == str(counselor_b.pk)
    assert approved_json["approved_at"] is not None
    assert approved_json["issued_by"]["id"] == str(counselor_b.pk)
    assert approved_json["issued_by"]["display_name"] == "Daniel SupervisorB"

    assert Notification.objects.filter(
        recipient=student,
        event_code=NotificationEvent.CALL_SLIP_ISSUED,
        target_id=slip_id,
    ).exists()
    assert len(student_client.get("/api/v1/call-slips/me").json()["items"]) == 1
    assert student_client.get(f"/api/v1/call-slips/me/{slip_id}").status_code == 200

    # 8. Printout shows the issuing Counselor.
    slip_record = CallSlip.objects.get(pk=slip_id)
    assert slip_record.issued_by_name_snapshot == "Daniel SupervisorB"
    pdf_response = counselor_b_client.get(f"/api/v1/call-slips/{slip_id}/pdf")
    assert pdf_response.status_code == 200
    assert pdf_response["Content-Type"] == "application/pdf"

    # 9. GOA can withdraw a pending or returned Call Slip.
    student_b = make_user(
        "cs-student-b@example.edu", "STUDENT", first_name="StudentB", last_name="Second"
    )
    StudentAcademicProfile.objects.create(student=student_b, current_college=college_b)
    second = goa_client.post(
        "/api/v1/call-slips",
        data=json.dumps(
            {
                "student_id": str(student_b.pk),
                "course_year": "BSIT 3B",
                "destination_type": "GUIDANCE_OFFICE",
                "report_at": (report_at + timedelta(days=1)).isoformat(),
                "notify_student": True,
            }
        ),
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY=str(uuid4()),
        **csrf(goa_client),
    )
    assert second.status_code == 201
    second_id = second.json()["id"]
    withdrawn = goa_client.post(
        f"/api/v1/call-slips/{second_id}/withdraw",
        data=json.dumps({}),
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY=str(uuid4()),
        **csrf(goa_client),
    )
    assert withdrawn.status_code == 200
    assert withdrawn.json()["state"] == CallSlipLifecycleState.VOIDED

    # 10. Counselor direct issuance is unchanged (ACTIVE immediately).
    direct = counselor_b_client.post(
        "/api/v1/call-slips",
        data=json.dumps(
            {
                "student_id": str(student_b.pk),
                "course_year": "BSIT 3B",
                "destination_type": "GUIDANCE_OFFICE",
                "report_at": (report_at + timedelta(days=3)).isoformat(),
                "notify_student": True,
            }
        ),
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY=str(uuid4()),
        **csrf(counselor_b_client),
    )
    assert direct.status_code == 201
    assert direct.json()["state"] == CallSlipLifecycleState.ACTIVE
    assert CallSlip.objects.get(pk=direct.json()["id"]).approval_status is None


@pytest.mark.django_db
def test_goa_announcements_and_resources_approval_lifecycle_and_published_edit_block(monkeypatch):
    monkeypatch.setattr("compass.notifications.services._safe_kick_email_delivery", lambda _: None)
    monkeypatch.setattr("compass.notifications.services._safe_kick_push_delivery", lambda _: None)
    sync_policy()

    supervisor = make_user(
        "content-supervisor@example.edu", "COUNSELOR", first_name="Sup", last_name="Counselor"
    )
    goa = make_user(
        "content-goa@example.edu",
        "GUIDANCE_OFFICE_ASSISTANT",
        first_name="Office",
        last_name="Assistant",
    )
    StaffSupervision.objects.create(staff=goa, supervisor=supervisor)

    goa_client = auth_client(goa)
    sup_client = auth_client(supervisor)

    # --- Announcements ---
    ann_created = goa_client.post(
        "/api/v1/announcements/management",
        data=json.dumps(
            {
                "title": "Orientation Schedule",
                "body_markdown": "Orientation starts Monday at 8:00 AM.",
                "audience": "STUDENTS",
                "is_pinned": False,
            }
        ),
        content_type="application/json",
        **csrf(goa_client),
    )
    assert ann_created.status_code == 201
    ann_id = ann_created.json()["id"]

    # GOA cannot publish directly.
    assert (
        goa_client.post(
            f"/api/v1/announcements/management/{ann_id}/publish",
            **csrf(goa_client),
        ).status_code
        == 403
    )

    # GOA submits for approval.
    ann_submitted = goa_client.post(
        f"/api/v1/announcements/management/{ann_id}/submit",
        **csrf(goa_client),
    )
    assert ann_submitted.status_code == 200
    assert ann_submitted.json()["status"] == "PENDING_APPROVAL"
    assert ann_submitted.json()["prepared_by"]["id"] == str(goa.pk)
    assert any(
        item["kind"] == "ANNOUNCEMENT_APPROVAL" and item["source_id"] == ann_id
        for item in sup_client.get("/api/v1/work").json()["items"]
    )
    assert Notification.objects.filter(
        recipient=supervisor,
        event_code=NotificationEvent.ANNOUNCEMENT_APPROVAL_REQUESTED,
        target_id=ann_id,
    ).exists()

    # Supervising Counselor returns with a note -> returns to DRAFT.
    ann_returned = sup_client.post(
        f"/api/v1/announcements/management/{ann_id}/return",
        data=json.dumps({"note": "Add the venue room number."}),
        content_type="application/json",
        **csrf(sup_client),
    )
    assert ann_returned.status_code == 200
    assert ann_returned.json()["status"] == "DRAFT"
    assert ann_returned.json()["return_note"] == "Add the venue room number."
    assert ann_returned.json()["returned_by"]["id"] == str(supervisor.pk)
    assert Notification.objects.filter(
        recipient=goa,
        event_code=NotificationEvent.ANNOUNCEMENT_RETURNED,
        target_id=ann_id,
    ).exists()

    # GOA edits and resubmits, then supervising Counselor approves and publishes.
    assert (
        goa_client.patch(
            f"/api/v1/announcements/management/{ann_id}",
            data=json.dumps({"body_markdown": "Orientation starts Monday at 8:00 AM in Room 204."}),
            content_type="application/json",
            **csrf(goa_client),
        ).status_code
        == 200
    )
    assert (
        goa_client.post(
            f"/api/v1/announcements/management/{ann_id}/submit",
            **csrf(goa_client),
        ).status_code
        == 200
    )
    ann_published = sup_client.post(
        f"/api/v1/announcements/management/{ann_id}/publish",
        **csrf(sup_client),
    )
    assert ann_published.status_code == 200
    assert ann_published.json()["status"] == "PUBLISHED"
    assert ann_published.json()["published_by"]["id"] == str(supervisor.pk)
    assert ann_published.json()["prepared_by"]["id"] == str(goa.pk)

    # GOA is blocked from editing or archiving a published Announcement.
    assert (
        goa_client.patch(
            f"/api/v1/announcements/management/{ann_id}",
            data=json.dumps(
                {"title": "Unauthorized GOA edit", "acknowledge_publication_consequences": True}
            ),
            content_type="application/json",
            **csrf(goa_client),
        ).status_code
        == 403
    )
    assert (
        goa_client.post(
            f"/api/v1/announcements/management/{ann_id}/archive",
            **csrf(goa_client),
        ).status_code
        == 403
    )

    # --- Resources ---
    res_created = goa_client.post(
        "/api/v1/resources/management",
        data=json.dumps(
            {
                "title": "Study Habits Guide",
                "body_markdown": "Practical tips for time management.",
                "category": "GENERAL",
                "kind": "ARTICLE",
                "audience": "STUDENTS",
                "display_order": 1,
            }
        ),
        content_type="application/json",
        **csrf(goa_client),
    )
    assert res_created.status_code == 201
    res_id = res_created.json()["id"]

    assert (
        goa_client.post(
            f"/api/v1/resources/management/{res_id}/publish",
            **csrf(goa_client),
        ).status_code
        == 403
    )
    res_submitted = goa_client.post(
        f"/api/v1/resources/management/{res_id}/submit",
        **csrf(goa_client),
    )
    assert res_submitted.status_code == 200
    assert res_submitted.json()["status"] == "PENDING_APPROVAL"
    assert any(
        item["kind"] == "RESOURCE_APPROVAL" and item["source_id"] == res_id
        for item in sup_client.get("/api/v1/work").json()["items"]
    )

    res_returned = sup_client.post(
        f"/api/v1/resources/management/{res_id}/return",
        data=json.dumps({"note": "Expand section 2."}),
        content_type="application/json",
        **csrf(sup_client),
    )
    assert res_returned.status_code == 200
    assert res_returned.json()["status"] == "DRAFT"
    assert res_returned.json()["return_note"] == "Expand section 2."

    assert (
        goa_client.post(
            f"/api/v1/resources/management/{res_id}/submit",
            **csrf(goa_client),
        ).status_code
        == 200
    )
    res_published = sup_client.post(
        f"/api/v1/resources/management/{res_id}/publish",
        **csrf(sup_client),
    )
    assert res_published.status_code == 200
    assert res_published.json()["status"] == "PUBLISHED"
    assert res_published.json()["published_by"]["id"] == str(supervisor.pk)
    assert res_published.json()["prepared_by"]["id"] == str(goa.pk)

    assert (
        goa_client.patch(
            f"/api/v1/resources/management/{res_id}",
            data=json.dumps(
                {"title": "Unauthorized GOA edit", "acknowledge_publication_consequences": True}
            ),
            content_type="application/json",
            **csrf(goa_client),
        ).status_code
        == 403
    )


@pytest.mark.django_db
def test_supervising_counselor_still_sees_goa_operational_activity():
    sync_policy()
    supervisor = make_user("sup-act@example.edu", "COUNSELOR")
    goa = make_user("goa-act@example.edu", "GUIDANCE_OFFICE_ASSISTANT")
    StaffSupervision.objects.create(staff=goa, supervisor=supervisor)

    goa_client = auth_client(goa)
    created = goa_client.post(
        "/api/v1/announcements/management",
        data=json.dumps(
            {
                "title": "Draft by GOA",
                "body_markdown": "Body text",
                "audience": "STUDENTS",
                "is_pinned": False,
            }
        ),
        content_type="application/json",
        **csrf(goa_client),
    )
    assert created.status_code == 201

    sup_client = auth_client(supervisor)
    staff_list = sup_client.get("/api/v1/me/supervised-staff")
    assert staff_list.status_code == 200
    assert [row["id"] for row in staff_list.json()["items"]] == [str(goa.pk)]

    activity = sup_client.get(f"/api/v1/me/supervised-staff-activity?staff_id={goa.pk}")
    assert activity.status_code == 200
    assert any(item["type"] == "announcement.created" for item in activity.json()["items"])
