"""CW-2 explicit Appointment membership, current schedule facts and concurrency."""

from datetime import timedelta
from uuid import uuid4

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from compass.appointments.models import Appointment
from compass.counseling.case_appointment_services import (
    CounselingCaseAppointmentAlreadyLinked,
    CounselingCaseAppointmentInvalid,
    CounselingCaseAppointmentNotFound,
    link_appointment,
    list_appointment_candidates,
    unlink_appointment,
)
from compass.counseling.case_models import CounselingCaseAppointment, CounselingCaseEvent
from compass.counseling.case_services import (
    CounselingCaseChanged,
    CounselingCaseInvalid,
    get_case,
    open_case,
)
from compass.service_catalog.models import Service
from tests.test_counseling import auth_client, context, make_appointment
from tests.test_counseling_cases import intake, link, post, record, world
from tests.test_counseling_cases_concurrency import fresh, race, split


@pytest.fixture
def cw2():
    w = world("cw2-appointment")
    w.case = intake(w.a, w.student)
    return w


def appointment(w, *, days=2, **kwargs):
    row = make_appointment(
        student=kwargs.pop("student", w.student),
        provider=kwargs.pop("provider", w.a),
        service=kwargs.pop("service", w.service),
        **kwargs,
    )
    start = timezone.now() + timedelta(days=days)
    Appointment.objects.filter(pk=row.pk).update(
        starts_at=start, ends_at=start + timedelta(hours=1)
    )
    row.refresh_from_db()
    return row


def add(w, row, case=None):
    case = case or w.case
    case.refresh_from_db()
    return link_appointment(
        actor=w.a,
        case_id=case.pk,
        appointment_id=row.pk,
        expected_version=case.version,
        context=context(w.a),
    )


def remove(w, row, reason="LINKED_BY_MISTAKE"):
    w.case.refresh_from_db()
    return unlink_appointment(
        actor=w.a,
        case_id=w.case.pk,
        appointment_id=row.pk,
        expected_version=w.case.version,
        reason=reason,
        context=context(w.a),
    )


@pytest.mark.django_db
def test_link_and_unlink_bump_case_keep_history_and_never_change_appointment(cw2):
    w = cw2
    row = appointment(w)
    before = Appointment.objects.filter(pk=row.pk).values().get()
    add(w, row)
    assert w.case.appointment_links.count() == 1
    w.case.refresh_from_db()
    assert w.case.version == 2
    assert get_case(actor=w.a, case_id=w.case.pk).next_appointment.pk == row.pk
    remove(w, row)
    saved = CounselingCaseAppointment.objects.get(appointment=row)
    assert saved.removed_at and saved.removed_by_id == w.a.pk
    assert saved.removal_reason == "LINKED_BY_MISTAKE"
    w.case.refresh_from_db()
    assert w.case.version == 3
    assert get_case(actor=w.a, case_id=w.case.pk).next_appointment is None
    assert Appointment.objects.filter(pk=row.pk).values().get() == before
    assert list(CounselingCaseEvent.objects.values_list("kind", flat=True)) == ["OPENED"]
    add(w, row)
    assert CounselingCaseAppointment.objects.filter(appointment=row).count() == 2


@pytest.mark.django_db
@pytest.mark.parametrize(
    "change,error",
    [
        ({"student": "other"}, CounselingCaseAppointmentInvalid),
        ({"provider": "b"}, CounselingCaseAppointmentNotFound),
        ({"status": "CANCELLED"}, CounselingCaseAppointmentInvalid),
        ({"status": "NO_SHOW"}, CounselingCaseAppointmentInvalid),
        ({"status": "COMPLETED"}, CounselingCaseAppointmentInvalid),
        ({"service": "other"}, CounselingCaseAppointmentInvalid),
    ],
)
def test_link_eligibility(cw2, change, error):
    w = cw2
    values = dict(change)
    for name in ("student", "provider"):
        if name in values:
            values[name] = getattr(w, values[name])
    if "service" in values:
        values["service"] = Service.objects.create(code="CW2_OTHER", name="Other service")
    row = appointment(w, **values)
    with pytest.raises(error):
        add(w, row)
    assert not CounselingCaseAppointment.objects.exists()


