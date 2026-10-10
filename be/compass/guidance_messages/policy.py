"""Messages owns its narrow content policy; Head designation never grants content access."""

from django.db.models import Q

from compass.accounts.models import StudentLifecycleStatus, User
from compass.appointments.models import AppointmentStatus
from compass.organization.access_scope import (
    HEAD_GUIDANCE_DESIGNATION,
    resolve_operational_responsibility_scope,
)
from compass.organization.models import CounselorResponsibility, StaffSupervision
from compass.service_catalog.canonical import COUNSELING_SERVICE_CODE

from .errors import MessagesPermissionDenied, ThreadNotFound
from .models import GuidanceThread, ThreadKind

STAFF_ROLES = {"COUNSELOR", "GUIDANCE_SERVICES_STAFF"}
RELATIONSHIP_STATUSES = {AppointmentStatus.SCHEDULED, AppointmentStatus.COMPLETED}


def current_actor(actor, *, lock=False):
    query = User.objects.select_related("role")
    if lock:
        query = query.select_for_update(of=("self",), no_key=True)
    user = query.filter(pk=getattr(actor, "pk", None), is_active=True).first()
    if user is None:
        raise MessagesPermissionDenied()
    return user


def require_actor(actor, *, manage=False, staff_only=False):
    suffix = "manage" if manage else "view"
    if actor.role.code == "STUDENT" and not staff_only:
        code = f"guidance_messages.{suffix}_self"
    elif actor.role.code in STAFF_ROLES:
        code = f"guidance_messages.{suffix}"
    else:
        raise MessagesPermissionDenied()
    if not actor.has_capability(code):
        raise MessagesPermissionDenied()


def authorized_threads(actor, *, manage=False):
    require_actor(actor, manage=manage)
    query = GuidanceThread.objects.all()
    if actor.role.code == "STUDENT":
        return query.filter(student_id=actor.pk)
    scope = resolve_operational_responsibility_scope(actor)
    allowed = Q(kind=ThreadKind.OFFICE, routing_college_id__in=scope.college_ids)
    if actor.role.code == "COUNSELOR":
        allowed |= Q(kind=ThreadKind.COUNSELING, counselor_id=actor.pk)
    return query.filter(allowed)


def require_thread(actor, thread, *, manage=False, staff_only=False):
    try:
        require_actor(actor, manage=manage, staff_only=staff_only)
    except MessagesPermissionDenied:
        raise ThreadNotFound() from None
    if actor.role.code == "STUDENT":
        allowed = thread.student_id == actor.pk
    elif thread.kind == ThreadKind.COUNSELING:
        allowed = actor.role.code == "COUNSELOR" and thread.counselor_id == actor.pk
    else:
        allowed = (
            thread.routing_college_id in resolve_operational_responsibility_scope(actor).college_ids
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

    Explicit College Counselors, every Head (for the unique-Head fallback) and the staff they
    supervise. Callers must still apply the canonical workload check to each candidate.
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
    """Whether `user` may be assigned an Office thread: they can manage it under current workload.

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


def recipient_ids(thread):
    """Finite routing candidates, then the same current content authorization as HTTP."""
    candidates = Q(pk=thread.student_id)
    if thread.kind == ThreadKind.COUNSELING:
        candidates |= Q(pk=thread.counselor_id)
    else:
        candidates |= office_staff_candidates(thread)
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
