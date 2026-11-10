"""Live Case coverage, Handoff and case-coordination rules."""

from datetime import timedelta

from compass.accounts.models import UserDesignation
from compass.organization.access_scope import resolve_operational_responsibility_scope
from compass.organization.models import College
from compass.student_academics.models import StudentAcademicProfile

MAX_DURATION = timedelta(days=30)
MAX_ADVANCE = timedelta(days=14)
SOURCE_KINDS = frozenset({"ENCOUNTER", "ROUTINE_EVALUATION"})
CASE_COORDINATION = "CASE_COORDINATION"
PROJECTIONS = {
    "ENCOUNTER": "ENCOUNTER_METADATA_V1",
    "ROUTINE_EVALUATION": "FINALIZED_EVALUATION_V1",
}
ENCOUNTER_METADATA_FIELDS = frozenset(
    {
        "id",
        "started_at",
        "ended_at",
        "entry_mode",
        "delivery_mode",
        "counselor_id",
    }
)
EVALUATION_FIELDS = frozenset({"academic_adjustment_rating", "recommendations"})
PROJECTION_FIELDS = {
    ("ENCOUNTER", "ENCOUNTER_METADATA_V1"): ENCOUNTER_METADATA_FIELDS,
    ("ROUTINE_EVALUATION", "FINALIZED_EVALUATION_V1"): EVALUATION_FIELDS,
}


class ContinuityError(Exception):
    def __init__(self, code, status=403):
        self.code = "continuity_" + code
        self.status = status
        super().__init__("Continuity operation is unavailable (" + code + ").")


def is_head(actor):
    return (
        actor is not None
        and actor.is_active
        and actor.role.code == "COUNSELOR"
        and (
            UserDesignation.objects.filter(
                user_id=actor.pk, designation__code="HEAD_GUIDANCE_COUNSELOR"
            ).exists()
        )
    )


def is_office_requester(actor):
    return (
        actor is not None
        and actor.is_active
        and (actor.role.code == "GUIDANCE_OFFICE_ASSISTANT" or is_head(actor))
    )


def active_college_ids():
    return frozenset(
        College.objects.filter(is_active=True, campus__is_active=True).values_list("pk", flat=True)
    )


def office_college_ids(actor):
    """Live responsibility permits selection, never confidential content reads."""
    if not is_office_requester(actor):
        return frozenset()
    return frozenset(resolve_operational_responsibility_scope(actor).college_ids).intersection(
        active_college_ids()
    )


def office_can_select(actor, student_id):
    return StudentAcademicProfile.objects.filter(
        student_id=student_id,
        current_college_id__in=office_college_ids(actor),
        student__is_active=True,
        student__role__code="STUDENT",
        student__student_lifecycle_status="CURRENT",
    ).exists()


def selected_fields(resource_kind, projection):
    fields = PROJECTION_FIELDS.get((resource_kind, projection))
    if fields is None:
        raise ContinuityError("source_not_found", 404)
    return fields


def overlapping_grants(grant):
    """Reject overlapping requests or approvals for the Student, across all receivers."""
    from compass.counseling.continuity_models import CounselorCaseContinuityGrant

    return CounselorCaseContinuityGrant.objects.filter(
        student_id=grant.student_id,
        decision__in=["REQUESTED", "APPROVED"],
        starts_at__lt=grant.expires_at,
        expires_at__gt=grant.starts_at,
    ).exclude(pk=grant.pk)


def require_unchanged_placement(current_marker, recorded_marker):
    """A College placement change requires a new request."""
    if current_marker != recorded_marker:
        raise ContinuityError("student_changed", 409)