@pytest.mark.django_db
def test_one_current_case_per_appointment_and_stale_versions(cw2):
    w = cw2
    row = appointment(w)
    second = intake(w.a, w.student, known=[w.case.pk])
    add(w, row)
    with pytest.raises(CounselingCaseAppointmentAlreadyLinked):
        add(w, row, second)
    with pytest.raises(IntegrityError), transaction.atomic():
        CounselingCaseAppointment.objects.create(case=second, appointment=row, linked_by=w.a)
    with pytest.raises(CounselingCaseChanged):
        unlink_appointment(
            actor=w.a,
            case_id=w.case.pk,
            appointment_id=row.pk,
            expected_version=1,
            reason="LINKED_BY_MISTAKE",
            context=context(w.a),
        )
    with pytest.raises(CounselingCaseInvalid):
        remove(w, row, reason="Free text is not a reason code")
    assert CounselingCaseAppointment.objects.get().removed_at is None


@pytest.mark.django_db
def test_opening_from_scheduled_appointment_links_it_atomically(cw2):
    w = cw2
    row = appointment(w)
    case = open_case(
        actor=w.a,
        origin="APPOINTMENT",
        source_id=row.pk,
        known_active_case_ids=[w.case.pk],
        context=context(w.a),
    )
    membership = CounselingCaseAppointment.objects.get(appointment=row)
    assert membership.case_id == case.pk and membership.linked_by_id == w.a.pk
    assert case.version == 2
    assert get_case(actor=w.a, case_id=case.pk).next_appointment.pk == row.pk
    with pytest.raises(CounselingCaseAppointmentAlreadyLinked):
        open_case(
            actor=w.a,
            origin="APPOINTMENT",
            source_id=row.pk,
            known_active_case_ids=[w.case.pk, case.pk],
            context=context(w.a),
        )
    assert w.a.primary_counseling_cases.count() == 2


@pytest.mark.django_db
@pytest.mark.parametrize("status", ["CANCELLED", "NO_SHOW", "COMPLETED"])
def test_next_appointment_ignores_every_terminal_status(cw2, status):
    w = cw2
    first, second = appointment(w, days=1), appointment(w, days=3)
    add(w, second)
    add(w, first)
    assert get_case(actor=w.a, case_id=w.case.pk).next_appointment.pk == first.pk
    stamp = {"CANCELLED": "cancelled_at", "NO_SHOW": "no_show_at", "COMPLETED": "completed_at"}[
        status
    ]
    Appointment.objects.filter(pk=first.pk).update(status=status, **{stamp: timezone.now()})
    assert get_case(actor=w.a, case_id=w.case.pk).next_appointment.pk == second.pk
    remove(w, second)
    assert get_case(actor=w.a, case_id=w.case.pk).next_appointment is None


@pytest.mark.django_db
def test_next_appointment_uses_current_time_provider_and_membership(cw2):
    w = cw2
    row = appointment(w)
    add(w, row)
    assert get_case(actor=w.a, case_id=w.case.pk, now=row.starts_at).next_appointment is None
    earlier = row.starts_at - timedelta(seconds=1)
    assert get_case(actor=w.a, case_id=w.case.pk, now=earlier).next_appointment.pk == row.pk
    past = timezone.now() - timedelta(days=2)
    Appointment.objects.filter(pk=row.pk).update(starts_at=past, ends_at=past + timedelta(hours=1))
    assert get_case(actor=w.a, case_id=w.case.pk).next_appointment is None
    future = timezone.now() + timedelta(days=5)
    Appointment.objects.filter(pk=row.pk).update(
        starts_at=future,
        ends_at=future + timedelta(hours=1),
        provider=w.b,
    )
    next_appointment = get_case(actor=w.a, case_id=w.case.pk).next_appointment
    assert next_appointment.pk == row.pk
    assert next_appointment.provider_id == w.b.pk
    detail = auth_client(w.a).get(f"/api/v1/counseling/cases/{w.case.pk}").json()
    assert detail["appointments"][0]["appointment"]["provider"]["id"] == str(w.b.pk)
    assert detail["appointments"][0]["appointment"]["record_accessible"] is False
    # The original case owner can correct a link after eligibility changes.
    remove(w, row)


