"""Faculty progress and published Student records remain independent of case lifecycle."""

import json

import pytest
from cryptography.fernet import Fernet

from compass.counseling import case_closure_services as closure
from compass.counseling.case_services import open_case
from compass.counseling.models import CounselingEncounter, StudentSessionSummary
from compass.counseling.student_session_summaries import (
    publish_assigned_student_session_summary,
    put_assigned_student_session_summary,
)
from compass.referrals import faculty_services
from compass.referrals.models import Referral
from tests.faculty_referral_helpers import submit
from tests.referral_administration_helpers import make_world, transition
from tests.test_appointment_management_scope import auth_client
from tests.test_counseling import context, create_counseling_service
from tests.test_counseling_cases import record

pytestmark = pytest.mark.django_db


def test_faculty_and_student_http_payloads_are_identical_through_closure_and_reopening(
    monkeypatch, settings
):
    settings.COUNSELOR_HANDOFF_SUMMARY_ENCRYPTION_KEYS = (Fernet.generate_key().decode(),)
    w = make_world(monkeypatch)
    create_counseling_service(w.admin)
    submitted, _ = submit(w)
    referral = Referral.objects.get(pk=submitted["id"])
    session = record(w.counselor, w.student)
    put_assigned_student_session_summary(
        encounter_id=session.pk, counselor=w.counselor, content="Student-facing agreed steps."
    )
    publish_assigned_student_session_summary(
        encounter_id=session.pk, counselor=w.counselor, context=context(w.counselor)
    )
    case = open_case(
        actor=w.counselor, origin="ENCOUNTER", source_id=session.pk, context=context(w.counselor)
    )
    student_client = auth_client(w.student)
    student_path = "/api/v1/counseling/me/student-session-summaries"
    before = student_client.get(student_path)
    assert before.status_code == 200, before.content
    before = before.json()
    faculty_before = faculty_services.get_own_submission(
        actor=w.faculty, actor_session=w.issued.session, referral_id=referral.pk
    )
    original = (
        referral.administrative_version,
        referral.received_at,
        referral.administratively_closed_at,
    )
    summary = StudentSessionSummary.objects.get(encounter=session)
    closure.close_case(
        actor=w.counselor,
        case_id=case.pk,
        expected_version=case.version,
        reason="CONTACT_NOT_REESTABLISHED",
        outcome="NOT_ASSESSED",
        note="Documented contact attempts remained unanswered.",
        context=context(w.counselor),
    )
    assert student_client.get(student_path).json() == before
    faculty_after = faculty_services.get_own_submission(
        actor=w.faculty, actor_session=w.issued.session, referral_id=referral.pk
    )
    assert faculty_after == faculty_before
    assert set(faculty_after) == {
        "id",
        "reference_code",
        "submitted_at",
        "state",
        "student",
        "received_at",
        "closed_at",
        # CW-5: the Faculty member's own immutable scheduling statement and its timing status.
        "scheduling_statement",
        "timing_status",
    }
    assert not any(
        text in json.dumps(faculty_after, default=str)
        for text in (
            "CONTACT_NOT_REESTABLISHED",
            "NOT_ASSESSED",
            "Documented contact",
            "case_status",
            "session_count",
            "tasks",
        )
    )
    referral.refresh_from_db()
    assert original == (
        referral.administrative_version,
        referral.received_at,
        referral.administratively_closed_at,
    )
    summary.refresh_from_db()
    assert summary.published_at and summary.encounter.counselor_id == w.counselor.pk
    assert CounselingEncounter.objects.filter(pk=session.pk).count() == 1
    case.refresh_from_db()
    closure.reopen_case(
        actor=w.counselor,
        case_id=case.pk,
        expected_version=case.version,
        reason="SAME_CONCERN_RETURNED",
        context=context(w.counselor),
    )
    assert student_client.get(student_path).json() == before
    assert (
        faculty_services.get_own_submission(
            actor=w.faculty, actor_session=w.issued.session, referral_id=referral.pk
        )
        == faculty_before
    )
    transition(w, referral.pk)
    transition(w, referral.pk, close=True)
    case.refresh_from_db()
    assert case.status == "ACTIVE"
