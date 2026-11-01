"""Explicit GCO transitions and safe metadata; no confidential content or task mutation."""

from django.utils import timezone

from compass.accounts.models import User
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.organization.integrity import catalog_dependent_write, catalog_gate
from compass.referrals import administrative_policy as policy
from compass.referrals.administrative_state import administrative_state
from compass.referrals.faculty_placement import resolve_student_placement
from compass.referrals.faculty_policy import FacultyReferralError
from compass.referrals.faculty_services import _session
from compass.referrals.models import Referral
from compass.referrals.services import ReferralNotFound, _student_in_scope


def _actor(actor, *, manage=False):
    if (
        actor is None
        or not actor.is_active
        or actor.role.code not in {"COUNSELOR", "GUIDANCE_SERVICES_STAFF"}
        or not actor.has_capability("referrals.view")
        or (manage and not actor.has_capability("referrals.manage"))
    ):
        raise policy.AdministrativeReferralError("not_permitted")
    return actor


def _lock(*, actor, actor_session, referral_id, manage=False):
    _actor(User.objects.select_related("role").filter(pk=actor.pk).first(), manage=manage)
    candidate = (
        Referral.objects.filter(pk=referral_id, submission_channel="FACULTY_PORTAL")
        .values_list("student_id", flat=True)
        .first()
    )
    if candidate is None:
        raise ReferralNotFound("The Referral was not found.")
    users = {
        user.pk: user
        for user in User.objects.select_related("role")
        .select_for_update(no_key=True, of=("self",))
        .filter(pk__in={actor.pk, candidate})
        .order_by("id")
    }
    current = _actor(users.get(actor.pk), manage=manage)
    try:
        session = _session(current, actor_session, timezone.now())
    except FacultyReferralError as exc:
        raise policy.AdministrativeReferralError("session_unavailable", exc.status) from None
    item = (
        Referral.objects.select_for_update(of=("self",))
        .select_related(
            "submitted_by",
            "faculty_home_college",
            "student_college_at_submission",
            "acknowledged_by",
            "administratively_closed_by",
        )
        .filter(pk=referral_id, submission_channel="FACULTY_PORTAL", student_id=candidate)
        .first()
    )
    if item is None or not _student_in_scope(current, item.student_id):
        raise ReferralNotFound("The Referral was not found.")
    try:
        session = _session(current, session, timezone.now())
    except FacultyReferralError as exc:
        raise policy.AdministrativeReferralError("session_unavailable", exc.status) from None
    return current, users.get(candidate), item, session


def _authority(actor, student, kind, now):
    placement = resolve_student_placement(student) if student else None
    if placement is None:
        raise policy.AdministrativeReferralError("placement_unavailable", 409)
    approved = policy.require_policy(kind, now)
    policy.require_admitted(actor, placement.college_id, approved)
    return approved


def _person(user):
    return {"id": user.pk, "display_name": user.get_full_name()} if user else None


def _facts(item):
    return {
        "referral_id": item.pk,
        "version": item.administrative_version,
        "state": administrative_state(item),
        "submitted_at": item.submitted_at,
        "submitted_by": _person(item.submitted_by),
        "faculty_home_college": item.faculty_home_college.name,
        "student_college_at_submission": item.student_college_at_submission.name,
        "received_at": item.received_at,
        "acknowledged_by": _person(item.acknowledged_by),
        "closed_at": item.administratively_closed_at,
        "closed_by": _person(item.administratively_closed_by),
        "can_acknowledge": False,
        "can_close": False,
        "valid_until": None,
    }


@catalog_dependent_write
def get_administration(*, actor, actor_session, referral_id):
    current, student, item, session = _lock(
        actor=actor, actor_session=actor_session, referral_id=referral_id
    )
    facts = _facts(item)
    now = timezone.now()
    if item.voided_at is not None or not current.has_capability("referrals.manage"):
        return facts
    kind = "CLOSURE" if item.acknowledged_by_id else "ACKNOWLEDGMENT"
    if item.administratively_closed_at is None:
        try:
            approved = _authority(current, student, kind, now)
            facts["can_close" if kind == "CLOSURE" else "can_acknowledge"] = True
            facts["valid_until"] = min(approved.valid_until, session.expires_at)
        except policy.AdministrativeReferralError:
            pass
    return facts


def transition(
    *,
    actor,
    actor_session,
    referral_id,
    expected_version,
    kind,
    context,
    obligations_reviewed=False,
):
    _actor(User.objects.select_related("role").filter(pk=actor.pk).first(), manage=True)
    if kind not in {"ACKNOWLEDGMENT", "CLOSURE"}:
        raise policy.AdministrativeReferralError("invalid_request", 422)
    policy.require_policy(kind, timezone.now())
    # Supported responsibility/supervision/Head-fallback writers take the shared gate.
    # A short exclusive transition fences all of them before account/resource locks.
    with catalog_gate(exclusive=True):
        return _transition_locked(
            actor=actor,
            actor_session=actor_session,
            referral_id=referral_id,
            expected_version=expected_version,
            kind=kind,
            context=context,
            obligations_reviewed=obligations_reviewed,
        )


def _transition_locked(
    *, actor, actor_session, referral_id, expected_version, kind, context, obligations_reviewed
):
    current, student, item, _current_session = _lock(
        actor=actor, actor_session=actor_session, referral_id=referral_id, manage=True
    )
    now = timezone.now()
    approved = _authority(current, student, kind, now)
    if type(expected_version) is not int or expected_version < 1:
        raise policy.AdministrativeReferralError("invalid_request", 422)
    if item.voided_at is not None or item.administrative_version != expected_version:
        raise policy.AdministrativeReferralError("conflict", 409)
    if kind == "ACKNOWLEDGMENT":
        if item.acknowledged_by_id is not None:
            raise policy.AdministrativeReferralError("conflict", 409)
        item.received_at = now
        item.acknowledged_by = current
        item.acknowledgment_policy_digest = approved.digest
        item.acknowledgment_policy_event_id = approved.activation_event_id
        changed = [
            "received_at",
            "acknowledged_by",
            "acknowledgment_policy_digest",
            "acknowledgment_policy_event",
        ]
    else:
        if item.acknowledged_by_id is None or item.administratively_closed_at is not None:
            raise policy.AdministrativeReferralError("conflict", 409)
        if obligations_reviewed is not True:
            raise policy.AdministrativeReferralError("review_required", 422)
        item.administratively_closed_at = now
        item.administratively_closed_by = current
        item.closure_policy_digest = approved.digest
        item.closure_policy_event_id = approved.activation_event_id
        changed = [
            "administratively_closed_at",
            "administratively_closed_by",
            "closure_policy_digest",
            "closure_policy_event",
        ]
    item.administrative_version += 1
    item.save(update_fields=[*changed, "administrative_version", "updated_at"])
    actual_context = AuditContext.user(
        current,
        request_id=context.request_id,
        ip_address=context.ip_address,
        user_agent_summary=context.user_agent_summary,
    )
    record_event(
        context=actual_context,
        action="referral.acknowledged"
        if kind == "ACKNOWLEDGMENT"
        else "referral.administratively_closed",
        outcome=AuditOutcome.SUCCESS,
        target_type="referrals.referral",
        target_id=item.pk,
        metadata={
            "version": item.administrative_version,
            "policy_digest": approved.digest,
            "policy_event_id": str(approved.activation_event_id),
            "contract": approved.contract,
            "obligations_reviewed": kind == "CLOSURE",
        },
    )
    return _facts(item)
