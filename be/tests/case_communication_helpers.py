"""Real provisional communication with explicit seams for policy-variation tests."""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.utils import timezone

from compass.accounts.models import Role, User
from compass.counseling import case_communication_policy
from compass.counseling.case_communication_policy import ApprovedCaseCommunicationPolicy
from compass.counseling.continuity_models import (
    CounselorCaseContinuityGrant as Grant,
)
from compass.counseling.continuity_sources import SelectedSource
from compass.counseling.models import CounselingEncounter
from compass.routine_interviews.models import RoutineInterview
from compass.student_academics.models import StudentAcademicProfile
from tests.test_continuity import case, decide, request  # noqa: F401

# Imported case fixture is passed to helpers below.
# ruff: noqa: F811
PURPOSE = "CASE_COORDINATION"
BODY = "Synthetic case coordination message. No Student content."


def approved_communication_policy(
    case,
    *,
    version="synthetic-c1",
    evidence="TEST-ONLY-GMSG5",
    permitted=("CASE_COORDINATION",),
    **changes,
):
    return ApprovedCaseCommunicationPolicy(
        **(
            {
                "version": version,
                "evidence_reference": evidence,
                "valid_from": case.policy.valid_from,
                "valid_until": case.policy.valid_until,
                "permitted_purposes": frozenset(permitted),
            }
            | changes
        )
    )


def patch_communication_policy(monkeypatch, policy):
    monkeypatch.setattr(
        case_communication_policy,
        "get_approved_case_communication_policy",
        lambda: policy,
    )
    return policy


@pytest.fixture
def communication(case):
    """The real provisional communication policy beside the real continuity policy."""
    case.communication_policy = case_communication_policy.get_approved_case_communication_policy()
    return case


def request_case_grant(case, **changes):
    options = {"communication_purpose": PURPOSE, "request_id": uuid4()} | changes
    return request(case, **options)


def live_case_grant(case, **changes):
    return decide(case, request_case_grant(case, **changes))


def open_case_thread(case, *, actor=None, grant_id=None, client_id=None, body=BODY):
    from compass.guidance_messages import services

    return services.open_case_coordination_thread(
        actor=actor or case.author,
        grant_id=grant_id or case.grant["id"],
        client_message_id=client_id or uuid4(),
        body=body,
    )


def revoke(case, grant):
    return decide(case, grant, "REVOKED", revocation_reason="COVERAGE_ENDED")


def expire(grant, *, seconds_ago=1):
    """Move expiry behind the current instant without touching the signed snapshot."""
    moment = timezone.now() - timedelta(seconds=seconds_ago)
    Grant.objects.filter(pk=grant["id"]).update(expires_at=moment)
    return Grant.objects.get(pk=grant["id"])


def additional_student(case, name="student-b"):
    """A second Student with independent sources, for multi-grant visibility tests."""
    student = User.objects.create_user(
        email=f"case-{name}@synthetic.test",
        role=Role.objects.get(code="STUDENT"),
        password=None,
        first_name="Synthetic",
        last_name=name,
    )
    StudentAcademicProfile.objects.create(student=student, current_college=case.college)
    now = timezone.now()
    encounter = CounselingEncounter.objects.create(
        student=student,
        counselor=case.author,
        service=case.service,
        entry_mode="WALK_IN",
        delivery_mode="IN_PERSON",
        started_at=now - timedelta(hours=2),
        ended_at=now - timedelta(hours=1),
    )
    routine = RoutineInterview.objects.create(
        student=student,
        counselor=case.author,
        counseling_encounter=encounter,
        entry_mode="WALK_IN",
        delivery_mode="IN_PERSON",
        intake_submitted_at=now - timedelta(hours=2),
        evaluation_finalized_at=now,
        student_intake_ciphertext="UNREADABLE-SYNTHETIC-INTAKE",
        counselor_evaluation_ciphertext="UNREADABLE-SYNTHETIC-EVALUATION",
    )
    return SimpleNamespace(
        student=student,
        scopes=[
            SelectedSource("ENCOUNTER", encounter.pk, "ENCOUNTER_METADATA_V1"),
            SelectedSource("ROUTINE_EVALUATION", routine.pk, "FINALIZED_EVALUATION_V1"),
        ],
    )
