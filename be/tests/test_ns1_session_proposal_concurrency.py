"""NS-1 accepts under real concurrency: at most one Appointment, clean refusals."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.test import override_settings

from compass.appointments.models import Appointment
from compass.appointments.services import create_student_appointment
from compass.counseling.session_proposal_models import CounselingSessionProposal
from compass.counseling.session_proposal_services import (
    SessionProposalClosed,
    SessionProposalError,
    SessionProposalTimeUnavailable,
    accept_proposal,
)
from tests.test_appointments import configure_availability, future_local_start
from tests.test_counseling import context
from tests.test_counseling_cases_concurrency import fresh, race, split
from tests.test_cw3_transfers import transfer_world
from tests.test_ns1_session_proposals import propose


@pytest.fixture
def ns(settings):
    with override_settings(TIME_ZONE="Asia/Manila"):
        w = transfer_world(settings, "ns1-race")
        configure_availability(w.admin, w.a)
        w.start = future_local_start(hour=10)
        yield w


def _accept(w, proposal_id, option_id):
    def call():
        student = fresh(w.student.pk)
        return accept_proposal(
            actor=student,
            proposal_id=proposal_id,
            option_id=option_id,
            expected_version=1,
            context=context(student),
        )

    return call


@pytest.mark.django_db(transaction=True)
def test_two_concurrent_accepts_create_exactly_one_appointment(ns):
    w = ns
    proposal = propose(w, starts=[w.start, w.start + timedelta(hours=2)])
    first, second = proposal.options.order_by("position")
    accepted, refused = split(
        race(_accept(w, proposal.pk, first.pk), _accept(w, proposal.pk, second.pk)),
        SessionProposalClosed,
    )
    assert (len(accepted), len(refused)) == (1, 1)
    assert Appointment.objects.filter(student=w.student).count() == 1
    saved = CounselingSessionProposal.objects.get(pk=proposal.pk)
    assert saved.state == "ACCEPTED" and saved.appointment_id is not None


@pytest.mark.django_db(transaction=True)
def test_accept_racing_another_booking_of_the_same_time_books_once(ns):
    w = ns
    proposal = propose(w, starts=[w.start])
    chosen = proposal.options.get()

    def other_booking():
        student = fresh(w.other.pk)
        return create_student_appointment(
            student=student,
            service_id=proposal.service_id,
            provider_id=w.a.pk,
            delivery_mode="IN_PERSON",
            starts_at=w.start,
            context=context(student),
        )

    outcomes = race(_accept(w, proposal.pk, chosen.pk), other_booking)
    failures = [item for item in outcomes if isinstance(item, Exception)]
    assert len(failures) == 1, outcomes
    assert isinstance(failures[0], (SessionProposalTimeUnavailable, Exception))
    assert Appointment.objects.filter(provider=w.a, starts_at=w.start).count() == 1
    saved = CounselingSessionProposal.objects.get(pk=proposal.pk)
    if isinstance(failures[0], SessionProposalError):
        assert saved.state == "PENDING" and saved.appointment_id is None
    else:
        assert saved.state == "ACCEPTED"
