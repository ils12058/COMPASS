"""FUP-3A: canonical Faculty Referral journey on the code-owned provisional path.

These tests use the real default providers. The only monkeypatch is the Redis-backed
confirmation limiter, so no APPROVED policy is substituted for the provisional path.
"""

from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from django.test import Client
from django.utils import timezone

from compass.accounts.bootstrap import sync_identity_policy
from compass.accounts.models import User
from compass.audit.actions import REFERRAL_FACULTY_POLICY_RECORDED
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent, AuditOutcome
from compass.audit.services import record_event
from compass.authentication.sessions import create_auth_session
from compass.guidance_followups import services as followup_services
from compass.guidance_followups.models import GuidanceFollowUp
from compass.notifications.models import EmailDelivery, Notification
from compass.organization.models import (
    Campus,
    College,
    CounselorResponsibility,
    FacultyAffiliation,
    StaffSupervision,
)
from compass.referrals import (
    administration,
    administrative_policy,
    faculty_policy,
    faculty_services,
    provisional_activation as provisional,
    services,
)
from compass.referrals.faculty_policy import FacultyReferralError
from compass.referrals.models import Referral, ReferralAction
from compass.referrals.notification_contract import prepare_candidate_intent
from compass.student_academics.models import StudentAcademicProfile
from tests.faculty_referral_helpers import SyntheticLimiter, person

pytestmark = pytest.mark.django_db

FACULTY_ITEM_KEYS = {
    "id",
    "reference_code",
    "submitted_at",
    "state",
    "student",
    "received_at",
    "closed_at",
}
FOLLOWUP_FIELD_NAMES = {
    "followup",
    "follow_up",
    "followups",
    "follow_ups",
    "assigned_to",
    "assigned_to_id",
    "assigned_to_name",
    "due_at",
    "outcome",
    "activity",
    "events",
    "counseling",
    "counselor",
    "category",
    "visibility",
}


@pytest.fixture
def world(monkeypatch, settings):
    settings.GUIDANCE_FOLLOWUP_ENCRYPTION_KEYS = (Fernet.generate_key().decode(),)
    sync_identity_policy()
    admin = person("fup3a-admin", "IT_ADMIN")
    faculty = person("fup3a-faculty", "FACULTY")
    other_faculty = person("fup3a-other-faculty", "FACULTY")
    student = person("fup3a-student", "STUDENT")
    counselor = person("fup3a-counselor", "COUNSELOR")
    staff = person("fup3a-staff", "GUIDANCE_OFFICE_ASSISTANT")
    campus = Campus.objects.create(code="FUP3A", name="Synthetic FUP3A Campus")
    cas = College.objects.create(campus=campus, code="FUP3A-CAS", name="Synthetic FUP3A CAS")
    ccms = College.objects.create(campus=campus, code="FUP3A-CCMS", name="Synthetic FUP3A CCMS")
    for member in (faculty, other_faculty):
        FacultyAffiliation.objects.create(
            faculty=member, college=cas, assigned_by=admin, basis="Synthetic"
        )
    StudentAcademicProfile.objects.create(student=student, current_college=ccms)
    CounselorResponsibility.objects.create(college=ccms, counselor=counselor)
    StaffSupervision.objects.create(staff=staff, supervisor=counselor)
    limiter = SyntheticLimiter()
    monkeypatch.setattr(faculty_services.RedisRateLimiter, "from_settings", lambda: limiter)
    value = SimpleNamespace(
        admin=admin,
        faculty=faculty,
        other_faculty=other_faculty,
        student=student,
        counselor=counselor,
        staff=staff,
        campus=campus,
        cas=cas,
        ccms=ccms,
        limiter=limiter,
    )
    for name in ("faculty", "other_faculty", "counselor", "staff"):
        setattr(
            value,
            name + "_issued",
            create_auth_session(getattr(value, name), mfa_verified_at=timezone.now()),
        )
    return value


def confirm(world, *, actor=None, issued=None):
    return faculty_services.confirm_student(
        actor=actor or world.faculty,
        actor_session=(issued or world.faculty_issued).session,
        institutional_id=world.student.institutional_id,
        ip_address="127.0.0.1",
    )


def submit(world, confirmation):
    return faculty_services.submit_referral(
        actor=world.faculty,
        actor_session=world.faculty_issued.session,
        confirmation=confirmation,
        course_year_block="Synthetic course/year/block",
        reason="Synthetic confidential journey reason",
        idempotency_key="fup3a-journey-submission",
        context=AuditContext.user(world.faculty),
    )


