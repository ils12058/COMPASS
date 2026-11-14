"""CW-1 Counseling cases: opening, session links, corrections, counts and access boundaries."""

from __future__ import annotations

import json
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from compass.accounts.models import Capability, Designation, UserCapabilityOverride, UserDesignation
from compass.appointments.models import AppointmentStatus
from compass.audit.models import AuditEvent
from compass.counseling.case_models import (
    CounselingCase,
    CounselingCaseEvent,
    CounselingCaseSession,
)
from compass.counseling.case_services import (
    CounselingCaseChanged,
    CounselingCaseClosed,
    CounselingCaseInvalid,
    CounselingCaseNotFound,
    CounselingCaseNotPermitted,
    CounselingCaseReviewRequired,
    CounselingCaseSessionAlreadyLinked,
    CounselingCaseSessionNotFound,
    CounselingCaseSessionStudentMismatch,
    CounselingCaseSourceInvalid,
    CounselingCaseSourceNotFound,
    get_case,
    get_opening_context,
    link_session,
    list_my_cases,
    list_session_candidates,
    open_case,
    unlink_session,
)
from compass.counseling.models import CounselingEncounter, StudentSessionSummary
from compass.counseling.services import create_encounter
from compass.counseling.student_session_summaries import (
    list_my_student_session_summaries,
    publish_assigned_student_session_summary,
    put_assigned_student_session_summary,
)
from compass.routine_interviews.models import RoutineInterview
from compass.service_catalog.models import Service
from tests.test_counseling import (
    auth_client,
    context,
    create_counseling_service,
    csrf,
    make_appointment,
    make_user,
    sync_policy,
)

CASES = "/api/v1/counseling/cases"


def world(prefix: str = "case") -> SimpleNamespace:
    sync_policy()
    admin = make_user(f"{prefix}-admin@example.edu", "IT_ADMIN")
    head = make_user(f"{prefix}-head@example.edu", "COUNSELOR")
    UserDesignation.objects.create(
        user=head, designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR")
    )
    return SimpleNamespace(
        admin=admin,
        head=head,
        a=make_user(f"{prefix}-a@example.edu", "COUNSELOR"),
        b=make_user(f"{prefix}-b@example.edu", "COUNSELOR"),
        goa=make_user(f"{prefix}-goa@example.edu", "GUIDANCE_OFFICE_ASSISTANT"),
        faculty=make_user(f"{prefix}-faculty@example.edu", "FACULTY"),
        officer=make_user(f"{prefix}-officer@example.edu", "INSTITUTIONAL_OFFICER"),
        student=make_user(f"{prefix}-student@example.edu", "STUDENT", institutional_id="2026-0001"),
        other=make_user(f"{prefix}-other@example.edu", "STUDENT", institutional_id="2026-0002"),
        service=create_counseling_service(admin),
    )


def record(counselor, student, *, hours_ago: int = 3, appointment=None) -> CounselingEncounter:
    end = timezone.now() - timedelta(hours=hours_ago)
    return create_encounter(
        counselor=counselor,
        student_id=None if appointment else student.pk,
        entry_mode="APPOINTMENT" if appointment else "WALK_IN",
        delivery_mode=None if appointment else "IN_PERSON",
        appointment_id=appointment.pk if appointment else None,
        started_at=end - timedelta(minutes=50),
        ended_at=end,
        context=context(counselor),
    )


def intake(actor, student, known=()) -> CounselingCase:
    return open_case(
        actor=actor,
        origin="INTAKE",
        student_id=student.pk,
        known_active_case_ids=known,
        context=context(actor),
    )


def link(actor, case, encounter):
    case.refresh_from_db()
    return link_session(
        actor=actor,
        case_id=case.pk,
        encounter_id=encounter.pk,
        expected_version=case.version,
        context=context(actor),
    )


def post(client, path, payload):
    return client.post(
        path, data=json.dumps(payload), content_type="application/json", **csrf(client)
    )


