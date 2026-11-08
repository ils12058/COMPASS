"""Authorization is a kind-explicit matrix: a kind with no rule is denied, never inferred."""

from dataclasses import dataclass

from django.db.models import Q

from compass.accounts.models import StudentLifecycleStatus, User
from compass.accounts.services import effective_capabilities
from compass.appointments.models import AppointmentStatus
from compass.counseling.case_communication import (
    authorize_case_coordination,
    visible_case_coordination_grant_ids,
)
from compass.counseling.continuity_policy import ContinuityError
from compass.organization.access_scope import (
    HEAD_GUIDANCE_DESIGNATION,
    resolve_general_guidance_college_scope,
)
from compass.organization.models import CounselorResponsibility, StaffSupervision
from compass.referrals.services import accessible_referrals
from compass.service_catalog.canonical import COUNSELING_SERVICE_CODE

from .errors import CaseCoordinationEnded, MessagesPermissionDenied, ThreadNotFound
from .models import GuidanceThread, ThreadKind

STAFF_ROLES = {"COUNSELOR", "GUIDANCE_SERVICES_STAFF"}
RELATIONSHIP_STATUSES = {AppointmentStatus.SCHEDULED, AppointmentStatus.COMPLETED}


@dataclass(frozen=True)
class _KindRule:
    """Who a thread of one kind is about, and which staff relation reaches it."""

    student_participant: bool
    staff_roles: frozenset[str]
    college_scoped: bool
    counselor_participant: bool
    office_staff_recipients: bool
    requester_participant: bool = False
    endpoint_staff_recipients: bool = False
    staff_capability: str | None = None
    referral_scoped: bool = False
    staff_capability_action_suffix: bool = False
    direct_pair_participant: bool = False
    case_grant_participant: bool = False


# Every kind the database can hold has an entry, so visibility, per-thread access and push routing
# all read one table. `None` would mean reserved: denied for every role without consulting any
# resource column. It replaces the old "anything not Counseling is College-scoped Office"
# fallthrough, which would otherwise have disclosed each new kind to every staff member in its
# College on creation. GMSG-2 gave FACULTY_INQUIRY its rule; GMSG-3 gave REFERRAL_COORDINATION its
# rule (staff scope is the Referral's current operational scope, never the thread's College
# snapshot); GMSG-4 gave COUNSELOR_DIRECT its pair rule; GMSG-5 gives COUNSELOR_CASE_COORDINATION
# its rule: only the grant's exact Counselor pair, and only while the grant itself is live.
_RULES: dict[str, _KindRule | None] = {
    ThreadKind.OFFICE: _KindRule(True, frozenset(STAFF_ROLES), True, False, True),
    ThreadKind.COUNSELING: _KindRule(True, frozenset({"COUNSELOR"}), False, True, False),
    ThreadKind.FACULTY_INQUIRY: _KindRule(
        student_participant=False,
        staff_roles=frozenset(STAFF_ROLES),
        college_scoped=False,
        counselor_participant=False,
        office_staff_recipients=False,
        requester_participant=True,
        endpoint_staff_recipients=True,
        staff_capability="guidance_messages.intake",
    ),
    ThreadKind.REFERRAL_COORDINATION: _KindRule(
        student_participant=False,
        staff_roles=frozenset(STAFF_ROLES),
        college_scoped=False,
        counselor_participant=False,
        office_staff_recipients=False,
        requester_participant=True,
        endpoint_staff_recipients=False,
        staff_capability=None,
        referral_scoped=True,
    ),
    ThreadKind.COUNSELOR_DIRECT: _KindRule(
        student_participant=False,
        staff_roles=frozenset({"COUNSELOR"}),
        college_scoped=False,
        counselor_participant=False,
        office_staff_recipients=False,
        direct_pair_participant=True,
        staff_capability="guidance_messages.counselor_direct",
        staff_capability_action_suffix=True,
    ),
    ThreadKind.COUNSELOR_CASE_COORDINATION: _KindRule(
        student_participant=False,
        staff_roles=frozenset({"COUNSELOR"}),
        college_scoped=False,
        counselor_participant=False,
        office_staff_recipients=False,
        case_grant_participant=True,
        staff_capability="guidance_messages.case_coordination",
        staff_capability_action_suffix=True,
    ),
}


