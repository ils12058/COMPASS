"""PostgreSQL is authoritative. Every success audit shares the mutation transaction."""

from uuid import UUID

from django.db import transaction
from django.db.models import BigIntegerField, Count, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from compass.accounts.models import User
from compass.appointments.models import Appointment
from compass.audit.actions import (
    GUIDANCE_MESSAGES_MESSAGE_SENT,
    GUIDANCE_MESSAGES_THREAD_ASSIGNED,
    GUIDANCE_MESSAGES_THREAD_CREATED,
    GUIDANCE_MESSAGES_THREAD_REOPENED,
    GUIDANCE_MESSAGES_THREAD_RESOLVED,
)
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.operational_students import list_scoped_operational_students
from compass.organization.access_scope import resolve_operational_responsibility_scope
from compass.organization.models import StudentAffiliation
from compass.organization.services import resolve_default_counselor_for_student
from compass.realtime.publish import publish_to_user_on_commit
from compass.service_catalog.canonical import COUNSELING_SERVICE_CODE

from . import content, policy
from .errors import InvalidMessageInput, MessagesConflict, ThreadNotFound
from .models import (
    GuidanceMessage,
    GuidanceThread,
    GuidanceThreadReadState,
    ThreadKind,
    ThreadStatus,
)

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50


def _audit(actor, action, thread, *, context=None, **metadata):
    record_event(
        context=context or AuditContext.user(actor),
        action=action,
        outcome=AuditOutcome.SUCCESS,
        target_type="guidance.messages.thread",
        target_id=thread.pk,
        metadata={"thread_id": str(thread.pk), "kind": thread.kind, **metadata},
    )


def _publish_current(thread_id):
    thread = GuidanceThread.objects.get(pk=thread_id)
    for user_id in policy.recipient_ids(thread):
        publish_to_user_on_commit(user_id, "messages.thread_changed", {"thread_id": thread.pk})


def _changed(thread):
    # Resolve current recipients at commit, after the state is durable. A callback failure
    # cannot undo it; the publisher independently drops transport errors.
    transaction.on_commit(lambda: _publish_current(thread.pk), robust=True)


def _pagination(page, page_size):
    if (
        type(page) is not int
        or page < 1
        or type(page_size) is not int
        or not 1 <= page_size <= MAX_PAGE_SIZE
    ):
        raise InvalidMessageInput("Use a positive page and page_size between 1 and 50.")


def _directory(query, actor):
    cursor = GuidanceThreadReadState.objects.filter(
        thread_id=OuterRef("pk"), user_id=actor.pk
    ).values("last_read_sequence")[:1]
    query = query.annotate(
        own_last_read_sequence=Coalesce(Subquery(cursor), Value(0), output_field=BigIntegerField())
    )
    unread = (
        GuidanceMessage.objects.filter(
            thread_id=OuterRef("pk"), sequence__gt=OuterRef("own_last_read_sequence")
        )
        .exclude(sender_id=actor.pk)
        .order_by()
        .values("thread_id")
        .annotate(count=Count("pk"))
        .values("count")
    )
    return query.select_related("student", "counselor", "assigned_to", "routing_college").annotate(
        own_unread_count=Coalesce(Subquery(unread), Value(0))
    )


def list_threads(*, actor, page=1, page_size=DEFAULT_PAGE_SIZE):
    _pagination(page, page_size)
    actor = policy.current_actor(actor)
    query = _directory(policy.authorized_threads(actor), actor).order_by("-last_message_at", "-id")
    offset = (page - 1) * page_size
    rows = list(query[offset : offset + page_size + 1])
    return rows[:page_size], len(rows) > page_size


def get_thread(*, actor, thread_id):
    actor = policy.current_actor(actor)
    thread = GuidanceThread.objects.filter(pk=thread_id).first()
    if thread is None:
        raise ThreadNotFound()
    policy.require_thread(actor, thread)
    return _directory(GuidanceThread.objects.filter(pk=thread_id), actor).get()


def list_messages(*, actor, thread_id, before_sequence=None, page_size=DEFAULT_PAGE_SIZE):
    _pagination(1, page_size)
    thread = get_thread(actor=actor, thread_id=thread_id)
    query = thread.messages.select_related("sender").order_by("-sequence")
    if before_sequence is not None:
        if type(before_sequence) is not int or before_sequence < 1:
            raise InvalidMessageInput("before_sequence must be a positive integer.")
        query = query.filter(sequence__lt=before_sequence)
    rows = list(query[: page_size + 1])
    return list(reversed(rows[:page_size])), len(rows) > page_size


def _lock_thread(actor, thread_id, *, staff_only=False):
    thread = GuidanceThread.objects.select_for_update(of=("self",)).filter(pk=thread_id).first()
    if thread is None:
        raise ThreadNotFound()
    policy.require_thread(actor, thread, manage=True, staff_only=staff_only)
    return thread


def _client_id(value):
    if not isinstance(value, UUID):
        raise InvalidMessageInput("client_message_id must be a UUID.")