def transition(world, referral_id, *, close=False, expected_version):
    return administration.transition(
        actor=world.counselor,
        actor_session=world.counselor_issued.session,
        referral_id=referral_id,
        expected_version=expected_version,
        kind="CLOSURE" if close else "ACKNOWLEDGMENT",
        obligations_reviewed=close,
        context=AuditContext.user(world.counselor),
    )


def linked_followup(world, referral_id, key):
    return followup_services.create_followup(
        actor=world.counselor,
        student_id=world.student.pk,
        assigned_to_id=world.staff.pk,
        category="REFERRAL_ACTION",
        due_at=timezone.now() + timedelta(days=3),
        source_kind="REFERRAL",
        source_id=referral_id,
        description=None,
        visibility=None,
        idempotency_key=key,
        request_fingerprint="a" * 64,
        context=AuditContext.user(world.counselor),
    )


def authenticated(issued):
    client = Client()
    client.cookies["compass_session"] = issued.token
    return client


def nested_keys(value):
    if isinstance(value, dict):
        keys = set(value)
        for nested in value.values():
            keys |= nested_keys(nested)
        return keys
    if isinstance(value, list):
        keys = set()
        for item in value:
            keys |= nested_keys(item)
        return keys
    return set()


def assert_faculty_projection(client, referral_id, state):
    availability = client.get("/api/v1/faculty/referrals/availability")
    assert availability.status_code == 200
    assert set(availability.json()) == {
        "can_confirm_student",
        "can_submit_referral",
        "can_view_submissions",
        "valid_until",
    }
    listing = client.get("/api/v1/faculty/referrals")
    assert listing.status_code == 200
    page = listing.json()
    assert set(page) == {"items", "page", "page_size", "has_next"}
    assert [item["id"] for item in page["items"]] == [str(referral_id)]
    for item in page["items"]:
        assert set(item) == FACULTY_ITEM_KEYS
        assert set(item["student"]) == {"display_name"}
        assert not nested_keys(item) & FOLLOWUP_FIELD_NAMES
        assert item["state"] == state
    detail = client.get(f"/api/v1/faculty/referrals/{referral_id}")
    assert detail.status_code == 200
    assert set(detail.json()) == FACULTY_ITEM_KEYS
    assert set(detail.json()["student"]) == {"display_name"}
    assert not nested_keys(detail.json()) & FOLLOWUP_FIELD_NAMES
    assert detail.json()["state"] == state


def referral_snapshot(item):
    return {
        "administrative_version": item.administrative_version,
        "received_at": item.received_at,
        "acknowledged_by_id": item.acknowledged_by_id,
        "acknowledgment_policy_digest": item.acknowledgment_policy_digest,
        "acknowledgment_policy_event_id": item.acknowledgment_policy_event_id,
        "administratively_closed_at": item.administratively_closed_at,
        "administratively_closed_by_id": item.administratively_closed_by_id,
        "closure_policy_digest": item.closure_policy_digest,
        "closure_policy_event_id": item.closure_policy_event_id,
        "voided_at": item.voided_at,
        "updated_at": item.updated_at,
    }