def current_actor(actor, *, lock=False):
    query = User.objects.select_related("role")
    if lock:
        query = query.select_for_update(of=("self",), no_key=True)
    user = query.filter(pk=getattr(actor, "pk", None), is_active=True).first()
    if user is None:
        raise MessagesPermissionDenied()
    return user


def require_actor(actor, *, manage=False, staff_only=False, kind=None, codes=None):
    """Whether `actor` may act at all, optionally scoped to one thread kind.

    `kind=None` is the directory question: a Faculty member holding only a self-facing family
    capability (inquiry or referral) must be able to load. A kind with no rule denies before any
    capability lookup. `codes` is the actor's already-resolved capability set; callers that check
    several codes for the same actor pass it so one lookup is enough.
    """
    if codes is None:
        codes = effective_capabilities(actor)
    suffix = "manage" if manage else "view"
    rule = _RULES.get(kind) if kind is not None else None
    if kind is not None and rule is None:
        raise MessagesPermissionDenied()
    if (
        actor.role.code == "STUDENT"
        and not staff_only
        and (rule is None or rule.student_participant)
    ):
        code = f"guidance_messages.{suffix}_self"
    elif actor.role.code in STAFF_ROLES and (rule is None or actor.role.code in rule.staff_roles):
        if rule is not None and rule.staff_capability:
            code = (
                f"{rule.staff_capability}.{suffix}"
                if rule.staff_capability_action_suffix
                else rule.staff_capability
            )
        else:
            code = f"guidance_messages.{suffix}"
    elif (
        actor.role.code == "FACULTY"
        and not staff_only
        and (rule is None or kind in (ThreadKind.FACULTY_INQUIRY, ThreadKind.REFERRAL_COORDINATION))
    ):
        cap = "referral" if kind == ThreadKind.REFERRAL_COORDINATION else "inquiry"
        code = f"guidance_messages.{cap}_{suffix}_self"
    else:
        raise MessagesPermissionDenied()
    if code not in codes:
        raise MessagesPermissionDenied()
    # A Referral-scoped kind also needs the Referral capability that scopes it. Without this the
    # messaging capability alone would answer 200 for an in-scope Referral the actor may no longer
    # read, disclosing that a conversation does not yet exist.
    if (
        rule is not None
        and rule.referral_scoped
        and actor.role.code in STAFF_ROLES
        and f"referrals.{suffix}" not in codes
    ):
        raise MessagesPermissionDenied()


def authorized_threads(actor, *, manage=False):
    codes = effective_capabilities(actor)
    require_actor(actor, manage=manage, codes=codes)
    suffix = "manage" if manage else "view"
    visible = Q()
    if actor.role.code == "STUDENT":
        for kind, rule in _RULES.items():
            if rule is not None and rule.student_participant:
                visible |= Q(kind=kind, student_id=actor.pk)
    elif actor.role.code == "FACULTY":
        # A kind the actor cannot view must not appear in the directory, even if a row exists.
        if "guidance_messages.inquiry_view_self" in codes:
            visible |= Q(kind=ThreadKind.FACULTY_INQUIRY, requester_id=actor.pk)
        if "guidance_messages.referral_view_self" in codes:
            visible |= Q(kind=ThreadKind.REFERRAL_COORDINATION, requester_id=actor.pk)
    else:
        scope = resolve_general_guidance_college_scope(actor)
        for kind, rule in _RULES.items():
            if rule is None or actor.role.code not in rule.staff_roles:
                continue
            if rule.staff_capability:
                capability = (
                    f"{rule.staff_capability}.{suffix}"
                    if rule.staff_capability_action_suffix
                    else rule.staff_capability
                )
                if capability in codes:
                    if rule.direct_pair_participant:
                        visible |= Q(
                            Q(kind=kind, direct_first_user_id=actor.pk)
                            | Q(kind=kind, direct_second_user_id=actor.pk)
                        )
                    elif rule.case_grant_participant:
                        # Never the generic `kind=` branch: that would show every Counselor holding
                        # the capability every case conversation in the institution.
                        visible |= Q(
                            kind=kind,
                            relationship_case_grant_id__in=visible_case_coordination_grant_ids(
                                actor=actor
                            ),
                        )
                    else:
                        visible |= Q(kind=kind)
                continue
            if rule.referral_scoped:
                # Current Referral operational scope, never the thread's College snapshot.
                if f"referrals.{suffix}" in codes:
                    visible |= Q(
                        kind=kind,
                        relationship_referral_id__in=accessible_referrals(actor).values("pk"),
                    )
                continue
            if rule.college_scoped:
                visible |= Q(kind=kind, routing_college_id__in=scope.college_ids)
            if rule.counselor_participant:
                visible |= Q(kind=kind, counselor_id=actor.pk)
    if not visible:
        return GuidanceThread.objects.none()
    return GuidanceThread.objects.filter(visible)