@pytest.mark.django_db
def test_recorded_session_from_any_linked_appointment_is_offered_for_explicit_link(cw2):
    w = cw2
    row = appointment(w, days=-2)
    add(w, row)
    session = record(w.a, w.student, hours_ago=2, appointment=row)
    before = get_case(actor=w.a, case_id=w.case.pk)
    assert before.summary.session_count == 0
    assert [item.pk for item in before.unlinked_appointment_sessions] == [session.pk]
    assert not w.case.session_links.exists()
    link(w.a, w.case, session)
    after = get_case(actor=w.a, case_id=w.case.pk)
    assert after.summary.session_count == 1 and after.unlinked_appointment_sessions == ()


@pytest.mark.django_db
def test_candidates_and_http_links_are_authorized_and_keep_paging(cw2):
    w = cw2
    first, second = appointment(w, days=1), appointment(w, days=4)
    appointment(w, student=w.other)
    appointment(w, provider=w.b)
    appointment(w, status="CANCELLED")
    page = list_appointment_candidates(actor=w.a, case_id=w.case.pk, page_size=1)
    assert [item.pk for item in page.items] == [first.pk] and page.has_next
    assert (
        list_appointment_candidates(actor=w.a, case_id=w.case.pk, page=2, page_size=1).items[0].pk
        == second.pk
    )
    base = f"/api/v1/counseling/cases/{w.case.pk}"
    client = auth_client(w.a)
    response = post(
        client, base + "/appointments", {"appointment_id": str(first.pk), "expected_version": 1}
    )
    assert response.status_code == 200 and response.json()["next_appointment"]["id"] == str(
        first.pk
    )
    stale = post(
        client, base + "/appointments", {"appointment_id": str(second.pk), "expected_version": 1}
    )
    assert stale.status_code == 409
    response = post(
        client,
        base + f"/appointments/{first.pk}/unlink",
        {"reason": "LINKED_BY_MISTAKE", "expected_version": 2},
    )
    assert response.status_code == 200 and response.json()["appointments"][0]["removed_at"]
    guessed = post(
        client,
        base + f"/appointments/{uuid4()}/unlink",
        {"reason": "LINKED_BY_MISTAKE", "expected_version": 3},
    )
    assert guessed.status_code == 404
    for actor in (w.b, w.head, w.goa, w.faculty, w.student, w.admin):
        other = auth_client(actor)
        assert other.get(base + "/appointment-candidates").status_code in (403, 404)
        denied = post(
            other, base + "/appointments", {"appointment_id": str(second.pk), "expected_version": 3}
        )
        assert denied.status_code in (403, 404)


@pytest.mark.django_db(transaction=True)
def test_two_cases_concurrently_linking_one_appointment_leave_one_membership():
    w = world("cw2-appointment-race")
    first = intake(w.a, w.student)
    second = intake(w.a, w.student, known=[first.pk])
    row = appointment(w)

    def attempt(case_id):
        def call():
            actor = fresh(w.a.pk)
            return link_appointment(
                actor=actor,
                case_id=case_id,
                appointment_id=row.pk,
                expected_version=1,
                context=context(actor),
            )

        return call

    linked, refused = split(
        race(attempt(first.pk), attempt(second.pk)), CounselingCaseAppointmentAlreadyLinked
    )
    assert (len(linked), len(refused)) == (1, 1)
    assert CounselingCaseAppointment.objects.count() == 1
