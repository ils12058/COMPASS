"""Exact structural selectors. Never load ciphertext or enumerate Student history.

These reviewed selectors are policy-gated by their caller. Ordinary assigned getters
and content services remain unchanged. Source-owned read adapters are separate from
these metadata selectors.
"""

from dataclasses import dataclass
from uuid import UUID

from django.db import OperationalError, transaction

from compass.counseling.continuity_encounters import encounter_revision
from compass.counseling.continuity_models import ContinuitySourceKind
from compass.counseling.continuity_policy import ContinuityError
from compass.counseling.models import CounselingEncounter
from compass.routine_interviews.continuity import evaluation_revision
from compass.routine_interviews.models import RoutineInterview

PROJECTIONS = {
    "ENCOUNTER": "ENCOUNTER_METADATA_V1",
    "ROUTINE_EVALUATION": "FINALIZED_EVALUATION_V1",
}
MAX_SCOPES = 32  # Technical request-size bound, not an institutional duration/category policy.


@dataclass(frozen=True, slots=True)
class SelectedSource:
    resource_kind: str
    source_id: UUID
    projection: str


def validate_selection(selection):
    if not 1 <= len(selection) <= MAX_SCOPES:
        raise ContinuityError("invalid_scope", 422)
    keys = [(s.resource_kind, s.source_id, s.projection) for s in selection]
    if len(set(keys)) != len(keys):
        raise ContinuityError("duplicate_scope", 422)
    if any(PROJECTIONS.get(s.resource_kind) != s.projection for s in selection):
        raise ContinuityError("invalid_source_category", 422)


def _resolve_source(*, selection, student_id, requester, policy, original_counselor_id):
    """Caller holds identity locks first; source locks are read-only and deterministic."""
    model = (
        CounselingEncounter
        if selection.resource_kind == ContinuitySourceKind.ENCOUNTER
        else RoutineInterview
    )
    fields = ["id", "student_id", "counselor_id", "updated_at"]
    if model is RoutineInterview:
        fields += ["evaluation_finalized_at", "counseling_encounter_id", "intake_submitted_at"]
    source = (
        model.objects.select_for_update(of=("self",), nowait=True)
        .only(*fields)
        .filter(pk=selection.source_id, student_id=student_id)
        .first()
    )
    # Conceal wrong/nonexistent/draft source uniformly, including safe requested-UUID failures.
    if source is None:
        raise ContinuityError("source_not_found", 404)
    if original_counselor_id is not None and source.counselor_id != original_counselor_id:
        raise ContinuityError("source_not_found", 404)
    if requester.pk not in policy.office_requester_ids:
        capability = (
            "counseling.view_assigned"
            if model is CounselingEncounter
            else "routine_interviews.view_assigned"
        )
        if source.counselor_id != requester.pk or not requester.has_capability(capability):
            raise ContinuityError("source_not_found", 404)
    if model is RoutineInterview:
        if (
            not source.evaluation_finalized_at
            or not source.intake_submitted_at
            or not source.counseling_encounter_id
        ):
            raise ContinuityError("source_not_found", 404)
        linked = (
            CounselingEncounter.objects.select_for_update(of=("self",), nowait=True)
            .only("id", "student_id", "counselor_id", "updated_at")
            .filter(
                pk=source.counseling_encounter_id,
                student_id=student_id,
                counselor_id=source.counselor_id,
            )
            .first()
        )
        if linked is None:
            raise ContinuityError("source_not_found", 404)
        return evaluation_revision(source, linked)
    return encounter_revision(source)


def resolve_source(**kwargs):
    # Existing source writers sometimes lock source -> User. Never wait in the
    # reverse order: a busy source produces a deliberate conflict, without retry.
    validate_selection([kwargs["selection"]])
    try:
        with transaction.atomic():
            return _resolve_source(**kwargs)
    except OperationalError as exc:
        if getattr(exc.__cause__, "sqlstate", None) == "55P03":
            raise ContinuityError("source_busy", 409) from exc
        raise