@pytest.mark.django_db
def test_intake_opens_one_active_case_owned_by_the_opening_counselor():
    w = world()

    case = intake(w.a, w.student)

    assert case.status == "ACTIVE"
    assert case.primary_counselor_id == w.a.pk
    assert case.opened_by_id == w.a.pk
    assert case.student_id == w.student.pk
    assert case.origin == "INTAKE"
    assert case.version == 1
    year = timezone.localtime(case.opened_at).year
    assert case.reference_code == f"CASE-{year:04d}-000001"
    overview = get_case(actor=w.a, case_id=case.pk)
    assert overview.summary.session_count == 0
    assert overview.summary.latest_session_at is None
    assert overview.can_manage is True
    opened = CounselingCaseEvent.objects.get(case=case)
    assert (opened.kind, opened.detail_code) == ("OPENED", "INTAKE")
    assert opened.actor_id == opened.primary_counselor_id == w.a.pk
    audit = AuditEvent.objects.get(action="counseling.case.opened")
    assert audit.target_id == str(case.pk)
    assert set(audit.metadata) == {
        "reference_code",
        "origin",
        "student_id",
        "primary_counselor_id",
    }


@pytest.mark.django_db
def test_opening_from_a_recorded_session_links_that_session_only():
    w = world()
    first = record(w.a, w.student, hours_ago=30)
    legacy = record(w.a, w.student, hours_ago=60)

    case = open_case(actor=w.a, origin="ENCOUNTER", source_id=first.pk, context=context(w.a))

    overview = get_case(actor=w.a, case_id=case.pk)
    assert [item.link.encounter_id for item in overview.sessions] == [first.pk]
    assert overview.summary.session_count == 1
    assert overview.summary.latest_session_at == first.started_at
    assert overview.origin_encounter_id == first.pk
    # Another session with the same Student is never grouped into the case on its own.
    assert not CounselingCaseSession.objects.filter(encounter=legacy).exists()
    kinds = list(
        CounselingCaseEvent.objects.filter(case=case)
        .order_by("occurred_at", "kind")
        .values_list("kind", flat=True)
    )
    assert sorted(kinds) == ["OPENED", "SESSION_LINKED"]


@pytest.mark.django_db
def test_opening_from_a_scheduled_appointment_never_links_a_later_session_automatically():
    w = world()
    appointment = make_appointment(student=w.student, provider=w.a, service=w.service)

    case = open_case(
        actor=w.a, origin="APPOINTMENT", source_id=appointment.pk, context=context(w.a)
    )
    assert get_case(actor=w.a, case_id=case.pk).summary.session_count == 0

    session = record(w.a, w.student, appointment=appointment)
    overview = get_case(actor=w.a, case_id=case.pk)
    # The scheduled Appointment is not a session, and its recorded session waits for a decision.
    assert overview.summary.session_count == 0
    assert overview.unlinked_origin_session.pk == session.pk
    assert overview.origin_appointment.pk == appointment.pk

    link(w.a, case, session)
    overview = get_case(actor=w.a, case_id=case.pk)
    assert overview.summary.session_count == 1
    assert overview.unlinked_origin_session is None


@pytest.mark.django_db
def test_a_session_with_an_appointment_and_a_routine_interview_counts_once():
    w = world()
    appointment = make_appointment(
        student=w.student, provider=w.a, service=w.service, status=AppointmentStatus.COMPLETED
    )
    session = record(w.a, w.student, appointment=appointment)
    routine = RoutineInterview.objects.create(
        student=w.student,
        counselor=w.a,
        appointment=appointment,
        counseling_encounter=session,
        entry_mode="APPOINTMENT",
        delivery_mode="IN_PERSON",
        student_intake_ciphertext="UNREADABLE-SYNTHETIC-INTAKE",
        counselor_evaluation_ciphertext="UNREADABLE-SYNTHETIC-EVALUATION",
    )
    # Appointments that never became sessions exist for the same Student and Counselor.
    make_appointment(student=w.student, provider=w.a, service=w.service)
    make_appointment(
        student=w.student, provider=w.a, service=w.service, status=AppointmentStatus.CANCELLED
    )
    make_appointment(
        student=w.student, provider=w.a, service=w.service, status=AppointmentStatus.NO_SHOW
    )

    case = open_case(
        actor=w.a, origin="ROUTINE_INTERVIEW", source_id=routine.pk, context=context(w.a)
    )

    overview = get_case(actor=w.a, case_id=case.pk)
    assert overview.summary.session_count == 1
    assert [item.link.encounter_id for item in overview.sessions] == [session.pk]
    assert overview.origin_routine_interview_id == routine.pk
    # The same session can't be added again through its Appointment.
    with pytest.raises(CounselingCaseSessionAlreadyLinked):
        open_case(
            actor=w.a,
            origin="APPOINTMENT",
            source_id=appointment.pk,
            known_active_case_ids=[case.pk],
            context=context(w.a),
        )


