"""Independent Follow-Up ACL, with type-specific source authorization.

Follow-Up responsibility does not confer access to a source record.
"""
from __future__ import annotations

from compass.accounts.models import User
from compass.organization.access_scope import (
    is_head_guidance,
    resolve_operational_responsibility_scope,
)
from compass.organization.models import StudentAffiliation

from .errors import FollowUpInvalid, FollowUpNotFound, FollowUpPermissionDenied
from .models import FollowUpCategory, FollowUpSource, FollowUpVisibility

ROLES = frozenset({"COUNSELOR", "GUIDANCE_SERVICES_STAFF"})


def current_actor(actor, *, manage=False, lock=False):
    query = User.objects.select_related("role")
    if lock:
        query = query.select_for_update(of=("self",))
    actor = query.filter(pk=getattr(actor, "pk", None), is_active=True).first()
    capability = "guidance_followups.manage" if manage else "guidance_followups.view"
    if actor is None or actor.role.code not in ROLES or not actor.has_capability(capability):
        raise FollowUpPermissionDenied("Guidance Follow-Up access is required.")
    return actor


def valid_student(student_id, *, lock=False):
    query = User.objects.select_related("role")
    if lock:
        query = query.select_for_update(of=("self",))
    student = query.filter(pk=student_id, is_active=True, role__code="STUDENT").first()
    if student is None:
        raise FollowUpNotFound("The Student is not available for Follow-Ups.")
    return student


def in_operational_scope(actor, student_id):
    if is_head_guidance(actor):
        return True  # Existing Referral operational oversight, not Counseling access.
    scope = resolve_operational_responsibility_scope(actor)
    if not scope.college_ids:
        return False
    return StudentAffiliation.objects.filter(
        student_id=student_id, college_id__in=scope.college_ids,
        college__is_active=True, college__campus__is_active=True,
    ).exists()


def require_source(actor, *, kind, source_id, student_id, manage=False):
    if kind == FollowUpSource.COUNSELING_ENCOUNTER:
        if actor.role.code != "COUNSELOR" or not actor.has_capability(
            "counseling.manage_assigned" if manage else "counseling.view_assigned"
        ):
            raise FollowUpNotFound("The related record is not available.")
        from compass.counseling.services import get_encounter_for_actor
        from compass.counseling.models import CounselingEncounter
        item = CounselingEncounter.objects.filter(
            pk=source_id, student_id=student_id, counselor_id=actor.pk,
        ).first()
        if item is None:
            raise FollowUpNotFound("The related record is not available.")
        try:
            get_encounter_for_actor(encounter_id=source_id, actor=actor)
        except Exception:
            raise FollowUpNotFound("The related record is not available.") from None
    elif kind == FollowUpSource.ROUTINE_INTERVIEW:
        if actor.role.code != "COUNSELOR" or not actor.has_capability(
            "routine_interviews.manage_assigned" if manage else "routine_interviews.view_assigned"
        ):
            raise FollowUpNotFound("The related record is not available.")
        from compass.routine_interviews.models import RoutineInterview
        from compass.routine_interviews.services import get_assigned
        if not RoutineInterview.objects.filter(
            pk=source_id, student_id=student_id, counselor_id=actor.pk,
            appointment__status__in=["SCHEDULED", "COMPLETED"],
        ).exists() and not RoutineInterview.objects.filter(
            pk=source_id, student_id=student_id, counselor_id=actor.pk,
            appointment__isnull=True,
        ).exists():
            raise FollowUpNotFound("The related record is not available.")
        try:
            get_assigned(counselor=actor, routine_interview_id=source_id)
        except Exception:
            raise FollowUpNotFound("The related record is not available.") from None
    elif kind == FollowUpSource.REFERRAL:
        if not actor.has_capability("referrals.manage" if manage else "referrals.view"):
            raise FollowUpNotFound("The related record is not available.")
        from compass.referrals.models import Referral
        from compass.referrals.services import get_referral
        if not Referral.objects.filter(pk=source_id, student_id=student_id, voided_at__isnull=True).exists():
            raise FollowUpNotFound("The related record is not available.")
        try:
            get_referral(actor=actor, referral_id=source_id)
        except Exception:
            raise FollowUpNotFound("The related record is not available.") from None
    else:
        raise FollowUpNotFound("The related record is not available.")
    return True


def classify(*, source_kind, category):
    if category not in FollowUpCategory.values:
        raise FollowUpInvalid("The follow-up category is unsupported.")
    if source_kind in {
        FollowUpSource.COUNSELING_ENCOUNTER, FollowUpSource.ROUTINE_INTERVIEW,
    }:
        if category != FollowUpCategory.COUNSELING:
            raise FollowUpInvalid("A professional follow-up requires the counseling category.")
        return FollowUpVisibility.COUNSELOR_CONFIDENTIAL
    if source_kind == FollowUpSource.REFERRAL:
        if category != FollowUpCategory.REFERRAL_ACTION:
            raise FollowUpInvalid("A Referral follow-up requires referral coordination.")
        return FollowUpVisibility.OPERATIONAL
    if source_kind is None:
        if category == FollowUpCategory.COUNSELING:
            raise FollowUpInvalid("Counseling follow-ups require an authorized source.")
        return FollowUpVisibility.OPERATIONAL
    raise FollowUpInvalid("The follow-up source is unsupported.")


def require_assignee(candidate_id, *, student_id, visibility, source_kind=None, source_id=None):
    candidate = User.objects.select_related("role").filter(pk=candidate_id, is_active=True).first()
    if candidate is None or candidate.role.code not in ROLES:
        raise FollowUpInvalid("The selected staff member is unavailable.")
    if not candidate.has_capability("guidance_followups.manage"):
        raise FollowUpInvalid("The selected staff member cannot manage follow-ups.")
    if visibility == FollowUpVisibility.COUNSELOR_CONFIDENTIAL:
        if candidate.role.code != "COUNSELOR":
            raise FollowUpInvalid("Confidential follow-ups require an authorized Counselor.")
        try:
            require_source(
                candidate, kind=source_kind, source_id=source_id,
                student_id=student_id, manage=True,
            )
        except FollowUpNotFound:
            raise FollowUpInvalid("The selected Counselor cannot manage this follow-up.") from None
    elif not in_operational_scope(candidate, student_id):
        raise FollowUpInvalid("The selected staff member is not responsible for this Student.")
    return candidate


def authorized(actor, followup, *, manage=False):
    if followup.assigned_to_id != actor.pk:
        return False
    if followup.visibility == FollowUpVisibility.OPERATIONAL:
        return in_operational_scope(actor, followup.student_id)
    if followup.visibility == FollowUpVisibility.COUNSELOR_CONFIDENTIAL:
        if actor.role.code != "COUNSELOR":
            return False
        try:
            require_source(
                actor, kind=followup.source_kind, source_id=followup.source_id,
                student_id=followup.student_id, manage=manage,
            )
        except FollowUpNotFound:
            return False
        return True
    return False


def scope(actor, queryset):
    # Coarse bound in SQL; final authorization is reapplied on each returned item.
    return queryset.filter(assigned_to_id=actor.pk)


def require_followup(actor, followup, *, manage=False):
    if not authorized(actor, followup, manage=manage):
        raise FollowUpNotFound("The Guidance Follow-Up was not found.")
    return followup


def visible_source(actor, followup):
    if not followup.source_kind or not followup.source_id:
        return None
    try:
        require_source(
            actor, kind=followup.source_kind, source_id=followup.source_id,
            student_id=followup.student_id,
        )
    except FollowUpNotFound:
        return None
    return {"kind": followup.source_kind, "id": followup.source_id}