def test_canonical_faculty_referral_journey_is_available_by_default(world):
    start_notifications = Notification.objects.count()
    start_deliveries = EmailDelivery.objects.count()

    availability = faculty_services.referral_availability(
        actor=world.faculty, actor_session=world.faculty_issued.session
    )
    assert availability["can_confirm_student"] is True
    assert availability["can_submit_referral"] is True
    assert availability["can_view_submissions"] is True

    confirmation = confirm(world)
    assert set(confirmation) == {"confirmed", "student", "confirmation", "expires_at"}
    assert confirmation["confirmed"] is True
    assert confirmation["student"] == {"display_name": world.student.get_full_name()}
    assert confirmation["confirmation"]
    assert provisional.EVENT_IDS[provisional.STUDENT_CONFIRMATION] == (
        AuditEvent.objects.get(pk=provisional.EVENT_IDS[provisional.STUDENT_CONFIRMATION]).pk
    )

    result, created = submit(world, confirmation["confirmation"])
    assert created is True and result["state"] == "SUBMITTED"
    row = Referral.objects.get(pk=result["id"])
    assert row.submission_channel == "FACULTY_PORTAL"
    assert row.submission_policy_event_id == provisional.EVENT_IDS[provisional.DIGITAL_SUBMISSION]
    submission_event = AuditEvent.objects.get(pk=row.submission_policy_event_id)
    assert submission_event.metadata["decision"] == provisional.PROVISIONAL_DECISION
    assert submission_event.metadata["provisional"] is True
    assert submission_event.metadata["authority"] == provisional.PROVISIONAL_AUTHORITY
    assert submission_event.metadata["policy_kind"] == provisional.DIGITAL_SUBMISSION
    assert submission_event.metadata["policy_digest"] == row.submission_policy_digest
    assert not ReferralAction.objects.exists()
    assert not GuidanceFollowUp.objects.exists()

    faculty = authenticated(world.faculty_issued)
    assert_faculty_projection(faculty, row.pk, "SUBMITTED")

    acknowledged = transition(world, row.pk, expected_version=1)
    row.refresh_from_db()
    assert acknowledged["state"] == "RECEIVED_BY_GCO" and acknowledged["version"] == 2
    assert row.acknowledged_by_id == world.counselor.pk
    assert row.acknowledgment_policy_event_id == provisional.EVENT_IDS[provisional.ACKNOWLEDGMENT]
    acknowledgment_event = AuditEvent.objects.get(pk=row.acknowledgment_policy_event_id)
    assert acknowledgment_event.metadata["decision"] == provisional.PROVISIONAL_DECISION
    assert acknowledgment_event.metadata["contract_evidence_reference"] == (
        provisional.PROVISIONAL_CONTRACT_EVIDENCE_REFERENCE
    )
    assert prepare_candidate_intent(referral_id=row.pk, event="RECEIVED_BY_GCO") is None
    assert_faculty_projection(faculty, row.pk, "RECEIVED_BY_GCO")
    assert Notification.objects.count() == start_notifications == 0
    assert EmailDelivery.objects.count() == start_deliveries == 0

    first = linked_followup(world, row.pk, "fup3a-completed-after-closure")
    second = linked_followup(world, row.pk, "fup3a-open-after-void")
    assert first.visibility == "OPERATIONAL" and first.category == "REFERRAL_ACTION"
    assert first.assigned_to_id == world.staff.pk
    assert followup_services.get_followup(
        actor=world.staff, followup_id=first.pk
    ).pk == first.pk
    staff_list = followup_services.list_followups(actor=world.staff)
    assert {item.pk for item in staff_list.items} == {first.pk, second.pk}
    assert GuidanceFollowUp.objects.count() == 2
    # Only the existing Follow-Up assignment notifications exist: no Referral/FAC-D8 notice.
    assignment_notifications = list(Notification.objects.all())
    assert len(assignment_notifications) == 2
    for notification in assignment_notifications:
        assert notification.recipient_id == world.staff.pk
        assert notification.recipient_id != world.faculty.pk
        assert notification.target_type == "GUIDANCE_FOLLOW_UP"
        assert notification.source_type == "guidance_followup_event"
    assert not EmailDelivery.objects.exists()
    notifications_before_closure = Notification.objects.count()
    assert_faculty_projection(faculty, row.pk, "RECEIVED_BY_GCO")

    closed = transition(world, row.pk, close=True, expected_version=2)
    row.refresh_from_db()
    assert closed["state"] == "ADMINISTRATIVELY_CLOSED" and closed["version"] == 3
    assert row.closure_policy_event_id == provisional.EVENT_IDS[provisional.CLOSURE]
    closure_event = AuditEvent.objects.get(pk=row.closure_policy_event_id)
    assert closure_event.metadata["decision"] == provisional.PROVISIONAL_DECISION
    assert GuidanceFollowUp.objects.get(pk=first.pk).status == "PENDING"
    assert GuidanceFollowUp.objects.get(pk=second.pk).status == "PENDING"
    assert prepare_candidate_intent(referral_id=row.pk, event="ADMINISTRATIVELY_CLOSED") is None
    assert_faculty_projection(faculty, row.pk, "ADMINISTRATIVELY_CLOSED")

    before_completion = referral_snapshot(row)
    referral_audit_before = list(
        AuditEvent.objects.filter(target_id=str(row.pk))
        .order_by("occurred_at", "id")
        .values_list("pk", flat=True)
    )
    completed = followup_services.complete_followup(
        actor=world.staff,
        followup_id=first.pk,
        expected_version=1,
        outcome="Synthetic completed referral action",
        context=AuditContext.user(world.staff),
    )
    assert completed.status == "COMPLETED"
    row.refresh_from_db()
    assert referral_snapshot(row) == before_completion
    assert (
        list(
            AuditEvent.objects.filter(target_id=str(row.pk))
            .order_by("occurred_at", "id")
            .values_list("pk", flat=True)
        )
        == referral_audit_before
    )
    assert GuidanceFollowUp.objects.get(pk=second.pk).status == "PENDING"
    assert_faculty_projection(faculty, row.pk, "ADMINISTRATIVELY_CLOSED")

    second_before = GuidanceFollowUp.objects.get(pk=second.pk)
    second_snapshot = {
        "status": second_before.status,
        "assigned_to_id": second_before.assigned_to_id,
        "source_kind": second_before.source_kind,
        "source_id": second_before.source_id,
        "version": second_before.version,
        "completed_at": second_before.completed_at,
        "cancelled_at": second_before.cancelled_at,
        "updated_at": second_before.updated_at,
    }
    followup_count = GuidanceFollowUp.objects.count()
    services.void_referral(
        actor=world.counselor,
        referral_id=row.pk,
        reason="Synthetic journey correction",
        context=AuditContext.user(world.counselor),
    )
    row.refresh_from_db()
    second_before.refresh_from_db()
    assert row.voided_at is not None
    assert (
        {
            "status": second_before.status,
            "assigned_to_id": second_before.assigned_to_id,
            "source_kind": second_before.source_kind,
            "source_id": second_before.source_id,
            "version": second_before.version,
            "completed_at": second_before.completed_at,
            "cancelled_at": second_before.cancelled_at,
            "updated_at": second_before.updated_at,
        }
        == second_snapshot
    )
    assert GuidanceFollowUp.objects.count() == followup_count
    assert followup_services.get_followup(actor=world.staff, followup_id=second.pk).pk == (
        second.pk
    )
    assert second.pk in {
        item.pk for item in followup_services.list_followups(actor=world.staff).items
    }
    detail = authenticated(world.staff_issued).get(
        f"/api/v1/guidance-followups/{second.pk}"
    )
    assert detail.status_code == 200
    assert detail.json()["source"] is None
    assert detail.json()["source_unavailable"] is True
    assert detail.json()["status"] == "PENDING"
    assert detail.json()["assigned_to_id"] == str(world.staff.pk)
    assert detail.json()["version"] == 1
    assert second_before.source_kind == "REFERRAL" and second_before.source_id == row.pk

    assert faculty.get(f"/api/v1/faculty/referrals/{row.pk}").status_code == 404
    assert faculty.get("/api/v1/faculty/referrals").json()["items"] == []
    assert not ReferralAction.objects.exists()
    assert Notification.objects.count() == notifications_before_closure
    assert not Notification.objects.filter(target_type="REFERRAL").exists()
    assert not Notification.objects.filter(source_type__startswith="referral").exists()
    assert EmailDelivery.objects.count() == start_deliveries == 0