@pytest.mark.django_db
def test_sources_must_be_the_counselors_own_eligible_records():
    w = world()
    theirs = record(w.b, w.student)
    their_appointment = make_appointment(student=w.student, provider=w.b, service=w.service)
    their_routine = RoutineInterview.objects.create(
        student=w.student,
        counselor=w.b,
        entry_mode="WALK_IN",
        delivery_mode="IN_PERSON",
        student_intake_ciphertext="UNREADABLE-SYNTHETIC-INTAKE",
        counselor_evaluation_ciphertext="UNREADABLE-SYNTHETIC-EVALUATION",
    )
    for origin, source in (
        ("ENCOUNTER", theirs.pk),
        ("APPOINTMENT", their_appointment.pk),
        ("ROUTINE_INTERVIEW", their_routine.pk),
        ("ENCOUNTER", uuid4()),
    ):
        with pytest.raises(CounselingCaseSourceNotFound):
            open_case(actor=w.a, origin=origin, source_id=source, context=context(w.a))

    for status in (AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW):
        closed = make_appointment(student=w.student, provider=w.a, service=w.service, status=status)
        with pytest.raises(CounselingCaseSourceInvalid):
            open_case(actor=w.a, origin="APPOINTMENT", source_id=closed.pk, context=context(w.a))

    other_service = Service.objects.create(code="SYNTHETIC", name="Synthetic")
    unrelated = make_appointment(student=w.student, provider=w.a, service=other_service)
    with pytest.raises(CounselingCaseSourceInvalid):
        open_case(actor=w.a, origin="APPOINTMENT", source_id=unrelated.pk, context=context(w.a))

    mine = record(w.a, w.student)
    with pytest.raises(CounselingCaseSourceInvalid):
        open_case(
            actor=w.a,
            origin="ENCOUNTER",
            source_id=mine.pk,
            student_id=w.other.pk,
            context=context(w.a),
        )
    with pytest.raises(CounselingCaseInvalid):
        open_case(actor=w.a, origin="INTAKE", context=context(w.a))
    with pytest.raises(CounselingCaseInvalid):
        open_case(
            actor=w.a,
            origin="INTAKE",
            student_id=w.student.pk,
            source_id=mine.pk,
            context=context(w.a),
        )
    assert CounselingCase.objects.count() == 0


@pytest.mark.django_db
def test_intake_requires_an_active_student_and_an_eligible_counselor():
    w = world()
    inactive = make_user("inactive-student@example.edu", "STUDENT", active=False)

    for target in (inactive, w.goa, w.b):
        with pytest.raises(CounselingCaseSourceNotFound):
            intake(w.a, target)
    for actor in (w.goa, w.student, w.faculty, w.admin, w.officer):
        with pytest.raises(CounselingCaseNotPermitted):
            intake(actor, w.student)

    w.service.is_active = False
    w.service.save(update_fields=["is_active"])
    with pytest.raises(CounselingCaseSourceInvalid):
        intake(w.a, w.student)
    assert CounselingCase.objects.count() == 0