def _replay(actor, client_message_id, thread_id):
    message = GuidanceMessage.objects.filter(
        sender_id=actor.pk, client_message_id=client_message_id
    ).first()
    if message is not None and message.thread_id != thread_id:
        raise MessagesConflict("client_message_id has already been used for another thread.")
    return message


def _send_locked(*, actor, thread, client_message_id, body, context):
    policy.require_thread(actor, thread, manage=True)
    _client_id(client_message_id)
    replay = _replay(actor, client_message_id, thread.pk)
    if replay is not None:
        return replay
    if thread.status != ThreadStatus.OPEN:
        raise MessagesConflict("This Guidance thread is resolved.")
    body = content.validate_body(body)
    message = GuidanceMessage(
        thread=thread,
        sender=actor,
        client_message_id=client_message_id,
        sequence=thread.last_sequence + 1,
    )
    message.body_ciphertext = content.encrypt_body(message, body)
    message.save(force_insert=True)
    thread.last_sequence = message.sequence
    thread.last_message_at = message.created_at
    thread.save(update_fields=("last_sequence", "last_message_at", "updated_at"))
    _audit(
        actor,
        GUIDANCE_MESSAGES_MESSAGE_SENT,
        thread,
        context=context,
        message_id=str(message.pk),
        sequence=message.sequence,
    )
    _changed(thread)
    return message


@transaction.atomic
def send_message(*, actor, thread_id, client_message_id, body, context=None):
    # NO KEY UPDATE serializes the sender without blocking peer foreign-key checks
    # during concurrent thread creation. Consistent sender -> thread locking serializes
    # reuse of a client ID across
    # different threads. Database uniqueness remains the final independent guard.
    actor = policy.current_actor(actor, lock=True)
    thread = _lock_thread(actor, thread_id)
    return _send_locked(
        actor=actor, thread=thread, client_message_id=client_message_id, body=body, context=context
    )


@transaction.atomic
def open_office_thread(*, actor, client_message_id, body, student_id=None, context=None):
    actor = policy.current_actor(actor, lock=True)
    policy.require_actor(actor, manage=True, staff_only=student_id is not None)
    _client_id(client_message_id)
    if actor.role.code == "STUDENT":
        student = actor
    else:
        scope = resolve_operational_responsibility_scope(actor)
        student = (
            User.objects.select_related("role")
            .select_for_update(of=("self",), no_key=True)
            .filter(
                pk=student_id, organization_student_affiliation__college_id__in=scope.college_ids
            )
            .first()
        )
        if student is None:
            raise ThreadNotFound()
    if not policy.current_student(student):
        raise ThreadNotFound()
    prior = (
        GuidanceMessage.objects.filter(sender=actor, client_message_id=client_message_id)
        .select_related("thread")
        .first()
    )
    if prior is not None:
        if prior.thread.kind != ThreadKind.OFFICE or prior.thread.student_id != student.pk:
            raise MessagesConflict("client_message_id has already been used for another thread.")
        policy.require_thread(actor, prior.thread, manage=True)
        return prior.thread, prior
    thread = (
        GuidanceThread.objects.select_for_update(of=("self",))
        .filter(kind=ThreadKind.OFFICE, status=ThreadStatus.OPEN, student=student)
        .first()
    )
    if thread is None:
        affiliation = (
            StudentAffiliation.objects.select_related("college__campus")
            .filter(student=student)
            .first()
        )
        resolution = resolve_default_counselor_for_student(student)
        if (
            affiliation is None
            or resolution.counselor is None
            or not resolution.counselor.has_capability("guidance_messages.manage")
            or affiliation.college_id
            not in resolve_operational_responsibility_scope(resolution.counselor).college_ids
        ):
            raise MessagesConflict("Guidance Office routing is currently unavailable.")
        thread = GuidanceThread.objects.create(
            kind=ThreadKind.OFFICE,
            student=student,
            routing_college=affiliation.college,
            assigned_to=resolution.counselor,
            created_by=actor,
        )
        policy.require_thread(actor, thread, manage=True)
        _audit(
            actor,
            GUIDANCE_MESSAGES_THREAD_CREATED,
            thread,
            context=context,
            routing_college_id=str(thread.routing_college_id),
        )
    message = _send_locked(
        actor=actor, thread=thread, client_message_id=client_message_id, body=body, context=context
    )
    return thread, message


@transaction.atomic
def open_counseling_thread(*, actor, appointment_id, client_message_id, body, context=None):
    actor = policy.current_actor(actor, lock=True)
    policy.require_actor(actor, manage=True)
    appointment = (
        Appointment.objects.select_related("student__role", "provider__role", "service")
        .select_for_update(of=("self",))
        .filter(pk=appointment_id)
        .first()
    )
    if appointment is None:
        raise ThreadNotFound()
    thread = (
        GuidanceThread.objects.select_for_update(of=("self",))
        .filter(relationship_appointment=appointment)
        .first()
    )
    if thread is not None:
        policy.require_thread(actor, thread, manage=True)
    else:
        if not policy.eligible_relationship(appointment) or not (
            (actor.role.code == "STUDENT" and actor.pk == appointment.student_id)
            or (actor.role.code == "COUNSELOR" and actor.pk == appointment.provider_id)
        ):
            raise ThreadNotFound()
        thread = GuidanceThread.objects.create(
            kind=ThreadKind.COUNSELING,
            student=appointment.student,
            counselor=appointment.provider,
            relationship_appointment=appointment,
            created_by=actor,
        )
        _audit(
            actor,
            GUIDANCE_MESSAGES_THREAD_CREATED,
            thread,
            context=context,
            appointment_id=str(appointment.pk),
        )
    message = _send_locked(
        actor=actor, thread=thread, client_message_id=client_message_id, body=body, context=context
    )
    return thread, message