def test_provisional_evidence_is_fixed_idempotent_and_truthful(world):
    now = timezone.now()
    providers = {
        provisional.STUDENT_CONFIRMATION: provisional.provisional_lookup_policy(now),
        provisional.DIGITAL_SUBMISSION: provisional.provisional_submission_policy(now),
        provisional.ACKNOWLEDGMENT: provisional.provisional_acknowledgment_policy(now),
        provisional.CLOSURE: provisional.provisional_closure_policy(now),
        provisional.FACULTY_TRACKING: provisional.provisional_tracking_disclosure_policy(now),
    }
    for _ in range(2):
        provisional.provisional_lookup_policy(now)
        provisional.provisional_submission_policy(now)
        provisional.provisional_acknowledgment_policy(now)
        provisional.provisional_closure_policy(now)
        provisional.provisional_tracking_disclosure_policy(now)

    providers[provisional.STUDENT_CONFIRMATION].validate(now)
    providers[provisional.DIGITAL_SUBMISSION].validate(now)
    for kind in (
        provisional.ACKNOWLEDGMENT,
        provisional.CLOSURE,
        provisional.FACULTY_TRACKING,
    ):
        providers[kind].validate(now, kind)

    assert len({policy.digest for policy in providers.values()}) == 5
    assert AuditEvent.objects.filter(pk__in=provisional.EVENT_IDS.values()).count() == 5
    for kind, policy in providers.items():
        assert policy.digest == provisional.digest_for(kind)
        event = AuditEvent.objects.get(pk=provisional.EVENT_IDS[kind])
        expected = provisional.metadata_for(kind)
        assert event.actor_type == "SYSTEM"
        assert event.outcome == "SUCCESS"
        assert event.action == (
            REFERRAL_FACULTY_POLICY_RECORDED
            if kind in {provisional.STUDENT_CONFIRMATION, provisional.DIGITAL_SUBMISSION}
            else administrative_policy.POLICY_RECORDED
        )
        assert {key: event.metadata.get(key) for key in expected} == expected
        assert event.metadata["decision"] == provisional.PROVISIONAL_DECISION
        assert event.metadata["decision"] != "APPROVED"

    new_campus = Campus.objects.create(code="FUP3A-NEW", name="Synthetic new campus")
    new_college = College.objects.create(
        campus=new_campus, code="FUP3A-NEW", name="Synthetic new college"
    )
    new_faculty = person("fup3a-new-faculty", "FACULTY")
    refreshed = provisional.provisional_lookup_policy(now)
    assert new_college.pk in refreshed.student_college_ids
    assert new_faculty.pk in refreshed.faculty_ids
    assert refreshed.digest == providers[provisional.STUDENT_CONFIRMATION].digest
    assert (
        AuditEvent.objects.filter(
            pk=provisional.EVENT_IDS[provisional.STUDENT_CONFIRMATION]
        ).count()
        == 1
    )


