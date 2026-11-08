"""PostgreSQL is authoritative. Every success audit shares the mutation transaction."""

from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import (
    BigIntegerField,
    Count,
    Exists,
    Max,
    OuterRef,
    Q,
    Subquery,
    Value,
)
from django.db.models.functions import Coalesce
from django.utils import timezone

from compass.accounts.models import User
from compass.accounts.services import effective_capabilities
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
from compass.common.rate_limit import RateLimitPolicy, RateLimitUnavailable, RedisRateLimiter
from compass.counseling.case_communication import authorize_case_coordination
from compass.counseling.continuity_models import CounselorCaseContinuityGrant
from compass.counseling.continuity_policy import ContinuityError
from compass.operational_students import list_scoped_operational_students
from compass.organization.access_scope import (
    resolve_general_guidance_college_scope,
    resolve_operational_responsibility_scope,
)
from compass.organization.integrity import catalog_dependent_write
from compass.organization.services import resolve_default_counselor_for_student
from compass.realtime.publish import publish_to_user, publish_to_user_on_commit
from compass.referrals.models import Referral
from compass.referrals.services import accessible_referrals, faculty_coordination_referral
from compass.service_catalog.canonical import COUNSELING_SERVICE_CODE
from compass.student_academics.reads import get_current_placement

from . import content, policy
from .errors import (
    CaseCoordinationEnded,
    InvalidMessageInput,
    MessagesConflict,
    MessagesPermissionDenied,
    ReferralVoided,
    ThreadNotFound,
)
from .models import (
    GuidanceMessage,
    GuidanceThread,
    GuidanceThreadReadState,
    ThreadKind,
    ThreadStatus,
)

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50
MAX_OPEN_FACULTY_INQUIRIES = 5
COUNSELOR_DIRECT_VIEW = "guidance_messages.counselor_direct.view"
COUNSELOR_DIRECT_MANAGE = "guidance_messages.counselor_direct.manage"
CASE_COORDINATION_MANAGE = "guidance_messages.case_coordination.manage"
MAX_PEER_SEARCH_LENGTH = 160


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


SEEN_BY_PERSON = "PERSON"
SEEN_BY_OFFICE = "OFFICE"


def thread_receipt(thread, actor):
    """The Seen this reader may be shown for `thread`, as `(scope, sequence)` (GMSG-6).

    Seen is derived only from read cursors, and a cursor moves only through `mark_read`, which the
    portal calls while the conversation is open in a visible tab with its newest Message in view.
    Nothing here claims delivery. A pair sees the other person's cursor. A requester sees
    "Seen by Guidance Office": the furthest cursor any Office reader reached (D-GMSG-03 option b,
    provisional). Because every such cursor was produced by an authorized read, an Office Seen does
    not revert when handling changes. Office staff see the Student's own cursor in a Student Office
    thread only (D-GMSG-04, provisional); everything else returns `(None, None)`, which the portal
    renders as no receipt at all rather than "not seen".
    """
    if thread.kind in policy.PAIR_KINDS:
        return SEEN_BY_PERSON, thread.others_last_read_sequence
    if thread.kind in policy.REQUESTER_KINDS:
        if actor.pk == policy.requester_id(thread):
            return SEEN_BY_OFFICE, thread.others_last_read_sequence
        if thread.kind in policy.REQUESTER_RECEIPT_KINDS:
            return SEEN_BY_PERSON, thread.student_last_read_sequence
    return None, None