@pytest.mark.django_db
def test_another_case_for_the_same_student_requires_reviewing_the_active_ones():
    w = world()
    first = intake(w.a, w.student)

    with pytest.raises(CounselingCaseReviewRequired):
        intake(w.a, w.student)
    with pytest.raises(CounselingCaseReviewRequired):
        intake(w.a, w.student, known=[uuid4()])

    second = intake(w.a, w.student, known=[first.pk])
    assert second.pk != first.pk
    assert second.reference_code != first.reference_code
    # Another Counselor's cases are not this Counselor's to review, or to learn about.
    theirs = intake(w.b, w.student)
    assert theirs.primary_counselor_id == w.b.pk
    page = list_my_cases(actor=w.a, status="ACTIVE", student_id=w.student.pk)
    assert {item.case.pk for item in page.items} == {first.pk, second.pk}
    reviewed = get_opening_context(actor=w.a, origin="INTAKE", student_id=w.student.pk)
    assert {item.case.pk for item in reviewed.active_cases} == {first.pk, second.pk}


@pytest.mark.django_db
def test_linking_validates_ownership_student_membership_version_and_status():
    w = world()
    case = intake(w.a, w.student)
    mine = record(w.a, w.student, hours_ago=5)
    other_student = record(w.a, w.other, hours_ago=7)
    theirs = record(w.b, w.student, hours_ago=9)

    with pytest.raises(CounselingCaseChanged):
        link_session(
            actor=w.a,
            case_id=case.pk,
            encounter_id=mine.pk,
            expected_version=case.version + 1,
            context=context(w.a),
        )
    with pytest.raises(CounselingCaseSessionStudentMismatch):
        link(w.a, case, other_student)
    # A matching Student and owning the case are not authority over another Counselor's record.
    with pytest.raises(CounselingCaseSessionNotFound):
        link(w.a, case, theirs)
    with pytest.raises(CounselingCaseNotFound):
        link(w.b, case, theirs)

    link(w.a, case, mine)
    case.refresh_from_db()
    assert case.version == 2
    with pytest.raises(CounselingCaseSessionAlreadyLinked, match="already in this case"):
        link(w.a, case, mine)
    second = intake(w.a, w.student, known=[case.pk])
    with pytest.raises(CounselingCaseSessionAlreadyLinked, match=case.reference_code):
        link(w.a, second, mine)

    audit = AuditEvent.objects.get(action="counseling.case.session_linked")
    assert audit.metadata == {"encounter_id": str(mine.pk)}

    CounselingCase.objects.filter(pk=second.pk).update(status="CLOSED")
    later = record(w.a, w.student, hours_ago=2)
    with pytest.raises(CounselingCaseClosed):
        link(w.a, second, later)
    with pytest.raises(CounselingCaseClosed):
        list_session_candidates(actor=w.a, case_id=second.pk)
    assert get_case(actor=w.a, case_id=second.pk).can_manage is False


@pytest.mark.django_db
def test_the_database_allows_one_current_case_per_session():
    w = world()
    first = intake(w.a, w.student)
    second = intake(w.a, w.student, known=[first.pk])
    session = record(w.a, w.student)
    link(w.a, first, session)

    with pytest.raises(IntegrityError), transaction.atomic():
        CounselingCaseSession.objects.create(case=second, encounter=session, linked_by=w.a)
    with pytest.raises(IntegrityError), transaction.atomic():
        # A removal names who removed it and why, or it is not a removal.
        CounselingCaseSession.objects.filter(encounter=session).update(removed_at=timezone.now())
    with pytest.raises(IntegrityError), transaction.atomic():
        CounselingCase.objects.filter(pk=first.pk).update(primary_counselor=w.student)