def require_thread(actor, thread, *, manage=False, staff_only=False):
    rule = _RULES.get(thread.kind)
    if rule is None:
        raise ThreadNotFound()
    codes = effective_capabilities(actor)
    suffix = "manage" if manage else "view"
    try:
        require_actor(actor, manage=manage, staff_only=staff_only, kind=thread.kind, codes=codes)
    except MessagesPermissionDenied:
        raise ThreadNotFound() from None
    if actor.role.code == "STUDENT":
        allowed = rule.student_participant and thread.student_id == actor.pk
    elif actor.role.code == "FACULTY":
        allowed = rule.requester_participant and thread.requester_id == actor.pk
    elif rule.case_grant_participant:
        # The thread's own row never decides access: the live grant does, re-evaluated here.
        if not thread.relationship_case_grant_id:
            raise ThreadNotFound()
        try:
            authorize_case_coordination(actor=actor, grant_id=thread.relationship_case_grant_id)
        except ContinuityError as exc:
            if exc.code == "continuity_case_access_ended":
                raise CaseCoordinationEnded() from None
            raise ThreadNotFound() from None
        allowed = True
    else:
        allowed = actor.role.code in rule.staff_roles and (
            (
                rule.direct_pair_participant
                and actor.pk in (thread.direct_first_user_id, thread.direct_second_user_id)
            )
            or (bool(rule.staff_capability) and not rule.direct_pair_participant)
            or (
                rule.college_scoped
                and thread.routing_college_id
                in resolve_general_guidance_college_scope(actor).college_ids
            )
            or (rule.counselor_participant and thread.counselor_id == actor.pk)
            or (
                rule.referral_scoped
                and bool(thread.relationship_referral_id)
                and f"referrals.{suffix}" in codes
                and accessible_referrals(actor).filter(pk=thread.relationship_referral_id).exists()
            )
        )
    if not allowed:
        raise ThreadNotFound()


def eligible_relationship(appointment):
    return (
        appointment.service.code == COUNSELING_SERVICE_CODE
        and appointment.status in RELATIONSHIP_STATUSES
        and appointment.student.is_active
        and appointment.student.role.code == "STUDENT"
        and appointment.provider.is_active
        and appointment.provider.role.code == "COUNSELOR"
        and appointment.provider.has_capability("guidance_messages.view")
    )


def relationship_participant(actor, appointment):
    """The exact Student or provider Counselor of the Appointment, as creation requires."""
    return (actor.role.code == "STUDENT" and actor.pk == appointment.student_id) or (
        actor.role.code == "COUNSELOR" and actor.pk == appointment.provider_id
    )


def current_student(student):
    return (
        student.is_active
        and student.role.code == "STUDENT"
        and student.student_lifecycle_status == StudentLifecycleStatus.CURRENT
    )


def office_staff_candidates(thread):
    """A finite superset of staff who could handle an Office thread's College right now.

    Explicit College Counselors, every valid Head (including across assigned Colleges),
    and their supervised staff. Callers must still apply current College visibility,
    effective capabilities and actor eligibility to each candidate.
    """
    counselors = (
        User.objects.filter(is_active=True, role__code="COUNSELOR")
        .filter(
            Q(
                pk__in=CounselorResponsibility.objects.filter(
                    college_id=thread.routing_college_id
                ).values("counselor_id")
            )
            | Q(designation_assignments__designation__code=HEAD_GUIDANCE_DESIGNATION)
        )
        .values("pk")
    )
    return Q(pk__in=counselors) | Q(
        pk__in=StaffSupervision.objects.filter(supervisor_id__in=counselors).values("staff_id")
    )


def eligible_handler(user, thread):
    """Whether `user` may manage an Office thread through current college visibility.

    Assignment is workflow ownership only. It never grants access; this check only keeps it from
    pointing at someone who could not act on the thread.
    """
    if thread.kind != ThreadKind.OFFICE or not user.is_active or user.role.code not in STAFF_ROLES:
        return False
    try:
        require_thread(user, thread, manage=True, staff_only=True)
    except ThreadNotFound:
        return False
    return True