def _directory(query, actor):
    cursor = GuidanceThreadReadState.objects.filter(
        thread_id=OuterRef("pk"), user_id=actor.pk
    ).values("last_read_sequence")[:1]
    others = (
        GuidanceThreadReadState.objects.filter(thread_id=OuterRef("pk"))
        .exclude(user_id=actor.pk)
        .order_by()
        .values("thread_id")
        .annotate(furthest=Max("last_read_sequence"))
        .values("furthest")
    )
    student_cursor = GuidanceThreadReadState.objects.filter(
        thread_id=OuterRef("pk"), user_id=OuterRef("student_id")
    ).values("last_read_sequence")[:1]
    query = query.annotate(
        own_last_read_sequence=Coalesce(Subquery(cursor), Value(0), output_field=BigIntegerField()),
        others_last_read_sequence=Coalesce(
            Subquery(others), Value(0), output_field=BigIntegerField()
        ),
        student_last_read_sequence=Coalesce(
            Subquery(student_cursor), Value(0), output_field=BigIntegerField()
        ),
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
    return query.select_related(
        "student",
        "counselor",
        "assigned_to",
        "routing_college",
        "requester",
        "relationship_referral",
        "direct_first_user",
        "direct_second_user",
        "student_subject",
    ).annotate(own_unread_count=Coalesce(Subquery(unread), Value(0)))


def list_threads(*, actor, page=1, page_size=DEFAULT_PAGE_SIZE):
    _pagination(page, page_size)
    actor = policy.current_actor(actor)
    query = _directory(policy.authorized_threads(actor), actor).order_by("-last_message_at", "-id")
    offset = (page - 1) * page_size
    rows = list(query[offset : offset + page_size + 1])
    return rows[:page_size], len(rows) > page_size


def count_unread_conversations(*, actor) -> int:
    actor = policy.current_actor(actor)
    cursor = GuidanceThreadReadState.objects.filter(
        thread_id=OuterRef("pk"), user_id=actor.pk
    ).values("last_read_sequence")[:1]
    threads = policy.authorized_threads(actor).annotate(
        own_last_read_sequence=Coalesce(Subquery(cursor), Value(0), output_field=BigIntegerField())
    )
    has_unread = GuidanceMessage.objects.filter(
        thread_id=OuterRef("pk"),
        sequence__gt=OuterRef("own_last_read_sequence"),
    ).exclude(sender_id=actor.pk)
    return threads.filter(Exists(has_unread)).count()


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


def _locked_referral_for(thread):
    """Lock the source Referral and refuse a voided one. Called after the thread lock.

    `void_referral` locks the same row, so a send and a void serialize here. Replay is checked
    before this guard: returning a recorded Message is history, not a new send.
    """
    if thread.relationship_referral_id is None:
        raise ThreadNotFound()
    referral = (
        Referral.objects.select_for_update(of=("self",))
        .filter(pk=thread.relationship_referral_id)
        .first()
    )
    if referral is None:
        raise ThreadNotFound()
    if referral.voided_at is not None:
        raise ReferralVoided()
    return referral


def _send_locked(*, actor, thread, client_message_id, body, context):
    policy.require_thread(actor, thread, manage=True)
    _client_id(client_message_id)
    replay = _replay(actor, client_message_id, thread.pk)
    if replay is not None:
        return replay
    if thread.status != ThreadStatus.OPEN:
        raise MessagesConflict("This Guidance thread is resolved.")
    if thread.kind == ThreadKind.REFERRAL_COORDINATION:
        _locked_referral_for(thread)
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


def _case_peer(grant, actor):
    """The other Counselor of the exact pair, or None when there is no authorized pair."""
    if grant is None:
        return None
    peer_id = (
        grant.receiving_counselor_id
        if actor.pk == grant.original_counselor_id
        else grant.original_counselor_id
    )
    if peer_id is None:
        return None
    return User.objects.select_related("role").filter(pk=peer_id).first()


def _authorized_case_grant(*, actor, grant_id, lock=False):
    """Translate the single predicate's non-disclosing refusals into messaging errors."""
    try:
        return authorize_case_coordination(actor=actor, grant_id=grant_id, lock=lock)
    except ContinuityError as exc:
        if exc.code == "continuity_case_access_ended":
            raise CaseCoordinationEnded() from None
        raise ThreadNotFound() from None


@transaction.atomic
def send_message(*, actor, thread_id, client_message_id, body, context=None):
    # NO KEY UPDATE serializes the sender without blocking peer foreign-key checks
    # during concurrent thread creation. Consistent sender -> thread locking serializes
    # reuse of a client ID across
    # different threads. Database uniqueness remains the final independent guard.
    actor = policy.current_actor(actor, lock=True)
    # Grant -> thread: read the immutable case link without a lock, then take the grant lock
    # before the thread lock so revocation and a send serialize on the grant row.
    case_grant_id = (
        GuidanceThread.objects.filter(pk=thread_id)
        .values_list("relationship_case_grant_id", flat=True)
        .first()
    )
    if case_grant_id is not None:
        _authorized_case_grant(actor=actor, grant_id=case_grant_id, lock=True)
    thread = _lock_thread(actor, thread_id)
    return _send_locked(
        actor=actor, thread=thread, client_message_id=client_message_id, body=body, context=context
    )


@catalog_dependent_write
@transaction.atomic
def open_office_thread(*, actor, client_message_id, body, student_id=None, context=None):
    actor = policy.current_actor(actor, lock=True)
    policy.require_actor(
        actor, manage=True, staff_only=student_id is not None, kind=ThreadKind.OFFICE
    )
    _client_id(client_message_id)
    if actor.role.code == "STUDENT":
        student = actor
    else:
        scope = resolve_general_guidance_college_scope(actor)
        student = (
            User.objects.select_related("role")
            .select_for_update(of=("self",), no_key=True)
            .filter(
                pk=student_id,
                student_academic_profile__current_college_id__in=scope.college_ids,
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
        placement = get_current_placement(student_id=student.pk)
        resolution = resolve_default_counselor_for_student(student)
        if (
            placement is None
            or resolution.counselor is None
            or not resolution.counselor.has_capability("guidance_messages.manage")
            or placement.college.id
            not in resolve_operational_responsibility_scope(resolution.counselor).college_ids
        ):
            raise MessagesConflict("Guidance Office routing is currently unavailable.")
        thread = GuidanceThread.objects.create(
            kind=ThreadKind.OFFICE,
            student=student,
            routing_college_id=placement.college.id,
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
    policy.require_actor(actor, manage=True, kind=ThreadKind.COUNSELING)
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
        if not policy.eligible_relationship(appointment) or not policy.relationship_participant(
            actor, appointment
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
def open_faculty_inquiry(*, actor, client_message_id, body, context=None):
    actor = policy.current_actor(actor, lock=True)
    policy.require_actor(actor, manage=True, kind=ThreadKind.FACULTY_INQUIRY)
    _client_id(client_message_id)
    prior = (
        GuidanceMessage.objects.filter(sender=actor, client_message_id=client_message_id)
        .select_related("thread")
        .first()
    )
    if prior is not None:
        if prior.thread.kind != ThreadKind.FACULTY_INQUIRY:
            raise MessagesConflict("client_message_id has already been used for another thread.")
        policy.require_thread(actor, prior.thread, manage=True)
        return prior.thread, prior
    if not policy.has_intake_staff():
        raise MessagesConflict("Guidance Office intake is currently unavailable.")
    open_count = GuidanceThread.objects.filter(
        kind=ThreadKind.FACULTY_INQUIRY, status=ThreadStatus.OPEN, requester=actor
    ).count()
    if open_count >= MAX_OPEN_FACULTY_INQUIRIES:
        raise MessagesConflict("You already have 5 open Guidance Office inquiries.")
    thread = GuidanceThread.objects.create(
        kind=ThreadKind.FACULTY_INQUIRY, requester=actor, created_by=actor
    )
    policy.require_thread(actor, thread, manage=True)
    _audit(actor, GUIDANCE_MESSAGES_THREAD_CREATED, thread, context=context)
    message = _send_locked(
        actor=actor, thread=thread, client_message_id=client_message_id, body=body, context=context
    )
    return thread, message


def appointment_context(*, actor, appointment_id):
    """Resolve an Appointment's Counseling thread for a contextual surface (ADR-103).

    An existing thread is authorized only by its persisted participants, never by the
    Appointment's current state, so cancellation keeps and reassignment never transfers it.
    Without one, the actor must be able to start it now under the same rules as
    `open_counseling_thread`, which revalidates at the first send. Anything else is concealed.
    Returns `(thread, can_start)`; no Message content is read.
    """
    actor = policy.current_actor(actor)
    existing = (
        GuidanceThread.objects.filter(relationship_appointment_id=appointment_id)
        .values_list("pk", flat=True)
        .first()
    )
    if existing is not None:
        return get_thread(actor=actor, thread_id=existing), False
    try:
        policy.require_actor(actor, manage=True, kind=ThreadKind.COUNSELING)
    except MessagesPermissionDenied:
        raise ThreadNotFound() from None
    appointment = (
        Appointment.objects.select_related("student__role", "provider__role", "service")
        .filter(pk=appointment_id)
        .first()
    )
    if (
        appointment is None
        or not policy.eligible_relationship(appointment)
        or not policy.relationship_participant(actor, appointment)
    ):
        raise ThreadNotFound()
    return None, True


def case_coordination_context(*, actor, grant_id):
    """Resolve one grant's case conversation for a contextual surface (ADR-103).

    The live Counseling predicate decides everything: participants, purpose, policy digests,
    window, revocation and current source state. A live grant returns its thread (or `can_start`);
    an ended grant returns `access_ended` only to the exact pair, and every other refusal is
    concealed as a missing thread. The Student is never returned here.
    Returns `(thread, can_start, access_ended, counterpart)`.
    """
    actor = policy.current_actor(actor)
    try:
        policy.require_actor(actor, kind=ThreadKind.COUNSELOR_CASE_COORDINATION, staff_only=True)
    except MessagesPermissionDenied:
        raise ThreadNotFound() from None
    try:
        grant = authorize_case_coordination(actor=actor, grant_id=grant_id)
    except ContinuityError as exc:
        if exc.code != "continuity_case_access_ended":
            raise ThreadNotFound() from None
        # The pair may learn that its own coordination ended; nobody else may learn it existed.
        pair_grant = (
            CounselorCaseContinuityGrant.objects.filter(pk=grant_id)
            .filter(Q(original_counselor_id=actor.pk) | Q(receiving_counselor_id=actor.pk))
            .first()
        )
        return None, False, True, _case_peer(pair_grant, actor)
    thread = (
        GuidanceThread.objects.filter(
            kind=ThreadKind.COUNSELOR_CASE_COORDINATION,
            relationship_case_grant_id=grant.pk,
            student_subject_id=grant.student_id,
        )
        .values_list("pk", flat=True)
        .first()
    )
    can_start = thread is None and actor.has_capability(CASE_COORDINATION_MANAGE)
    return (
        get_thread(actor=actor, thread_id=thread) if thread is not None else None,
        can_start,
        False,
        _case_peer(grant, actor),
    )


def referral_context(*, actor, referral_id):
    """Resolve a Referral's coordination thread for a contextual surface.

    An existing thread survives void and is authorized by its persisted participants. Starting
    is offered only to the Faculty submitter with manage authority on a non-voided Referral.
    Returns `(thread, can_start)`; no Message content or Referral form data is read. Both the
    existing-thread and the not-yet-started answer require the actor's current Referral capability.
    """
    actor = policy.current_actor(actor)
    if actor.role.code == "FACULTY":
        # The no-thread answer ("can_start") must not disclose an in-scope Referral to a Faculty
        # member whose current capability no longer includes reading their own submissions.
        try:
            policy.require_actor(actor, kind=ThreadKind.REFERRAL_COORDINATION)
        except MessagesPermissionDenied:
            raise ThreadNotFound() from None
        referral = faculty_coordination_referral(actor=actor, referral_id=referral_id)
        if referral is None:
            raise ThreadNotFound()
    elif actor.role.code in policy.STAFF_ROLES:
        try:
            policy.require_actor(actor, kind=ThreadKind.REFERRAL_COORDINATION)
        except MessagesPermissionDenied:
            raise ThreadNotFound() from None
        referral = accessible_referrals(actor).filter(pk=referral_id).first()
        if referral is None:
            raise ThreadNotFound()
    else:
        raise ThreadNotFound()
    existing = (
        GuidanceThread.objects.filter(
            kind=ThreadKind.REFERRAL_COORDINATION, relationship_referral_id=referral.pk
        )
        .values_list("pk", flat=True)
        .first()
    )
    if existing is not None:
        return get_thread(actor=actor, thread_id=existing), False
    if referral.voided_at is not None:
        raise ThreadNotFound()
    can_start = (
        actor.role.code == "FACULTY"
        and "guidance_messages.referral_manage_self" in effective_capabilities(actor)
    )
    return None, can_start


@transaction.atomic
def open_referral_thread(*, actor, referral_id, client_message_id, body, context=None):
    actor = policy.current_actor(actor, lock=True)
    policy.require_actor(actor, manage=True, kind=ThreadKind.REFERRAL_COORDINATION)
    if actor.role.code != "FACULTY":
        raise MessagesPermissionDenied()
    _client_id(client_message_id)
    referral = faculty_coordination_referral(actor=actor, referral_id=referral_id)
    if referral is None:
        raise ThreadNotFound()
    prior = (
        GuidanceMessage.objects.filter(sender=actor, client_message_id=client_message_id)
        .select_related("thread")
        .first()
    )
    if prior is not None:
        if (
            prior.thread.kind != ThreadKind.REFERRAL_COORDINATION
            or prior.thread.relationship_referral_id != referral.pk
        ):
            raise MessagesConflict("client_message_id has already been used for another thread.")
        policy.require_thread(actor, prior.thread, manage=True)
        return prior.thread, prior
    if referral.voided_at is not None:
        raise ReferralVoided()
    thread = (
        GuidanceThread.objects.select_for_update(of=("self",))
        .filter(kind=ThreadKind.REFERRAL_COORDINATION, relationship_referral_id=referral.pk)
        .first()
    )
    created = thread is None
    if created:
        try:
            with transaction.atomic():
                thread = GuidanceThread.objects.create(
                    kind=ThreadKind.REFERRAL_COORDINATION,
                    requester=actor,
                    relationship_referral=referral,
                    student_subject=referral.student,
                    routing_college_id=referral.student_college_at_submission_id,
                    created_by=actor,
                )
        except IntegrityError:
            # The partial unique index on relationship_referral is the creation guard: a
            # concurrent open already committed the thread, so reuse it instead of failing.
            thread = (
                GuidanceThread.objects.select_for_update(of=("self",))
                .filter(
                    kind=ThreadKind.REFERRAL_COORDINATION,
                    relationship_referral_id=referral.pk,
                )
                .first()
            )
            if thread is None:
                raise
            created = False
    policy.require_thread(actor, thread, manage=True)
    if created:
        _audit(
            actor,
            GUIDANCE_MESSAGES_THREAD_CREATED,
            thread,
            context=context,
            referral_id=str(referral.pk),
        )
    message = _send_locked(
        actor=actor, thread=thread, client_message_id=client_message_id, body=body, context=context
    )
    return thread, message


def _direct_pair_ids(actor_id, peer_id):
    """Validate the peer shape and return the pair in canonical ascending UUID order."""
    if not isinstance(peer_id, UUID) or peer_id == actor_id:
        raise ThreadNotFound()
    return tuple(sorted((actor_id, peer_id)))


def _lock_direct_pair(*, actor_id, peer_id):
    """Lock both participants in one global order, including the actor.

    `open_counselor_direct_thread` must not pre-lock the actor: A->B and B->A would otherwise take
    the locks in opposite order. Locking the canonical pair here serializes both directions and
    covers a different pair that shares one participant, because the ordering is global.
    """
    first_id, second_id = _direct_pair_ids(actor_id, peer_id)
    first = (
        User.objects.select_for_update(of=("self",), no_key=True)
        .select_related("role")
        .filter(pk=first_id)
        .first()
    )
    second = (
        User.objects.select_for_update(of=("self",), no_key=True)
        .select_related("role")
        .filter(pk=second_id)
        .first()
    )
    if first is None or second is None:
        raise ThreadNotFound()
    actor = first if first.pk == actor_id else second
    peer = second if first.pk == actor_id else first
    for user in (actor, peer):
        if not user.is_active or user.role.code != "COUNSELOR":
            raise ThreadNotFound()
    if not peer.has_capability(COUNSELOR_DIRECT_MANAGE):
        raise ThreadNotFound()
    return actor, peer, first, second


@transaction.atomic
def open_counselor_direct_thread(*, actor, peer_id, client_message_id, body, context=None):
    actor = policy.current_actor(actor)  # deliberately not locked; the pair lock includes the actor
    policy.require_actor(actor, manage=True, kind=ThreadKind.COUNSELOR_DIRECT)
    _client_id(client_message_id)
    pair = _direct_pair_ids(actor.pk, peer_id)
    prior = (
        GuidanceMessage.objects.filter(sender=actor, client_message_id=client_message_id)
        .select_related("thread")
        .first()
    )
    if prior is not None:
        if prior.thread.kind != ThreadKind.COUNSELOR_DIRECT or {
            prior.thread.direct_first_user_id,
            prior.thread.direct_second_user_id,
        } != set(pair):
            raise MessagesConflict("client_message_id has already been used for another thread.")
        policy.require_thread(actor, prior.thread, manage=True)
        return prior.thread, prior
    actor, peer, first, second = _lock_direct_pair(actor_id=actor.pk, peer_id=peer_id)
    thread = (
        GuidanceThread.objects.select_for_update(of=("self",))
        .filter(
            kind=ThreadKind.COUNSELOR_DIRECT,
            direct_first_user_id=first.pk,
            direct_second_user_id=second.pk,
        )
        .first()
    )
    created = thread is None
    if created:
        try:
            with transaction.atomic():
                thread = GuidanceThread.objects.create(
                    kind=ThreadKind.COUNSELOR_DIRECT,
                    direct_first_user=first,
                    direct_second_user=second,
                    created_by=actor,
                )
        except IntegrityError:
            # The partial unique index on the canonical pair is the independent creation guard:
            # a concurrent open committed first, so reuse that thread.
            thread = (
                GuidanceThread.objects.select_for_update(of=("self",))
                .filter(
                    kind=ThreadKind.COUNSELOR_DIRECT,
                    direct_first_user_id=first.pk,
                    direct_second_user_id=second.pk,
                )
                .first()
            )
            if thread is None:
                raise
            created = False
    policy.require_thread(actor, thread, manage=True)
    if created:
        _audit(
            actor,
            GUIDANCE_MESSAGES_THREAD_CREATED,
            thread,
            context=context,
            peer_id=str(peer.pk),
        )
    message = _send_locked(
        actor=actor, thread=thread, client_message_id=client_message_id, body=body, context=context
    )
    return thread, message


@catalog_dependent_write
@transaction.atomic
def open_case_coordination_thread(*, actor, grant_id, client_message_id, body, context=None):
    """Open (or continue) the one conversation on a live case-coordination grant.

    Lock order is grant -> thread, the same order `send_message` uses, so a revocation and a send
    serialize on the grant row. The predicate is the only participant/window/policy authority.
    """
    actor = policy.current_actor(actor, lock=True)
    try:
        policy.require_actor(
            actor, manage=True, kind=ThreadKind.COUNSELOR_CASE_COORDINATION, staff_only=True
        )
    except MessagesPermissionDenied:
        raise ThreadNotFound() from None
    _client_id(client_message_id)
    grant = _authorized_case_grant(actor=actor, grant_id=grant_id, lock=True)
    prior = (
        GuidanceMessage.objects.filter(sender=actor, client_message_id=client_message_id)
        .select_related("thread")
        .first()
    )
    if prior is not None:
        if (
            prior.thread.kind != ThreadKind.COUNSELOR_CASE_COORDINATION
            or prior.thread.relationship_case_grant_id != grant.pk
        ):
            raise MessagesConflict("client_message_id has already been used for another thread.")
        policy.require_thread(actor, prior.thread, manage=True)
        return prior.thread, prior
    thread = (
        GuidanceThread.objects.select_for_update(of=("self",))
        .filter(
            kind=ThreadKind.COUNSELOR_CASE_COORDINATION,
            relationship_case_grant_id=grant.pk,
            student_subject_id=grant.student_id,
        )
        .first()
    )
    created = thread is None
    if created:
        try:
            with transaction.atomic():
                thread = GuidanceThread.objects.create(
                    kind=ThreadKind.COUNSELOR_CASE_COORDINATION,
                    relationship_case_grant=grant,
                    student_subject_id=grant.student_id,
                    created_by=actor,
                )
        except IntegrityError:
            # The partial unique index on (grant, Student subject) is the creation guard: a
            # concurrent open committed first, so reuse that thread.
            thread = (
                GuidanceThread.objects.select_for_update(of=("self",))
                .filter(
                    kind=ThreadKind.COUNSELOR_CASE_COORDINATION,
                    relationship_case_grant_id=grant.pk,
                    student_subject_id=grant.student_id,
                )
                .first()
            )
            if thread is None:
                raise
            created = False
    policy.require_thread(actor, thread, manage=True)
    if created:
        _audit(
            actor,
            GUIDANCE_MESSAGES_THREAD_CREATED,
            thread,
            context=context,
            relationship_case_grant_id=str(grant.pk),
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
    previous = state.last_read_sequence
    if sequence <= previous:
        return state
    receipt_moved = _receipt_moved(thread, actor, previous=previous, sequence=sequence)
    # D-GMSG-26: the cursor only ever moves forward, enforced by the database as well as by the
    # thread lock. A row that is already at or past `sequence` is left untouched.
    advanced = GuidanceThreadReadState.objects.filter(
        pk=state.pk, last_read_sequence__lt=sequence
    ).update(last_read_sequence=sequence, updated_at=timezone.now())
    state.refresh_from_db(fields=("last_read_sequence", "updated_at"))
    if advanced != 1:
        return state
    publish_to_user_on_commit(actor.pk, "messages.thread_changed", {"thread_id": thread.pk})
    if receipt_moved:
        thread_id, actor_id = thread.pk, actor.pk
        transaction.on_commit(lambda: _publish_receipt(thread_id, actor_id), robust=True)
    return state


def _receipt_moved(thread, actor, *, previous, sequence):
    """Whether advancing `actor` from `previous` to `sequence` changes a Seen someone is shown.

    Only the counterpart side can see this reader's cursor, and only for Messages that side sent,
    so a read that covers none of their Messages tells them nothing new. An Office reader moves the
    requester's "Seen by Guidance Office" only when they pass the furthest Office cursor so far.
    """
    messages = GuidanceMessage.objects.filter(thread_id=thread.pk)
    if thread.kind in policy.PAIR_KINDS:
        return (
            messages.filter(sequence__gt=previous, sequence__lte=sequence)
            .exclude(sender_id=actor.pk)
            .exists()
        )
    if thread.kind not in policy.REQUESTER_KINDS:
        return False
    requester = policy.requester_id(thread)
    if actor.pk == requester:
        if thread.kind not in policy.REQUESTER_RECEIPT_KINDS:
            return False
        return (
            messages.filter(sequence__gt=previous, sequence__lte=sequence)
            .exclude(sender_id=actor.pk)
            .exists()
        )
    office_furthest = (
        GuidanceThreadReadState.objects.filter(thread_id=thread.pk)
        .exclude(user_id=requester)
        .aggregate(furthest=Max("last_read_sequence"))["furthest"]
        or 0
    )
    floor = max(previous, office_furthest)
    if sequence <= floor:
        return False
    return messages.filter(sequence__gt=floor, sequence__lte=sequence, sender_id=requester).exists()


def _publish_receipt(thread_id, actor_id):
    thread = GuidanceThread.objects.select_related("relationship_case_grant").get(pk=thread_id)
    actor = User.objects.get(pk=actor_id)
    for user_id in policy.counterpart_recipient_ids(thread, actor):
        publish_to_user_on_commit(user_id, "messages.thread_changed", {"thread_id": thread.pk})


# D-GMSG-13 (provisional engineering default): at most one typing hint per reader per thread every
# three seconds. Portals expire the indicator locally after eight seconds without another hint.
TYPING_POLICY = RateLimitPolicy(name="guidance-messages-typing", limit=1, window_seconds=3)


def signal_typing(*, actor, thread_id):
    """Tell the other side that `actor` is writing now (GMSG-7). Returns whether a hint went out.

    Nothing is stored: no draft text, no typing row, no audit event. The hint is the registered,
    content-free `messages.typing_changed {thread_id}` and goes only to currently authorized
    counterparts, so the referred Student of a Referral conversation and other Office staff never
    receive it. A reader who may not send here gets the same refusal sending would give. A refused
    or unavailable rate limiter publishes nothing, because typing is advisory.
    """
    actor = policy.current_actor(actor)
    thread = (
        GuidanceThread.objects.select_related("relationship_referral", "relationship_case_grant")
        .filter(pk=thread_id)
        .first()
    )
    if thread is None:
        raise ThreadNotFound()
    policy.require_thread(actor, thread, manage=True)
    if thread.status != ThreadStatus.OPEN:
        raise MessagesConflict("This Guidance thread is resolved.")
    if thread.kind == ThreadKind.REFERRAL_COORDINATION:
        referral = thread.relationship_referral
        if referral is None:
            raise ThreadNotFound()
        if referral.voided_at is not None:
            raise ReferralVoided()
    try:
        allowed = (
            RedisRateLimiter.from_settings()
            .consume_with_failure_policy(TYPING_POLICY, f"{actor.pk}:{thread.pk}")
            .allowed
        )
    except RateLimitUnavailable:
        allowed = False
    if not allowed:
        return False
    sent = False
    for user_id in policy.counterpart_recipient_ids(thread, actor):
        sent = publish_to_user(user_id, "messages.typing_changed", {"thread_id": thread.pk}) or sent
    return sent


@catalog_dependent_write
@transaction.atomic
def set_status(*, actor, thread_id, resolved, context=None):
    actor = policy.current_actor(actor, lock=True)
    snapshot = get_thread(actor=actor, thread_id=thread_id)
    if snapshot.kind == ThreadKind.FACULTY_INQUIRY:
        policy.require_thread(actor, snapshot, manage=True)
        thread = _lock_thread(actor, thread_id)
    elif snapshot.kind == ThreadKind.REFERRAL_COORDINATION:
        policy.require_thread(actor, snapshot, manage=True)
        thread = _lock_thread(actor, thread_id)
        # A voided Referral makes its conversation read-only, including resolve and reopen.
        _locked_referral_for(thread)
    elif snapshot.kind == ThreadKind.COUNSELOR_DIRECT:
        policy.require_thread(actor, snapshot, manage=True)
        raise MessagesConflict("Counselor direct conversations stay open.")
    elif snapshot.kind == ThreadKind.COUNSELOR_CASE_COORDINATION:
        # Resolve/reopen is messaging-only: it never writes back to the Counseling grant, and the
        # live predicate refuses both once coordination has ended.
        policy.require_thread(actor, snapshot, manage=True)
        thread = _lock_thread(actor, thread_id)
    else:
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
    # The final authority: an earlier eligible-handler list may be stale by now.
    handler = User.objects.select_related("role").filter(pk=handler_id, is_active=True).first()
    if handler is None or not policy.eligible_handler(handler, thread):
        raise InvalidMessageInput("Choose an eligible Guidance handler.")
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


MAX_HANDLER_SEARCH_LENGTH = 160


def eligible_handlers(*, actor, thread_id, search=None, page=1, page_size=DEFAULT_PAGE_SIZE):
    """Current eligible handlers for one Office thread the actor manages (ADR-104).

    Advisory discovery only: `assign_handler` revalidates. Search matches the staff display name
    only. The candidate set is finite (the thread College's Counselors, Heads and their staff).
    """
    _pagination(page, page_size)
    if search is not None and not isinstance(search, str):
        raise InvalidMessageInput("search must be text.")
    term = (search or "").strip().casefold()
    if len(term) > MAX_HANDLER_SEARCH_LENGTH:
        raise InvalidMessageInput(f"search must be at most {MAX_HANDLER_SEARCH_LENGTH} characters.")
    actor = policy.current_actor(actor)
    thread = GuidanceThread.objects.filter(pk=thread_id).first()
    if thread is None:
        raise ThreadNotFound()
    policy.require_thread(actor, thread, manage=True, staff_only=True)
    if thread.kind != ThreadKind.OFFICE:
        raise ThreadNotFound()
    handlers = sorted(
        (
            user
            for user in policy.eligible_handlers(thread)
            if term in user.get_full_name().casefold()
        ),
        key=lambda user: (user.get_full_name().casefold(), str(user.pk)),
    )
    offset = (page - 1) * page_size
    return handlers[offset : offset + page_size], len(handlers) > offset + page_size


def counselor_peers(*, actor, search=None, page=1, page_size=DEFAULT_PAGE_SIZE):
    """Bounded, name-only peer directory for starting a direct conversation."""
    _pagination(page, page_size)
    actor = policy.current_actor(actor)
    policy.require_actor(actor, manage=True, kind=ThreadKind.COUNSELOR_DIRECT)
    if search is not None and not isinstance(search, str):
        raise InvalidMessageInput("search must be text.")
    term = (search or "").strip()
    if len(term) > MAX_PEER_SEARCH_LENGTH:
        raise InvalidMessageInput(f"search must be at most {MAX_PEER_SEARCH_LENGTH} characters.")
    query = User.objects.filter(is_active=True, role__code="COUNSELOR").exclude(pk=actor.pk)
    if term:
        query = query.filter(
            Q(first_name__icontains=term)
            | Q(middle_name__icontains=term)
            | Q(last_name__icontains=term)
        )
    rows = sorted(
        (
            user
            for user in query.select_related("role")
            if user.has_capability(COUNSELOR_DIRECT_MANAGE)
        ),
        key=lambda user: (user.get_full_name().casefold(), str(user.pk)),
    )
    offset = (page - 1) * page_size
    return rows[offset : offset + page_size], len(rows) > offset + page_size


def eligible_students(*, actor, **query):
    actor = policy.current_actor(actor)
    policy.require_actor(actor, manage=True, staff_only=True)
    return list_scoped_operational_students(
        college_ids=resolve_general_guidance_college_scope(actor).college_ids, **query
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