@pytest.mark.django_db
def test_a_wrong_link_is_corrected_explicitly_and_keeps_its_history():
    w = world()
    wrong = intake(w.a, w.student)
    right = intake(w.a, w.student, known=[wrong.pk])
    session = record(w.a, w.student)
    link(w.a, wrong, session)
    before = CounselingEncounter.objects.get(pk=session.pk)

    with pytest.raises(CounselingCaseInvalid):
        unlink_session(
            actor=w.a,
            case_id=wrong.pk,
            encounter_id=session.pk,
            reason="",
            expected_version=2,
            context=context(w.a),
        )
    with pytest.raises(CounselingCaseNotFound):
        unlink_session(
            actor=w.b,
            case_id=wrong.pk,
            encounter_id=session.pk,
            reason="LINKED_BY_MISTAKE",
            expected_version=2,
            context=context(w.b),
        )
    unlink_session(
        actor=w.a,
        case_id=wrong.pk,
        encounter_id=session.pk,
        reason="BELONGS_TO_ANOTHER_CASE",
        expected_version=2,
        context=context(w.a),
    )

    removed = CounselingCaseSession.objects.get(case=wrong, encounter=session)
    assert removed.removed_by_id == w.a.pk
    assert removed.removal_reason == "BELONGS_TO_ANOTHER_CASE"
    assert get_case(actor=w.a, case_id=wrong.pk).summary.session_count == 0
    with pytest.raises(CounselingCaseSessionNotFound):
        unlink_session(
            actor=w.a,
            case_id=wrong.pk,
            encounter_id=session.pk,
            reason="LINKED_BY_MISTAKE",
            expected_version=3,
            context=context(w.a),
        )

    # The session moves only through a second deliberate link.
    assert get_case(actor=w.a, case_id=right.pk).summary.session_count == 0
    link(w.a, right, session)
    assert get_case(actor=w.a, case_id=right.pk).summary.session_count == 1
    assert CounselingCaseSession.objects.filter(encounter=session).count() == 2

    after = CounselingEncounter.objects.get(pk=session.pk)
    for field in ("counselor_id", "student_id", "started_at", "ended_at", "updated_at"):
        assert getattr(after, field) == getattr(before, field)
    history = get_case(actor=w.a, case_id=wrong.pk).events
    assert [event.kind for event in history] == ["SESSION_UNLINKED", "SESSION_LINKED", "OPENED"]
    assert history[0].detail_code == "BELONGS_TO_ANOTHER_CASE"
    audit = AuditEvent.objects.get(action="counseling.case.session_unlinked")
    assert audit.metadata == {
        "encounter_id": str(session.pk),
        "reason": "BELONGS_TO_ANOTHER_CASE",
    }


@pytest.mark.django_db
def test_linking_leaves_the_published_student_summary_and_authorship_untouched():
    w = world()
    session = record(w.a, w.student)
    put_assigned_student_session_summary(
        encounter_id=session.pk, counselor=w.a, content="Agreed next steps."
    )
    publish_assigned_student_session_summary(
        encounter_id=session.pk, counselor=w.a, context=context(w.a)
    )
    summary = StudentSessionSummary.objects.get(encounter=session)

    case = open_case(actor=w.a, origin="ENCOUNTER", source_id=session.pk, context=context(w.a))
    unlink_session(
        actor=w.a,
        case_id=case.pk,
        encounter_id=session.pk,
        reason="NOT_PART_OF_THIS_CASE",
        expected_version=1,
        context=context(w.a),
    )

    unchanged = StudentSessionSummary.objects.get(encounter=session)
    assert unchanged.content_ciphertext == summary.content_ciphertext
    assert unchanged.published_at == summary.published_at
    assert [item.pk for item in list_my_student_session_summaries(student=w.student).items] == [
        summary.pk
    ]
    assert CounselingEncounter.objects.get(pk=session.pk).counselor_id == w.a.pk


@pytest.mark.django_db
def test_my_cases_are_filtered_searched_and_ordered_for_their_counselor_only():
    w = world()
    quiet = intake(w.a, w.other)
    busy = intake(w.a, w.student)
    link(w.a, busy, record(w.a, w.student, hours_ago=1))
    intake(w.b, w.student)
    CounselingCase.objects.filter(pk=quiet.pk).update(opened_at=timezone.now() - timedelta(days=3))

    page = list_my_cases(actor=w.a)
    assert page.ordering == "LATEST_ACTIVITY"
    assert [item.case.pk for item in page.items] == [busy.pk, quiet.pk]
    assert [item.session_count for item in page.items] == [1, 0]
    oldest = list_my_cases(actor=w.a, ordering="OLDEST_OPENED")
    assert [item.case.pk for item in oldest.items] == [quiet.pk, busy.pk]
    assert [item.case.pk for item in list_my_cases(actor=w.a, search="2026-0002").items] == [
        quiet.pk
    ]
    assert [
        item.case.pk for item in list_my_cases(actor=w.a, search=busy.reference_code).items
    ] == [busy.pk]
    assert list_my_cases(actor=w.a, status="CLOSED").items == ()
    first = list_my_cases(actor=w.a, page_size=1)
    assert (len(first.items), first.has_next) == (1, True)
    assert list_my_cases(actor=w.head).items == ()
    with pytest.raises(CounselingCaseInvalid):
        list_my_cases(actor=w.a, ordering="student")
    with pytest.raises(CounselingCaseInvalid):
        list_my_cases(actor=w.a, status="PENDING")


