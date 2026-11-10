"""Live Case coverage, Handoff and case-coordination rules."""

from datetime import datetime, timedelta

from django.utils import timezone

from compass.accounts.models import UserDesignation
from compass.accounts.services import is_current_student
from compass.counseling.continuity_models import ContinuityReason
from compass.organization.access_scope import resolve_operational_responsibility_scope
from compass.organization.models import College
from compass.student_academics.models import StudentAcademicProfile

MAX_DURATION = timedelta(days=30)
MAX_ADVANCE = timedelta(days=14)
SOURCE_KINDS = frozenset({"ENCOUNTER", "ROUTINE_EVALUATION"})
CASE_COORDINATION = "CASE_COORDINATION"
REASON_CATEGORIES = frozenset(ContinuityReason.values)
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


def require_actor(user, action, now):
    roles = {"COUNSELOR"}
    if action in {"view", "request"}:
        roles.add("GUIDANCE_OFFICE_ASSISTANT")
    if user is None or not user.is_active or user.role.code not in roles:
        raise ContinuityError("invalid_role")
    if not user.has_capability("counseling.continuity." + action, at=now):
        raise ContinuityError("missing_capability")
    return user


def require_approver(actor, now):
    require_actor(actor, "approve", now)
    if not is_head(actor):
        # No Acting route: an override/supervision cannot establish formal delegation.
        raise ContinuityError("approval_authority_missing")


def student_placement_marker(student):
    if student is None or not is_current_student(student):
        raise ContinuityError("ineligible_student", 422)
    placement = (
        StudentAcademicProfile.objects.filter(student_id=student.pk)
        .values(
            "current_college_id",
            "updated_at",
            "current_college__is_active",
            "current_college__campus__is_active",
        )
        .first()
    )
    if (
        not placement
        or placement["current_college_id"] is None
        or placement["current_college_id"] not in active_college_ids()
        or not placement["current_college__is_active"]
        or not placement["current_college__campus__is_active"]
    ):
        raise ContinuityError("ineligible_student", 422)
    return str(placement["current_college_id"]) + ":" + placement["updated_at"].isoformat()


def require_receiver(receiver, now):
    if receiver is None or not receiver.is_active or receiver.role.code != "COUNSELOR":
        raise ContinuityError("ineligible_receiver", 422)
    if not receiver.has_capability("counseling.continuity.read_selected", at=now):
        raise ContinuityError("ineligible_receiver", 422)


def validate_interval(starts_at, expires_at, now):
    if (
        not isinstance(starts_at, datetime)
        or not isinstance(expires_at, datetime)
        or timezone.is_naive(starts_at)
        or timezone.is_naive(expires_at)
        or starts_at >= expires_at
        or expires_at <= now
        or expires_at - starts_at > MAX_DURATION
        or starts_at - now > MAX_ADVANCE
    ):
        raise ContinuityError("invalid_interval", 422)
