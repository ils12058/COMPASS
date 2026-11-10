"""Case coordination authority within active grants."""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest
from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext

from compass.counseling.case_communication import (
    authorize_case_coordination,
    visible_case_coordination_grant_ids,
)
from compass.counseling.continuity_models import CounselorCaseContinuityGrant as Grant
from compass.counseling.continuity_models import CounselorCaseContinuityScope as Scope
from compass.counseling.continuity_rules import ContinuityError
from compass.student_academics.models import StudentAcademicProfile
from tests.case_communication_helpers import (  # noqa: F401
    PURPOSE,
    additional_student,
    case,
    communication,
    expire,
    live_case_grant,
    request_case_grant,
    revoke,
)
from tests.test_continuity import request

# Imported fixtures are passed into tests below.
# ruff: noqa: F811
pytestmark = pytest.mark.django_db(transaction=True)


def expect(code):
    return pytest.raises(ContinuityError, match=rf"\({code}\)")


def test_case_coordination_purpose_requests(case):
    assert request_case_grant(case)["communication_purpose"] == PURPOSE


def test_grant_records_the_case_coordination_purpose(communication):
    grant = live_case_grant(communication)
    row = Grant.objects.get(pk=grant["id"])
    assert row.communication_purpose == PURPOSE
    assert grant["communication_purpose"] == PURPOSE


def test_purpose_request_requires_a_distinct_original_counselor(communication):
    with expect("invalid_original_counselor"):
        request_case_grant(communication, original_counselor_id=None)
    with expect("invalid_original_counselor"):
        request_case_grant(communication, original_counselor_id=communication.receiver.pk)


def test_unknown_purpose_is_rejected(communication):
    with expect("invalid_purpose"):
        request_case_grant(communication, communication_purpose="SYNTHETIC")


def test_only_the_exact_pair_is_authorized(communication):
    case = communication
    grant = live_case_grant(case)
    for actor in (case.author, case.receiver):
        assert authorize_case_coordination(actor=actor, grant_id=grant["id"]).pk == grant["id"]
    for actor in (case.head, case.outsider, case.student):
        with expect("not_found"):
            authorize_case_coordination(actor=actor, grant_id=grant["id"])


def test_inactive_or_missing_actor_is_not_found(communication):
    case = communication
    grant = live_case_grant(case)
    case.receiver.is_active = False
    case.receiver.save(update_fields=["is_active"])
    for actor in (case.receiver, None):
        with expect("not_found"):
            authorize_case_coordination(actor=actor, grant_id=grant["id"])


def test_unknown_grant_is_not_found(communication):
    with expect("not_found"):
        authorize_case_coordination(actor=communication.author, grant_id=uuid4())


def test_metadata_only_grant_never_authorizes_case_messaging(case):
    metadata_only = request(case, request_id=uuid4())
    assert metadata_only["communication_purpose"] is None
    for actor in (case.author, case.receiver):
        with expect("not_found"):
            authorize_case_coordination(actor=actor, grant_id=metadata_only["id"])


def test_window_boundaries_are_exact(communication):
    case = communication
    grant = live_case_grant(case)
    row = Grant.objects.get(pk=grant["id"])
    assert authorize_case_coordination(actor=case.author, grant_id=row.pk, now=row.starts_at)
    assert authorize_case_coordination(
        actor=case.receiver,
        grant_id=row.pk,
        now=row.expires_at - timedelta(microseconds=1),
    )
    with expect("not_found"):
        authorize_case_coordination(
            actor=case.author, grant_id=row.pk, now=row.starts_at - timedelta(microseconds=1)
        )
    with expect("case_access_ended"):
        authorize_case_coordination(actor=case.author, grant_id=row.pk, now=row.expires_at)


def test_revocation_and_expiry_end_access_for_both_participants(communication):
    case = communication
    revoked = live_case_grant(case)
    revoke(case, revoked)
    other = additional_student(case)
    expired = live_case_grant(case, student_id=other.student.pk, scopes=other.scopes)
    expire(expired)
    for grant in (revoked, expired):
        for actor in (case.author, case.receiver):
            with expect("case_access_ended"):
                authorize_case_coordination(actor=actor, grant_id=grant["id"])


def test_student_placement_change_ends_coordination(communication):
    case = communication
    grant = live_case_grant(case)
    StudentAcademicProfile.objects.filter(student=case.student).update(
        current_college=case.college_b
    )
    with expect("case_access_ended"):
        authorize_case_coordination(actor=case.author, grant_id=grant["id"])
    assert visible_case_coordination_grant_ids(actor=case.author) == []


def test_persisted_scope_drift_ends_coordination(communication):
    case = communication
    grant = live_case_grant(case)
    Scope.objects.filter(grant_id=grant["id"]).update(source_revision="0" * 64)
    with expect("case_access_ended"):
        authorize_case_coordination(actor=case.author, grant_id=grant["id"])


def test_lock_true_acquires_the_grant_row(communication):
    case = communication
    grant = live_case_grant(case)
    with transaction.atomic(), CaptureQueriesContext(connection) as queries:
        authorize_case_coordination(actor=case.author, grant_id=grant["id"], lock=True)
    locked = [q["sql"] for q in queries.captured_queries if "FOR UPDATE" in q["sql"]]
    assert locked
    assert all("counseling_counselorcasecontinuitygrant" in sql for sql in locked)


def test_read_path_never_locks(communication):
    case = communication
    grant = live_case_grant(case)
    with CaptureQueriesContext(connection) as queries:
        authorize_case_coordination(actor=case.author, grant_id=grant["id"])
    assert not [q for q in queries.captured_queries if "FOR UPDATE" in q["sql"]]


def test_visible_ids_include_only_live_case_grants(communication):
    case = communication
    first = live_case_grant(case)
    second_student = additional_student(case)
    second = live_case_grant(
        case, student_id=second_student.student.pk, scopes=second_student.scopes
    )
    third_student = additional_student(case, name="student-c")
    metadata_only = request(
        case, student_id=third_student.student.pk, scopes=third_student.scopes, request_id=uuid4()
    )
    assert metadata_only["communication_purpose"] is None
    expected = sorted([first["id"], second["id"]])
    assert visible_case_coordination_grant_ids(actor=case.author) == expected
    assert visible_case_coordination_grant_ids(actor=case.receiver) == expected
    assert visible_case_coordination_grant_ids(actor=case.head) == []
    assert visible_case_coordination_grant_ids(actor=case.student) == []
    revoke(case, first)
    assert visible_case_coordination_grant_ids(actor=case.author) == [second["id"]]
    expire(second)
    assert visible_case_coordination_grant_ids(actor=case.author) == []