@pytest.mark.django_db
def test_api_opens_reviews_links_and_corrects_a_case():
    w = world()
    session = record(w.a, w.student, hours_ago=4)
    later = record(w.a, w.student, hours_ago=2)
    client = auth_client(w.a)

    reviewed = client.get(f"{CASES}/opening-context?origin=ENCOUNTER&source_id={session.pk}")
    assert reviewed.status_code == 200
    assert reviewed.json()["active_cases"] == []
    assert reviewed.json()["session"]["encounter_id"] == str(session.pk)
    assert reviewed.json()["student"]["institutional_id"] == "2026-0001"

    opened = post(client, CASES, {"origin": "ENCOUNTER", "source_id": str(session.pk)})
    assert opened.status_code == 201
    case = opened.json()
    assert case["status"] == "ACTIVE"
    assert case["primary_counselor"]["id"] == str(w.a.pk)
    assert case["session_count"] == 1
    assert case["sessions"][0]["counselor"]["id"] == str(w.a.pk)
    assert case["sessions"][0]["record_accessible"] is True
    assert case["source"]["encounter_id"] == str(session.pk)
    assert case["can_manage"] is True
    assert [event["kind"] for event in case["history"]] == ["SESSION_LINKED", "OPENED"]

    blocked = post(client, CASES, {"origin": "INTAKE", "student_id": str(w.student.pk)})
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "counseling_case_review_required"
    reviewed = client.get(f"{CASES}/opening-context?origin=INTAKE&student_id={w.student.pk}")
    assert [item["id"] for item in reviewed.json()["active_cases"]] == [case["id"]]

    candidates = client.get(f"{CASES}/{case['id']}/session-candidates")
    assert [item["encounter_id"] for item in candidates.json()["items"]] == [str(later.pk)]
    stale = post(
        client,
        f"{CASES}/{case['id']}/sessions",
        {"encounter_id": str(later.pk), "expected_version": 9},
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "counseling_case_changed"
    linked = post(
        client,
        f"{CASES}/{case['id']}/sessions",
        {"encounter_id": str(later.pk), "expected_version": case["version"]},
    )
    assert linked.status_code == 200
    assert linked.json()["session_count"] == 2
    assert linked.json()["sessions"][0]["encounter_id"] == str(later.pk)

    corrected = post(
        client,
        f"{CASES}/{case['id']}/sessions/{later.pk}/unlink",
        {"reason": "LINKED_BY_MISTAKE", "expected_version": linked.json()["version"]},
    )
    assert corrected.status_code == 200
    assert corrected.json()["session_count"] == 1
    assert corrected.json()["history"][0]["detail_code"] == "LINKED_BY_MISTAKE"
    invalid = post(
        client,
        f"{CASES}/{case['id']}/sessions/{session.pk}/unlink",
        {"reason": "BECAUSE", "expected_version": corrected.json()["version"]},
    )
    assert invalid.status_code == 422

    listing = client.get(f"{CASES}?status=ACTIVE&search=2026-0001")
    assert listing.status_code == 200
    assert [item["id"] for item in listing.json()["items"]] == [case["id"]]
    assert listing.json()["ordering"] == "LATEST_ACTIVITY"
    # No endpoint here closes, reopens or reassigns a case.
    assert (
        client.patch(
            f"{CASES}/{case['id']}", data="{}", content_type="application/json", **csrf(client)
        ).status_code
        == 405
    )


@pytest.mark.django_db
def test_api_denies_every_audience_except_the_primary_counselor():
    w = world()
    session = record(w.a, w.student)
    case = open_case(actor=w.a, origin="ENCOUNTER", source_id=session.pk, context=context(w.a))
    detail = f"{CASES}/{case.pk}"

    from django.test import Client

    assert Client().get(detail).status_code == 401
    for user in (w.goa, w.student, w.faculty, w.admin, w.officer):
        client = auth_client(user)
        for response in (
            client.get(CASES),
            client.get(detail),
            client.get(f"{detail}/session-candidates"),
            client.get(f"{CASES}/opening-context?origin=INTAKE&student_id={w.student.pk}"),
            post(client, CASES, {"origin": "INTAKE", "student_id": str(w.student.pk)}),
            post(
                client,
                f"{detail}/sessions",
                {"encounter_id": str(session.pk), "expected_version": 1},
            ),
            post(
                client,
                f"{detail}/sessions/{session.pk}/unlink",
                {"reason": "LINKED_BY_MISTAKE", "expected_version": 1},
            ),
        ):
            assert response.status_code == 403, (user.email, response.content)
            assert "CASE-" not in response.content.decode()

    # A Head designation, a guessed identifier and being a Counselor are not case access.
    for user in (w.head, w.b):
        client = auth_client(user)
        assert client.get(detail).status_code == 404
        assert client.get(f"{detail}/session-candidates").status_code == 404
        assert client.get(CASES).json()["items"] == []
        guessed = post(
            client,
            f"{detail}/sessions/{session.pk}/unlink",
            {"reason": "LINKED_BY_MISTAKE", "expected_version": 1},
        )
        assert guessed.status_code == 404
        assert guessed.json()["error"]["code"] == "counseling_case_not_found"
        foreign = client.get(f"{CASES}/opening-context?origin=ENCOUNTER&source_id={session.pk}")
        assert foreign.status_code == 404

    UserCapabilityOverride.objects.create(
        user=w.a,
        capability=Capability.objects.get(code="counseling.manage_assigned"),
        effect="REVOKE",
        reason="temporary separation",
    )
    client = auth_client(w.a)
    assert client.get(detail).status_code == 200
    assert client.get(detail).json()["can_manage"] is False
    assert (
        post(client, CASES, {"origin": "INTAKE", "student_id": str(w.other.pk)}).status_code == 403
    )
    UserCapabilityOverride.objects.create(
        user=w.a,
        capability=Capability.objects.get(code="counseling.view_assigned"),
        effect="REVOKE",
        reason="temporary separation",
    )
    assert auth_client(w.a).get(detail).status_code == 403
    assert CounselingCaseSession.objects.filter(removed_at__isnull=True).count() == 1


@pytest.mark.django_db
def test_holding_a_case_never_opens_another_counselors_session_record():
    """Responsibility for a case and access to a linked record are separate facts.

    CW-1 has no transfer, so the later state is built directly: Counselor B becomes responsible for
    a case that contains Counselor A's session.
    """

    w = world()
    appointment = make_appointment(
        student=w.student, provider=w.a, service=w.service, status=AppointmentStatus.COMPLETED
    )
    session = record(w.a, w.student, appointment=appointment)
    put_assigned_student_session_summary(
        encounter_id=session.pk, counselor=w.a, content="Private summary."
    )
    case = open_case(actor=w.a, origin="ENCOUNTER", source_id=session.pk, context=context(w.a))
    CounselingCase.objects.filter(pk=case.pk).update(primary_counselor=w.b)

    holder = auth_client(w.b)
    detail = holder.get(f"{CASES}/{case.pk}")
    assert detail.status_code == 200
    projected = detail.json()["sessions"][0]
    assert projected["record_accessible"] is False
    assert projected["appointment"] is None
    assert projected["counselor"]["id"] == str(w.a.pk)
    assert detail.json()["source"] == {
        "appointment": None,
        "encounter_id": None,
        "routine_interview_id": None,
    }
    assert appointment.reference_code not in detail.content.decode()
    assert "Private summary" not in detail.content.decode()
    assert holder.get(f"/api/v1/counseling/encounters/{session.pk}").status_code == 404
    assert (
        holder.get(
            f"/api/v1/counseling/encounters/{session.pk}/student-session-summary"
        ).status_code
        == 404
    )
    assert holder.get("/api/v1/counseling/me/encounters").json()["items"] == []
    # The holder can't pull in more of the author's records either.
    more = record(w.a, w.student, hours_ago=1)
    assert holder.get(f"{CASES}/{case.pk}/session-candidates").json()["items"] == []
    refused = post(
        holder,
        f"{CASES}/{case.pk}/sessions",
        {"encounter_id": str(more.pk), "expected_version": case.version},
    )
    assert refused.status_code == 404
    assert refused.json()["error"]["code"] == "counseling_case_session_not_found"

    # The author keeps their record and learns only that it is in a case they can't open.
    author = auth_client(w.a)
    own = author.get(f"/api/v1/counseling/encounters/{session.pk}").json()
    assert (own["in_case"], own["case"]) == (True, None)
    assert author.get(f"{CASES}/{case.pk}").status_code == 404


@pytest.mark.django_db
def test_session_records_report_and_filter_their_case_membership():
    w = world()
    linked = record(w.a, w.student, hours_ago=5)
    loose = record(w.a, w.student, hours_ago=3)
    case = open_case(actor=w.a, origin="ENCOUNTER", source_id=linked.pk, context=context(w.a))
    client = auth_client(w.a)

    rows = {
        item["id"]: item for item in client.get("/api/v1/counseling/me/encounters").json()["items"]
    }
    assert rows[str(linked.pk)]["in_case"] is True
    assert rows[str(linked.pk)]["case"] == {
        "id": str(case.pk),
        "reference_code": case.reference_code,
        "status": "ACTIVE",
    }
    assert (rows[str(loose.pk)]["in_case"], rows[str(loose.pk)]["case"]) == (False, None)
    for value, expected in (("LINKED", linked), ("UNLINKED", loose)):
        page = client.get(f"/api/v1/counseling/me/encounters?case_link={value}").json()
        assert [item["id"] for item in page["items"]] == [str(expected.pk)]
    assert client.get("/api/v1/counseling/me/encounters?case_link=ALL").status_code == 422
    assert client.get(f"/api/v1/counseling/encounters/{loose.pk}").json()["in_case"] is False


@pytest.mark.django_db
def test_recording_from_a_case_links_the_session_or_records_nothing():
    w = world()
    case = intake(w.a, w.student)
    theirs = intake(w.b, w.student)
    client = auth_client(w.a)
    end = timezone.now() - timedelta(minutes=10)

    def body(**changes):
        return {
            "entry_mode": "WALK_IN",
            "student_id": str(w.student.pk),
            "delivery_mode": "IN_PERSON",
            "started_at": (end - timedelta(minutes=45)).isoformat(),
            "ended_at": end.isoformat(),
            "case_id": str(case.pk),
            **changes,
        }

    mismatch = post(client, "/api/v1/counseling/encounters", body(student_id=str(w.other.pk)))
    assert mismatch.status_code == 409
    assert mismatch.json()["error"]["code"] == "counseling_case_session_student_mismatch"
    foreign = post(client, "/api/v1/counseling/encounters", body(case_id=str(theirs.pk)))
    assert foreign.status_code == 404
    assert foreign.json()["error"]["code"] == "counseling_case_not_found"
    assert CounselingEncounter.objects.count() == 0

    created = post(client, "/api/v1/counseling/encounters", body())
    assert created.status_code == 201
    assert created.json()["case"]["id"] == str(case.pk)
    overview = get_case(actor=w.a, case_id=case.pk)
    assert overview.summary.session_count == 1
    assert overview.summary.case.version == 2

    independent = post(client, "/api/v1/counseling/encounters", body(case_id=None))
    assert independent.status_code == 201
    assert independent.json()["in_case"] is False
    assert get_case(actor=w.a, case_id=case.pk).summary.session_count == 1