def test_live_scope_removal_denies_affected_provisional_operation(world):
    assert confirm(world, actor=world.other_faculty, issued=world.other_faculty_issued)[
        "confirmed"
    ] is True
    world.other_faculty.is_active = False
    world.other_faculty.save(update_fields=["is_active"])
    with pytest.raises(FacultyReferralError):
        confirm(world, actor=world.other_faculty, issued=world.other_faculty_issued)
    assert world.other_faculty.pk not in provisional.provisional_lookup_policy().faculty_ids

    ticket = confirm(world)["confirmation"]
    result, _ = submit(world, ticket)
    world.ccms.is_active = False
    world.ccms.save(update_fields=["is_active"])
    assert confirm(world)["confirmed"] is False
    assert world.ccms.pk not in provisional.provisional_lookup_policy().student_college_ids
    with pytest.raises(
        (administrative_policy.AdministrativeReferralError, services.ReferralNotFound)
    ):
        transition(world, result["id"], expected_version=1)
    assert Referral.objects.get(pk=result["id"]).received_at is None


def test_empty_provisional_scopes_fail_closed_without_creating_evidence(world):
    now = timezone.now()
    College.objects.filter(pk__in=[world.cas.pk, world.ccms.pk]).update(is_active=False)
    lookup = provisional.provisional_lookup_policy(now)
    assert lookup.student_college_ids == frozenset()
    with pytest.raises(FacultyReferralError):
        lookup.validate(now)
    with pytest.raises(FacultyReferralError):
        faculty_policy.require_lookup_policy(now)
    assert not AuditEvent.objects.filter(
        pk=provisional.EVENT_IDS[provisional.STUDENT_CONFIRMATION]
    ).exists()

    College.objects.filter(pk__in=[world.cas.pk, world.ccms.pk]).update(is_active=True)
    User.objects.filter(pk__in=[world.counselor.pk, world.staff.pk]).update(is_active=False)
    acknowledgment = provisional.provisional_acknowledgment_policy(now)
    assert acknowledgment.actor_ids == frozenset()
    with pytest.raises(administrative_policy.AdministrativeReferralError):
        acknowledgment.validate(now, provisional.ACKNOWLEDGMENT)
    with pytest.raises(administrative_policy.AdministrativeReferralError):
        administrative_policy.require_policy("ACKNOWLEDGMENT", now)
    assert not AuditEvent.objects.filter(
        pk=provisional.EVENT_IDS[provisional.ACKNOWLEDGMENT]
    ).exists()


