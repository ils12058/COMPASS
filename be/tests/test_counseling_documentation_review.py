"""CENC-4: the derived Needs-documentation worklist and the linked-Encounter fact."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.conf import settings
from django.test import Client
from django.utils import timezone

from compass.accounts.models import Capability, UserCapabilityOverride
from compass.appointments.models import Appointment, AppointmentStatus
from compass.audit.models import AuditEvent
from compass.counseling.models import CounselingEncounter, CounselingEntryMode
from compass.counseling.services import (
    CounselingDocumentationReviewReason,
    CounselingNotPermitted,
    appointment_encounter_linked,
    appointment_encounter_matches,
    appointment_encounter_recorded,
    list_documentation_review,
)
from compass.feedback.models import (
    CustomerFeedbackService,
    FeedbackOpportunity,
    FeedbackOpportunitySourceType,
)
from compass.notifications.models import Notification
from compass.routine_interviews.models import RoutineInterview
from compass.service_catalog.services import create_service
from tests.test_counseling import (
    auth_client,
    context,
    create_counseling_service,
    make_appointment,
    make_user,
    sync_policy,
)

REVIEW_URL = "/api/v1/counseling/documentation-review"
REVIEW_ITEM_FIELDS = {
    "appointment_id",
    "reference_code",
    "student",
    "delivery_mode",
    "starts_at",
    "ends_at",
    "status",
    "reason",
    "encounter_id",
}


def setup_domain(prefix: str = "review", *, with_service: bool = True):
    sync_policy()
    admin = make_user(f"{prefix}-admin@example.edu", "IT_ADMIN")
    counselor = make_user(f"{prefix}-counselor@example.edu", "COUNSELOR")
    student = make_user(f"{prefix}-student@example.edu", "STUDENT")
    service = create_counseling_service(admin) if with_service else None
    return admin, counselor, student, service


def review_items(counselor, **kwargs):
    return list_documentation_review(counselor=counselor, **kwargs).items


def review_by_appointment(counselor, **kwargs):
    return {str(item.appointment.pk): item for item in review_items(counselor, **kwargs)}


def move(appointment, *, starts_at=None, ends_at=None) -> Appointment:
    """``make_appointment`` fixes the session window; boundary cases need their own."""

    fields = []
    if starts_at is not None:
        appointment.starts_at = starts_at
        fields.append("starts_at")
    if ends_at is not None:
        appointment.ends_at = ends_at
        fields.append("ends_at")
    appointment.save(update_fields=fields)
    return appointment


def link_encounter(
    *,
    appointment: Appointment,
    counselor,
    student,
    service,
    entry_mode=CounselingEntryMode.APPOINTMENT,
    delivery_mode: str | None = None,
    owner=None,
    student_override=None,
    service_override=None,
):
    """A linked Encounter, written straight to the table: this slice never creates one."""

    ended_at = timezone.now() - timedelta(minutes=10)
    return CounselingEncounter.objects.create(
        student=student_override or student,
        counselor=owner or counselor,
        service=service_override or service,
        appointment=appointment,
        entry_mode=entry_mode,
        delivery_mode=delivery_mode or appointment.delivery_mode,
        started_at=ended_at - timedelta(minutes=45),
        ended_at=ended_at,
        created_by=counselor,
    )


@pytest.mark.django_db
def test_worklist_reports_the_three_reasons():
    admin, counselor, student, service = setup_domain("review-reasons")
    missing = make_appointment(
        student=student,
        provider=counselor,
        service=service,
        status=AppointmentStatus.COMPLETED,
    )
    uncompleted = make_appointment(student=student, provider=counselor, service=service)
    recorded = link_encounter(
        appointment=uncompleted, counselor=counselor, student=student, service=service
    )
    conflict = make_appointment(
        student=student,
        provider=counselor,
        service=service,
        status=AppointmentStatus.COMPLETED,
    )
    walk_in = link_encounter(
        appointment=conflict,
        counselor=counselor,
        student=student,
        service=service,
        entry_mode=CounselingEntryMode.WALK_IN,
    )

    by_id = review_by_appointment(counselor)
    assert set(by_id) == {str(missing.pk), str(uncompleted.pk), str(conflict.pk)}

    assert by_id[str(missing.pk)].reason is CounselingDocumentationReviewReason.MISSING_ENCOUNTER
    assert by_id[str(missing.pk)].encounter_id is None
    assert by_id[str(missing.pk)].appointment.status == AppointmentStatus.COMPLETED

    assert (
        by_id[str(uncompleted.pk)].reason
        is CounselingDocumentationReviewReason.UNCOMPLETED_APPOINTMENT
    )
    assert by_id[str(uncompleted.pk)].encounter_id == recorded.pk
    assert by_id[str(uncompleted.pk)].appointment.status == AppointmentStatus.SCHEDULED

    assert by_id[str(conflict.pk)].reason is CounselingDocumentationReviewReason.LINKED_CONFLICT
    assert by_id[str(conflict.pk)].encounter_id == walk_in.pk

    row = by_id[str(missing.pk)].appointment
    assert row.student_id == student.pk
    assert row.student.get_full_name() == student.get_full_name()
    assert row.reference_code == missing.reference_code

    payload = auth_client(counselor).get(REVIEW_URL).json()
    assert {item["reason"] for item in payload["items"]} == {
        "MISSING_ENCOUNTER",
        "UNCOMPLETED_APPOINTMENT",
        "LINKED_CONFLICT",
    }
    for item in payload["items"]:
        assert set(item) == REVIEW_ITEM_FIELDS
        assert item["student"] == {
            "id": str(student.pk),
            "institutional_id": student.institutional_id,
            "display_name": student.get_full_name(),
            "profile_photo_url": None,
            "profile_photo_updated_at": None,
        }


@pytest.mark.django_db
def test_worklist_excludes_states_that_need_no_reconciliation():
    admin, counselor, student, service = setup_domain("review-exclusions")
    other = make_user("review-exclusions-other@example.edu", "COUNSELOR")
    inactive_student = make_user("review-exclusions-inactive@example.edu", "STUDENT", active=False)
    other_service = create_service(
        code="CAREER_GUIDANCE", name="Career Guidance", context=context(admin)
    )

    cancelled_bare = make_appointment(
        student=student,
        provider=counselor,
        service=service,
        status=AppointmentStatus.CANCELLED,
    )
    cancelled_linked = make_appointment(
        student=student,
        provider=counselor,
        service=service,
        status=AppointmentStatus.CANCELLED,
    )
    link_encounter(
        appointment=cancelled_linked, counselor=counselor, student=student, service=service
    )
    no_show_bare = make_appointment(
        student=student,
        provider=counselor,
        service=service,
        status=AppointmentStatus.NO_SHOW,
    )
    no_show_linked = make_appointment(
        student=student,
        provider=counselor,
        service=service,
        status=AppointmentStatus.NO_SHOW,
    )
    link_encounter(
        appointment=no_show_linked, counselor=counselor, student=student, service=service
    )
    scheduled_bare = make_appointment(student=student, provider=counselor, service=service)
    completed_matching = make_appointment(
        student=student,
        provider=counselor,
        service=service,
        status=AppointmentStatus.COMPLETED,
    )
    link_encounter(
        appointment=completed_matching, counselor=counselor, student=student, service=service
    )
    other_provider = make_appointment(
        student=student,
        provider=other,
        service=service,
        status=AppointmentStatus.COMPLETED,
    )
    wrong_service = make_appointment(
        student=student,
        provider=counselor,
        service=other_service,
        status=AppointmentStatus.COMPLETED,
    )
    inactive_owner = make_appointment(
        student=inactive_student,
        provider=counselor,
        service=service,
        status=AppointmentStatus.COMPLETED,
    )
    upcoming = make_appointment(student=student, provider=counselor, service=service)
    link_encounter(appointment=upcoming, counselor=counselor, student=student, service=service)
    later = timezone.now() + timedelta(hours=2)
    move(upcoming, starts_at=later, ends_at=later + timedelta(hours=1))
    future_conflict = make_appointment(student=student, provider=counselor, service=service)
    link_encounter(
        appointment=future_conflict,
        counselor=counselor,
        student=student,
        service=service,
        entry_mode=CounselingEntryMode.WALK_IN,
    )
    move(future_conflict, starts_at=later, ends_at=later + timedelta(hours=1))

    excluded = {
        str(cancelled_bare.pk),
        str(cancelled_linked.pk),
        str(no_show_bare.pk),
        str(no_show_linked.pk),
        str(scheduled_bare.pk),
        str(completed_matching.pk),
        str(other_provider.pk),
        str(wrong_service.pk),
        str(inactive_owner.pk),
        str(upcoming.pk),
        str(future_conflict.pk),
    }
    assert Appointment.objects.filter(pk__in=excluded).count() == len(excluded)
    assert set(review_by_appointment(counselor)) & excluded == set()


@pytest.mark.django_db
def test_worklist_waits_for_the_online_access_window_to_close():
    admin, counselor, student, service = setup_domain("review-grace")
    grace = timedelta(seconds=settings.ECOUNSELING_REJOIN_GRACE_SECONDS)
    ended = timezone.now() - timedelta(hours=1)

    online = make_appointment(
        student=student, provider=counselor, service=service, delivery_mode="ONLINE"
    )
    link_encounter(appointment=online, counselor=counselor, student=student, service=service)
    move(online, starts_at=ended - timedelta(hours=1), ends_at=ended)

    # Completing is refused while the access period is open, so the row must not appear yet.
    still_open = review_by_appointment(counselor, now=ended + grace - timedelta(seconds=1))
    assert str(online.pk) not in still_open
    closed = review_by_appointment(counselor, now=ended + grace + timedelta(seconds=1))
    assert closed[str(online.pk)].reason is (
        CounselingDocumentationReviewReason.UNCOMPLETED_APPOINTMENT
    )

    # An IN_PERSON session is gated only by its own end, including the exact ending instant.
    in_person = make_appointment(student=student, provider=counselor, service=service)
    link_encounter(appointment=in_person, counselor=counselor, student=student, service=service)
    move(in_person, starts_at=ended - timedelta(hours=1), ends_at=ended)
    assert str(in_person.pk) not in review_by_appointment(
        counselor, now=ended - timedelta(seconds=1)
    )
    assert str(in_person.pk) in review_by_appointment(counselor, now=ended)


@pytest.mark.django_db
def test_worklist_gives_one_row_per_appointment_with_conflict_precedence():
    admin, counselor, student, service = setup_domain("review-precedence")
    completed_conflict = make_appointment(
        student=student,
        provider=counselor,
        service=service,
        status=AppointmentStatus.COMPLETED,
    )
    link_encounter(
        appointment=completed_conflict,
        counselor=counselor,
        student=student,
        service=service,
        entry_mode=CounselingEntryMode.CALLED_IN,
    )
    scheduled_conflict = make_appointment(student=student, provider=counselor, service=service)
    link_encounter(
        appointment=scheduled_conflict,
        counselor=counselor,
        student=student,
        service=service,
        delivery_mode="ONLINE",
    )

    items = review_items(counselor)
    assert len(items) == 2
    assert {item.appointment.pk for item in items} == {
        completed_conflict.pk,
        scheduled_conflict.pk,
    }
    assert {item.reason for item in items} == {CounselingDocumentationReviewReason.LINKED_CONFLICT}


@pytest.mark.django_db
def test_worklist_is_scoped_to_the_reading_counselor():
    admin, counselor, student, service = setup_domain("review-scope")
    other = make_user("review-scope-other@example.edu", "COUNSELOR")
    mine = make_appointment(
        student=student,
        provider=counselor,
        service=service,
        status=AppointmentStatus.COMPLETED,
    )
    theirs = make_appointment(
        student=student,
        provider=other,
        service=service,
        status=AppointmentStatus.COMPLETED,
    )

    assert set(review_by_appointment(counselor)) == {str(mine.pk)}
    assert set(review_by_appointment(other)) == {str(theirs.pk)}


@pytest.mark.django_db
def test_worklist_reports_a_reassigned_conflict_without_exposing_the_encounter():
    admin, counselor, student, service = setup_domain("review-reassign")
    appointment = make_appointment(
        student=student,
        provider=counselor,
        service=service,
        status=AppointmentStatus.COMPLETED,
    )
    former_owner = make_user("review-reassign-former@example.edu", "COUNSELOR")
    link_encounter(
        appointment=appointment,
        counselor=counselor,
        student=student,
        service=service,
        owner=former_owner,
    )

    item = review_by_appointment(counselor)[str(appointment.pk)]
    assert item.reason is CounselingDocumentationReviewReason.LINKED_CONFLICT
    assert item.encounter_id is None

    rows = auth_client(counselor).get(REVIEW_URL).json()["items"]
    row = next(row for row in rows if row["appointment_id"] == str(appointment.pk))
    assert row["encounter_id"] is None
    assert row["reason"] == "LINKED_CONFLICT"
    assert appointment_encounter_linked(actor=counselor, appointment=appointment) is True
    assert appointment_encounter_recorded(actor=counselor, appointment=appointment) is False


@pytest.mark.django_db
def test_worklist_survives_service_deactivation_and_needs_a_configured_service():
    admin, counselor, student, _ = setup_domain("review-deactivation", with_service=False)
    client = auth_client(counselor)

    unconfigured = client.get(REVIEW_URL)
    assert unconfigured.status_code == 409
    assert unconfigured.json()["error"]["code"] == "counseling_service_not_configured"

    service = create_counseling_service(admin)
    appointment = make_appointment(
        student=student,
        provider=counselor,
        service=service,
        status=AppointmentStatus.COMPLETED,
    )
    # The catalog refuses to deactivate the canonical Service, so this is the only way to reach the
    # historical row state the worklist must still read.
    service.is_active = False
    service.save(update_fields=["is_active"])

    response = client.get(REVIEW_URL)
    assert response.status_code == 200
    assert [row["appointment_id"] for row in response.json()["items"]] == [str(appointment.pk)]


@pytest.mark.django_db
def test_worklist_orders_by_session_end_and_pages_canically():
    admin, counselor, student, service = setup_domain("review-paging")
    anchors = []
    for index in range(6):
        appointment = make_appointment(
            student=student,
            provider=counselor,
            service=service,
            status=AppointmentStatus.COMPLETED,
        )
        ends_at = timezone.now() - timedelta(days=6 - index, hours=1)
        move(appointment, starts_at=ends_at - timedelta(hours=1), ends_at=ends_at)
        anchors.append(appointment)

    first = list_documentation_review(counselor=counselor, page=1, page_size=5)
    assert [item.appointment.pk for item in first.items] == [row.pk for row in anchors[:5]]
    assert first.has_next is True

    second = list_documentation_review(counselor=counselor, page=2, page_size=5)
    assert [item.appointment.pk for item in second.items] == [anchors[5].pk]
    assert second.has_next is False

    client = auth_client(counselor)
    assert client.get(REVIEW_URL, {"page": 0}).status_code == 422
    assert client.get(REVIEW_URL, {"page_size": 51}).status_code == 422


def state_snapshot() -> dict:
    return {
        "encounters": list(CounselingEncounter.objects.order_by("pk").values()),
        "routines": list(RoutineInterview.objects.order_by("pk").values()),
        "feedback": list(FeedbackOpportunity.objects.order_by("pk").values()),
        "notifications": list(Notification.objects.order_by("pk").values()),
        "audits": list(AuditEvent.objects.order_by("pk").values()),
    }


@pytest.mark.django_db
def test_worklist_reads_and_never_writes():
    admin, counselor, student, service = setup_domain("review-readonly")
    reconciled = make_appointment(
        student=student,
        provider=counselor,
        service=service,
        status=AppointmentStatus.COMPLETED,
    )
    encounter = link_encounter(
        appointment=reconciled, counselor=counselor, student=student, service=service
    )
    RoutineInterview.objects.create(
        student=student,
        counselor=counselor,
        appointment=reconciled,
        counseling_encounter=encounter,
        entry_mode=CounselingEntryMode.APPOINTMENT,
        delivery_mode="IN_PERSON",
        intake_submitted_at=timezone.now(),
        evaluation_finalized_at=timezone.now(),
        student_intake_ciphertext="unread-by-projection",
        counselor_evaluation_ciphertext="unread-by-projection",
    )
    FeedbackOpportunity.objects.create(
        student=student,
        source_type=FeedbackOpportunitySourceType.COUNSELING_ENCOUNTER,
        source_id=encounter.pk,
        service_kind=CustomerFeedbackService.COUNSELING,
        service_label_snapshot="Counseling",
        service_completed_at=timezone.now(),
    )
    orphan = make_appointment(
        student=student,
        provider=counselor,
        service=service,
        status=AppointmentStatus.COMPLETED,
    )

    before = state_snapshot()
    response = auth_client(counselor).get(REVIEW_URL)
    assert response.status_code == 200
    assert [row["appointment_id"] for row in response.json()["items"]] == [str(orphan.pk)]
    assert state_snapshot() == before
    assert Appointment.objects.get(pk=reconciled.pk).status == AppointmentStatus.COMPLETED


@pytest.mark.django_db
@pytest.mark.parametrize("role", ["STUDENT", "GUIDANCE_SERVICES_STAFF", "IT_ADMIN"])
def test_documentation_review_is_counselor_only(role):
    admin, counselor, student, service = setup_domain(f"review-role-{role}")
    make_appointment(
        student=student,
        provider=counselor,
        service=service,
        status=AppointmentStatus.COMPLETED,
    )
    actor = make_user(f"review-role-{role}@example.edu", role)

    assert auth_client(actor).get(REVIEW_URL).status_code == 403
    with pytest.raises(CounselingNotPermitted):
        list_documentation_review(counselor=actor)


@pytest.mark.django_db
def test_documentation_review_requires_session_and_view_capability():
    admin, counselor, student, service = setup_domain("review-authz")
    appointment = make_appointment(
        student=student,
        provider=counselor,
        service=service,
        status=AppointmentStatus.COMPLETED,
    )

    assert Client().get(REVIEW_URL).status_code == 401

    UserCapabilityOverride.objects.create(
        user=counselor,
        capability=Capability.objects.get(code="counseling.view_assigned"),
        effect="REVOKE",
        reason="synthetic separation of duties",
    )
    assert auth_client(counselor).get(REVIEW_URL).status_code == 403
    # The service is the read-scope boundary; the capability gate lives in the endpoint.
    assert str(appointment.pk) in {str(item.appointment.pk) for item in review_items(counselor)}

    UserCapabilityOverride.objects.all().delete()
    counselor.is_active = False
    counselor.save(update_fields=["is_active"])
    with pytest.raises(CounselingNotPermitted):
        list_documentation_review(counselor=counselor)


@pytest.mark.django_db
def test_recorded_and_linked_facts_agree_with_the_worklist_reason():
    admin, counselor, student, service = setup_domain("review-parity")
    outsider = make_user("review-parity-outsider@example.edu", "STUDENT")

    recorded_match = make_appointment(
        student=student,
        provider=counselor,
        service=service,
        status=AppointmentStatus.COMPLETED,
    )
    link_encounter(
        appointment=recorded_match, counselor=counselor, student=student, service=service
    )
    linked_only = make_appointment(
        student=student,
        provider=counselor,
        service=service,
        status=AppointmentStatus.COMPLETED,
    )
    link_encounter(
        appointment=linked_only,
        counselor=counselor,
        student=student,
        service=service,
        entry_mode=CounselingEntryMode.REFERRED,
    )
    nothing_linked = make_appointment(
        student=student,
        provider=counselor,
        service=service,
        status=AppointmentStatus.COMPLETED,
    )

    by_id = review_by_appointment(counselor)
    for appointment in (recorded_match, linked_only, nothing_linked):
        recorded = appointment_encounter_recorded(actor=counselor, appointment=appointment)
        linked = appointment_encounter_linked(actor=counselor, appointment=appointment)
        assert recorded is appointment_encounter_matches(appointment)
        assert (recorded is None) == (linked is None)
        if recorded is True:
            assert linked is True
        if linked is True and recorded is False:
            assert by_id[str(appointment.pk)].reason is (
                CounselingDocumentationReviewReason.LINKED_CONFLICT
            )
    assert str(recorded_match.pk) not in by_id
    assert str(linked_only.pk) in by_id
    assert str(nothing_linked.pk) in by_id

    # Neither fact is exposed to someone who is not the assigned Counselor.
    assert appointment_encounter_linked(actor=outsider, appointment=linked_only) is None
    assert appointment_encounter_recorded(actor=outsider, appointment=linked_only) is None
