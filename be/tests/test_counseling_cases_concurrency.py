"""CW-1 Counseling cases under concurrent requests: invariants hold and failures are clean."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from django.db import close_old_connections, connection

from compass.accounts.models import User
from compass.counseling.case_models import CounselingCase, CounselingCaseSession
from compass.counseling.case_services import (
    CounselingCaseChanged,
    CounselingCaseReviewRequired,
    CounselingCaseSessionAlreadyLinked,
    link_session,
    open_case,
)
from tests.test_counseling import context
from tests.test_counseling_cases import intake, record, world


def race(*calls):
    """Run each call in its own thread and connection, released together."""

    barrier = threading.Barrier(len(calls))

    def worker(call):
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            try:
                return call()
            except Exception as exc:
                return exc
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=len(calls)) as executor:
        futures = [executor.submit(worker, call) for call in calls]
        return [future.result(timeout=30) for future in futures]


def fresh(user_id):
    return User.objects.select_related("role").get(pk=user_id)


def split(outcomes, error):
    failures = [item for item in outcomes if isinstance(item, Exception)]
    assert all(isinstance(item, error) for item in failures), outcomes
    return [item for item in outcomes if not isinstance(item, Exception)], failures


@pytest.mark.django_db(transaction=True)
def test_two_unreviewed_openings_for_one_student_create_one_case():
    w = world("race-open")

    def attempt():
        actor = fresh(w.a.pk)
        return open_case(
            actor=actor, origin="INTAKE", student_id=w.student.pk, context=context(actor)
        )

    created, refused = split(race(attempt, attempt), CounselingCaseReviewRequired)

    assert (len(created), len(refused)) == (1, 1)
    assert CounselingCase.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_one_session_linked_to_two_cases_at_once_joins_exactly_one():
    w = world("race-link")
    first = intake(w.a, w.student)
    second = intake(w.a, w.student, known=[first.pk])
    session = record(w.a, w.student)

    def attempt(case_id):
        def call():
            actor = fresh(w.a.pk)
            return link_session(
                actor=actor,
                case_id=case_id,
                encounter_id=session.pk,
                expected_version=1,
                context=context(actor),
            )

        return call

    linked, refused = split(
        race(attempt(first.pk), attempt(second.pk)), CounselingCaseSessionAlreadyLinked
    )

    assert (len(linked), len(refused)) == (1, 1)
    assert CounselingCaseSession.objects.filter(removed_at__isnull=True).count() == 1
    assert CounselingCaseSession.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_two_changes_from_the_same_version_apply_one_and_report_the_other_as_stale():
    w = world("race-version")
    case = intake(w.a, w.student)
    sessions = [record(w.a, w.student, hours_ago=hours) for hours in (5, 3)]

    def attempt(encounter_id):
        def call():
            actor = fresh(w.a.pk)
            return link_session(
                actor=actor,
                case_id=case.pk,
                encounter_id=encounter_id,
                expected_version=1,
                context=context(actor),
            )

        return call

    linked, stale = split(
        race(attempt(sessions[0].pk), attempt(sessions[1].pk)), CounselingCaseChanged
    )

    assert (len(linked), len(stale)) == (1, 1)
    case.refresh_from_db()
    assert case.version == 2
    assert CounselingCaseSession.objects.filter(case=case, removed_at__isnull=True).count() == 1


@pytest.mark.django_db(transaction=True)
def test_opening_from_a_session_races_a_link_of_the_same_session():
    w = world("race-open-link")
    existing = intake(w.a, w.student)
    session = record(w.a, w.student)

    def open_from_session():
        actor = fresh(w.a.pk)
        return open_case(
            actor=actor,
            origin="ENCOUNTER",
            source_id=session.pk,
            known_active_case_ids=[existing.pk],
            context=context(actor),
        )

    def link_existing():
        actor = fresh(w.a.pk)
        return link_session(
            actor=actor,
            case_id=existing.pk,
            encounter_id=session.pk,
            expected_version=1,
            context=context(actor),
        )

    done, refused = split(
        race(open_from_session, link_existing), CounselingCaseSessionAlreadyLinked
    )

    assert (len(done), len(refused)) == (1, 1)
    assert CounselingCaseSession.objects.filter(removed_at__isnull=True).count() == 1
    # A refused opening leaves no empty case behind.
    assert (
        CounselingCase.objects.count()
        == 1 + CounselingCaseSession.objects.filter(case__origin="ENCOUNTER").count()
    )