def eligible_handlers(thread):
    users = (
        User.objects.filter(
            office_staff_candidates(thread), is_active=True, role__code__in=STAFF_ROLES
        )
        .select_related("role")
        .distinct()
    )
    return [user for user in users if eligible_handler(user, thread)]


def active_staff_candidates():
    """Finite superset: active staff; caller re-checks effective capability and Referral scope."""
    return Q(role__code__in=STAFF_ROLES, is_active=True)


def has_intake_staff():
    return any(
        user.has_capability("guidance_messages.intake")
        for user in User.objects.filter(is_active=True, role__code__in=STAFF_ROLES)
        .select_related("role")
        .distinct()
    )


# GMSG-6/7 conversation sides. A requester kind is one person (Student or Faculty) writing to the
# Guidance Office as an institution; a pair kind is exactly two people. Receipts and typing always
# travel from one side to the other, never between staff on the Office side.
REQUESTER_KINDS = frozenset(
    {ThreadKind.OFFICE, ThreadKind.FACULTY_INQUIRY, ThreadKind.REFERRAL_COORDINATION}
)
PAIR_KINDS = frozenset(
    {ThreadKind.COUNSELING, ThreadKind.COUNSELOR_DIRECT, ThreadKind.COUNSELOR_CASE_COORDINATION}
)
# D-GMSG-04 (provisional engineering default, not GCO/DPO-approved): Office staff see the
# requester's personal Seen only in a Student Office thread. Faculty inquiry and Referral
# coordination withhold it until D-GMSG-03 and D-GMSG-22 are decided.
REQUESTER_RECEIPT_KINDS = frozenset({ThreadKind.OFFICE})


def requester_id(thread):
    """The one person on the requester side of a requester kind, or None for any other kind."""
    if thread.kind == ThreadKind.OFFICE:
        return thread.student_id
    if thread.kind in (ThreadKind.FACULTY_INQUIRY, ThreadKind.REFERRAL_COORDINATION):
        return thread.requester_id
    return None


def counterpart_recipient_ids(thread, actor):
    """Currently authorized people on the other side of the conversation from `actor`.

    The requester's counterpart is every authorized Office reader; an Office reader's counterpart
    is the requester alone, so staff never receive each other's typing or receipts. A pair's
    counterpart is the other person. Recipients come from `recipient_ids`, so the same current
    authorization as HTTP applies and a revoked reader receives nothing.
    """
    recipients = recipient_ids(thread)
    if thread.kind in REQUESTER_KINDS:
        requester = requester_id(thread)
        if actor.pk == requester:
            return tuple(user_id for user_id in recipients if user_id != requester)
        return tuple(user_id for user_id in recipients if user_id == requester)
    if thread.kind in PAIR_KINDS:
        return tuple(user_id for user_id in recipients if user_id != actor.pk)
    return ()


def recipient_ids(thread):
    """Finite routing candidates, then the same current content authorization as HTTP."""
    rule = _RULES.get(thread.kind)
    if rule is None:
        return ()
    candidates = Q()
    if rule.student_participant and thread.student_id:
        candidates |= Q(pk=thread.student_id)
    if rule.counselor_participant and thread.counselor_id:
        candidates |= Q(pk=thread.counselor_id)
    if rule.requester_participant and thread.requester_id:
        candidates |= Q(pk=thread.requester_id)
    if rule.direct_pair_participant:
        if thread.direct_first_user_id:
            candidates |= Q(pk=thread.direct_first_user_id)
        if thread.direct_second_user_id:
            candidates |= Q(pk=thread.direct_second_user_id)
    if rule.case_grant_participant and thread.relationship_case_grant_id:
        grant = thread.relationship_case_grant
        candidates |= Q(pk=grant.original_counselor_id)
        candidates |= Q(pk=grant.receiving_counselor_id)
    if rule.office_staff_recipients:
        candidates |= office_staff_candidates(thread)
    if rule.endpoint_staff_recipients:
        candidates |= active_staff_candidates()
    if rule.referral_scoped:
        candidates |= active_staff_candidates()
    if not candidates:
        return ()
    recipients = []
    for user in (
        User.objects.filter(candidates, is_active=True).select_related("role").distinct().iterator()
    ):
        try:
            require_thread(user, thread)
        except ThreadNotFound:
            continue
        recipients.append(user.pk)
    return tuple(recipients)