def test_approved_and_provisional_evidence_cannot_cross_activate(world):
    now = timezone.now()
    provisional_lookup = provisional.provisional_lookup_policy(now)
    approved_event = record_event(
        context=AuditContext.system(),
        action=REFERRAL_FACULTY_POLICY_RECORDED,
        outcome=AuditOutcome.SUCCESS,
        metadata={
            "decision": "APPROVED",
            "policy_kind": provisional.STUDENT_CONFIRMATION,
            "policy_digest": provisional_lookup.digest,
            "policy_version": provisional_lookup.version,
            "evidence_reference": provisional_lookup.evidence_reference,
        },
    )
    disguised_provisional = replace(
        provisional_lookup, activation_event_id=approved_event.pk
    )
    with pytest.raises(FacultyReferralError):
        disguised_provisional.validate(now)

    approved_lookup = faculty_policy.ApprovedFacultyStudentLookupPolicy(
        version="fup3a-approved-v1",
        evidence_reference="SYNTHETIC-APPROVED-NOT-INSTITUTIONAL",
        valid_from=now - timedelta(days=1),
        valid_until=now + timedelta(days=1),
        faculty_ids=frozenset({world.faculty.pk}),
        student_college_ids=frozenset({world.ccms.pk}),
        activation_event_id=uuid4(),
        maximum_confirmation_age_seconds=300,
        actor_attempt_limit=10,
        ip_attempt_limit=30,
        attempt_window_seconds=300,
    )
    provisional_event = record_event(
        context=AuditContext.system(),
        action=REFERRAL_FACULTY_POLICY_RECORDED,
        outcome=AuditOutcome.SUCCESS,
        metadata={
            "decision": "PROVISIONAL",
            "policy_kind": provisional.STUDENT_CONFIRMATION,
            "policy_digest": approved_lookup.digest,
            "policy_version": approved_lookup.version,
            "evidence_reference": approved_lookup.evidence_reference,
        },
    )
    disguised_approved = replace(approved_lookup, activation_event_id=provisional_event.pk)
    with pytest.raises(FacultyReferralError):
        disguised_approved.validate(timezone.now())

    provisional_admin = provisional.provisional_acknowledgment_policy(now)
    approved_admin_event = record_event(
        context=AuditContext.system(),
        action=administrative_policy.POLICY_RECORDED,
        outcome=AuditOutcome.SUCCESS,
        metadata={
            "decision": "APPROVED",
            "policy_kind": provisional.ACKNOWLEDGMENT,
            "policy_digest": provisional_admin.digest,
            "policy_version": provisional_admin.version,
            "evidence_reference": provisional_admin.evidence_reference,
        },
    )
    with pytest.raises(administrative_policy.AdministrativeReferralError):
        replace(provisional_admin, activation_event_id=approved_admin_event.pk).validate(
            now, provisional.ACKNOWLEDGMENT
        )

    approved_admin = administrative_policy.ApprovedAdministrativePolicy(
        version="fup3a-approved-admin-v1",
        evidence_reference="SYNTHETIC-APPROVED-NOT-INSTITUTIONAL",
        contract_evidence_reference="SYNTHETIC-APPROVED-CONTRACT",
        kind=provisional.ACKNOWLEDGMENT,
        contract=administrative_policy.CONTRACTS[provisional.ACKNOWLEDGMENT],
        valid_from=now - timedelta(days=1),
        valid_until=now + timedelta(days=1),
        actor_ids=provisional_admin.actor_ids,
        student_college_ids=provisional_admin.student_college_ids,
        roles=provisional_admin.roles,
        activation_event_id=uuid4(),
    )
    provisional_admin_event = record_event(
        context=AuditContext.system(),
        action=administrative_policy.POLICY_RECORDED,
        outcome=AuditOutcome.SUCCESS,
        metadata={
            "decision": "PROVISIONAL",
            "policy_kind": provisional.ACKNOWLEDGMENT,
            "policy_digest": approved_admin.digest,
            "policy_version": approved_admin.version,
            "evidence_reference": approved_admin.evidence_reference,
        },
    )
    with pytest.raises(administrative_policy.AdministrativeReferralError):
        replace(approved_admin, activation_event_id=provisional_admin_event.pk).validate(
            timezone.now(), provisional.ACKNOWLEDGMENT
        )


def test_empty_scope_keeps_events_uncreated_even_after_prior_resolution(world):
    now = timezone.now()
    provisional.provisional_lookup_policy(now)
    assert AuditEvent.objects.filter(
        pk=provisional.EVENT_IDS[provisional.STUDENT_CONFIRMATION]
    ).exists()
    College.objects.filter(pk__in=[world.cas.pk, world.ccms.pk]).update(is_active=False)
    with pytest.raises(FacultyReferralError):
        faculty_policy.require_lookup_policy(now)
    assert AuditEvent.objects.filter(
        pk=provisional.EVENT_IDS[provisional.STUDENT_CONFIRMATION]
    ).count() == 1
    assert not AuditEvent.objects.filter(
        pk=provisional.EVENT_IDS[provisional.ACKNOWLEDGMENT]
    ).exists()
