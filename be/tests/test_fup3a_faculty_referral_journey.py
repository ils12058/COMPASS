"""FUP-3A: canonical Faculty Referral journey and live authorization boundaries."""

from datetime import timedelta
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet
from django.test import Client
from django.utils import timezone

from compass.accounts.bootstrap import sync_identity_policy
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
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
    faculty_rules,
    faculty_services,
    services,
)
from compass.referrals.faculty_rules import FacultyReferralError
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
        "administratively_closed_at": item.administratively_closed_at,
        "administratively_closed_by_id": item.administratively_closed_by_id,
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

    result, created = submit(world, confirmation["confirmation"])
    assert created is True and result["state"] == "SUBMITTED"
    row = Referral.objects.get(pk=result["id"])
    assert row.submission_channel == "FACULTY_PORTAL"
    assert not ReferralAction.objects.exists()
    assert not GuidanceFollowUp.objects.exists()

    faculty = authenticated(world.faculty_issued)
    assert_faculty_projection(faculty, row.pk, "SUBMITTED")

    acknowledged = transition(world, row.pk, expected_version=1)
    row.refresh_from_db()
    assert acknowledged["state"] == "RECEIVED_BY_GCO" and acknowledged["version"] == 2
    assert row.acknowledged_by_id == world.counselor.pk
    assert prepare_candidate_intent(referral_id=row.pk, event="RECEIVED_BY_GCO") is not None
    assert_faculty_projection(faculty, row.pk, "RECEIVED_BY_GCO")
    assert Notification.objects.count() == start_notifications + 1 == 1
    assert EmailDelivery.objects.count() == start_deliveries + 1 == 1

    first = linked_followup(world, row.pk, "fup3a-completed-after-closure")
    second = linked_followup(world, row.pk, "fup3a-open-after-void")
    assert first.visibility == "OPERATIONAL" and first.category == "REFERRAL_ACTION"
    assert first.assigned_to_id == world.staff.pk
    assert followup_services.get_followup(actor=world.staff, followup_id=first.pk).pk == first.pk
    staff_list = followup_services.list_followups(actor=world.staff)
    assert {item.pk for item in staff_list.items} == {first.pk, second.pk}
    assert GuidanceFollowUp.objects.count() == 2
    # Follow-Up assignment notices remain scoped to their staff assignee.
    assignment_notifications = list(
        Notification.objects.filter(source_type="guidance_followup_event")
    )
    assert len(assignment_notifications) == 2
    for notification in assignment_notifications:
        assert notification.recipient_id == world.staff.pk
        assert notification.recipient_id != world.faculty.pk
        assert notification.target_type == "GUIDANCE_FOLLOW_UP"
        assert notification.source_type == "guidance_followup_event"
    assert EmailDelivery.objects.count() == start_deliveries + 3
    notifications_before_closure = Notification.objects.count()
    assert_faculty_projection(faculty, row.pk, "RECEIVED_BY_GCO")

    closed = transition(world, row.pk, close=True, expected_version=2)
    row.refresh_from_db()
    assert closed["state"] == "ADMINISTRATIVELY_CLOSED" and closed["version"] == 3
    assert GuidanceFollowUp.objects.get(pk=first.pk).status == "PENDING"
    assert GuidanceFollowUp.objects.get(pk=second.pk).status == "PENDING"
    assert prepare_candidate_intent(referral_id=row.pk, event="ADMINISTRATIVELY_CLOSED") is not None
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
    assert {
        "status": second_before.status,
        "assigned_to_id": second_before.assigned_to_id,
        "source_kind": second_before.source_kind,
        "source_id": second_before.source_id,
        "version": second_before.version,
        "completed_at": second_before.completed_at,
        "cancelled_at": second_before.cancelled_at,
        "updated_at": second_before.updated_at,
    } == second_snapshot
    assert GuidanceFollowUp.objects.count() == followup_count
    assert followup_services.get_followup(actor=world.staff, followup_id=second.pk).pk == (
        second.pk
    )
    assert second.pk in {
        item.pk for item in followup_services.list_followups(actor=world.staff).items
    }
    detail = authenticated(world.staff_issued).get(f"/api/v1/guidance-followups/{second.pk}")
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
    assert Notification.objects.count() == notifications_before_closure + 1
    assert Notification.objects.filter(target_type="FACULTY_REFERRAL").count() == 2
    assert Notification.objects.filter(source_type="faculty_referral_administration").count() == 2
    assert EmailDelivery.objects.count() == start_deliveries + 4


def test_live_scope_removal_denies_affected_operation(world):
    assert (
        confirm(world, actor=world.other_faculty, issued=world.other_faculty_issued)["confirmed"]
        is True
    )
    world.other_faculty.is_active = False
    world.other_faculty.save(update_fields=["is_active"])
    with pytest.raises(FacultyReferralError):
        confirm(world, actor=world.other_faculty, issued=world.other_faculty_issued)

    ticket = confirm(world)["confirmation"]
    result, _ = submit(world, ticket)
    world.ccms.is_active = False
    world.ccms.save(update_fields=["is_active"])
    assert confirm(world)["confirmed"] is False
    with pytest.raises((faculty_rules.AdministrativeReferralError, services.ReferralNotFound)):
        transition(world, result["id"], expected_version=1)
    assert Referral.objects.get(pk=result["id"]).received_at is None