@transaction.atomic
def mark_read(*, actor, thread_id, sequence):
    actor = policy.current_actor(actor)
    thread = _lock_thread(actor, thread_id)
    if type(sequence) is not int or not 0 <= sequence <= thread.last_sequence:
        raise InvalidMessageInput(
            "Read sequence must be between zero and the latest Message sequence."
        )
    state, _ = GuidanceThreadReadState.objects.get_or_create(thread=thread, user=actor)
    if sequence > state.last_read_sequence:
        state.last_read_sequence = sequence
        state.save(update_fields=("last_read_sequence", "updated_at"))
        publish_to_user_on_commit(actor.pk, "messages.thread_changed", {"thread_id": thread.pk})
    return state


@transaction.atomic
def set_status(*, actor, thread_id, resolved, context=None):
    actor = policy.current_actor(actor, lock=True)
    snapshot = get_thread(actor=actor, thread_id=thread_id)
    policy.require_thread(actor, snapshot, manage=True, staff_only=True)
    User.objects.select_for_update(of=("self",), no_key=True).get(pk=snapshot.student_id)
    thread = _lock_thread(actor, thread_id, staff_only=True)
    status = ThreadStatus.RESOLVED if resolved else ThreadStatus.OPEN
    if thread.status == status:
        return thread
    if not resolved and thread.kind == ThreadKind.OFFICE:
        # The Student lock serializes Office creation and reopening.
        if (
            GuidanceThread.objects.filter(
                kind=ThreadKind.OFFICE, status=ThreadStatus.OPEN, student_id=thread.student_id
            )
            .exclude(pk=thread.pk)
            .exists()
        ):
            raise MessagesConflict("This Student already has an open Guidance Office thread.")
    thread.status = status
    thread.resolved_by = actor if resolved else None
    thread.resolved_at = timezone.now() if resolved else None
    thread.save(update_fields=("status", "resolved_by", "resolved_at", "updated_at"))
    action = GUIDANCE_MESSAGES_THREAD_RESOLVED if resolved else GUIDANCE_MESSAGES_THREAD_REOPENED
    _audit(actor, action, thread, context=context)
    _changed(thread)
    return thread


@transaction.atomic
def assign_handler(*, actor, thread_id, handler_id, context=None):
    actor = policy.current_actor(actor)
    thread = _lock_thread(actor, thread_id, staff_only=True)
    if thread.kind != ThreadKind.OFFICE:
        raise ThreadNotFound()
    handler = User.objects.select_related("role").filter(pk=handler_id, is_active=True).first()
    if handler is None or handler.role.code not in policy.STAFF_ROLES:
        raise InvalidMessageInput("Choose an eligible Guidance handler.")
    try:
        policy.require_thread(handler, thread, manage=True, staff_only=True)
    except ThreadNotFound:
        raise InvalidMessageInput("Choose an eligible Guidance handler.") from None
    previous = thread.assigned_to_id
    if previous != handler.pk:
        thread.assigned_to = handler
        thread.save(update_fields=("assigned_to", "updated_at"))
        _audit(
            actor,
            GUIDANCE_MESSAGES_THREAD_ASSIGNED,
            thread,
            context=context,
            previous_handler_id=str(previous) if previous else None,
            handler_id=str(handler.pk),
        )
        _changed(thread)
    return thread


def eligible_students(*, actor, **query):
    actor = policy.current_actor(actor)
    policy.require_actor(actor, manage=True, staff_only=True)
    return list_scoped_operational_students(
        college_ids=resolve_operational_responsibility_scope(actor).college_ids, **query
    )


def recipient_options(*, actor, page=1, page_size=DEFAULT_PAGE_SIZE):
    _pagination(page, page_size)
    actor = policy.current_actor(actor)
    policy.require_actor(actor, manage=True)
    if actor.role.code != "STUDENT":
        raise ThreadNotFound()
    query = (
        Appointment.objects.select_related("student__role", "provider__role", "service")
        .filter(
            student=actor,
            service__code=COUNSELING_SERVICE_CODE,
            status__in=policy.RELATIONSHIP_STATUSES,
            provider__is_active=True,
            provider__role__code="COUNSELOR",
        )
        .order_by("-starts_at", "-id")
    )
    # Bound each page even when a provider capability was overridden. Such a row is
    # omitted; pagination still advances through the canonical Appointment directory.
    offset = (page - 1) * page_size
    rows = list(query[offset : offset + page_size + 1])
    return [item for item in rows[:page_size] if policy.eligible_relationship(item)], len(
        rows
    ) > page_size
