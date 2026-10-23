"""Routine-owned finalized Evaluation projection, independent of ordinary assigned detail."""

import hashlib

from django.core.exceptions import ImproperlyConfigured

from compass.counseling.continuity_encounters import _lock_encounter
from compass.counseling.continuity_policy import ContinuityError
from compass.routine_interviews import content
from compass.routine_interviews.errors import RoutineContentUnavailable
from compass.routine_interviews.matching import (
    RoutineEncounterFacts,
    routine_interview_encounter_match_issue_for_facts,
)
from compass.routine_interviews.models import RoutineInterview


def evaluation_revision(item, encounter):
    marker = item.updated_at.isoformat() + ":" + encounter.updated_at.isoformat()
    return hashlib.sha256(marker.encode()).hexdigest()


def _lock_evaluation(*, routine_interview_id, student_id, original_counselor_id, now):
    item = (
        RoutineInterview.objects.select_for_update(of=("self",), nowait=True)
        .only(
            "id",
            "student_id",
            "counselor_id",
            "updated_at",
            "intake_submitted_at",
            "evaluation_finalized_at",
            "counseling_encounter_id",
            "entry_mode",
            "delivery_mode",
            "appointment_id",
        )
        .filter(pk=routine_interview_id, student_id=student_id)
        .first()
    )
    if (
        item is None
        or item.intake_submitted_at is None
        or item.evaluation_finalized_at is None
        or item.counseling_encounter_id is None
        or item.evaluation_finalized_at > now
        or item.intake_submitted_at > item.evaluation_finalized_at
        or (original_counselor_id is not None and item.counselor_id != original_counselor_id)
    ):
        raise ContinuityError("source_not_found", 404)
    encounter, service = _lock_encounter(
        encounter_id=item.counseling_encounter_id,
        student_id=student_id,
        original_counselor_id=item.counselor_id,
        now=now,
    )
    issue = routine_interview_encounter_match_issue_for_facts(
        item=item,
        now=now,
        facts=RoutineEncounterFacts(
            student_id=encounter.student_id,
            counselor_id=encounter.counselor_id,
            service_code=service.code,
            delivery_mode=encounter.delivery_mode,
            ended_at=encounter.ended_at,
            entry_mode=encounter.entry_mode,
            appointment_id=encounter.appointment_id,
        ),
    )
    if issue is not None or encounter.ended_at > item.evaluation_finalized_at:
        raise ContinuityError("source_not_found", 404)
    return item, encounter


def _evaluation_projection(item, fields):
    # This call is reached only inside the coordinated authorization transaction.
    # The Intake column stays deferred, even when its ciphertext is malformed.
    try:
        values = content.read_evaluation(item)
    except (RoutineContentUnavailable, ImproperlyConfigured):
        raise ContinuityError("source_unavailable", 503) from None
    # Explicit policy-approved V1 keys only. Never return the complete decrypted dictionary.
    return {field: values[field] for field in sorted(fields)}


def read_selected_evaluation_for_continuity(
    *,
    actor,
    grant_id,
    routine_interview_id,
    expected_version,
    context=None,
    actor_session_id=None,
    actor_session_digest=None,
):
    from compass.counseling.continuity_access import read_selected_continuity_record

    return read_selected_continuity_record(
        actor=actor,
        grant_id=grant_id,
        source_id=routine_interview_id,
        resource_kind="ROUTINE_EVALUATION",
        projection="FINALIZED_EVALUATION_V1",
        expected_version=expected_version,
        context=context,
        actor_session_id=actor_session_id,
        actor_session_digest=actor_session_digest,
    )
