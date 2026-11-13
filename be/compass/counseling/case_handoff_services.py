"""Case-first protected handoff operations; bodies leave only after durable commit."""

import hashlib
import json

from django.db import OperationalError, connection, transaction
from django.utils import timezone

from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.authentication.models import AuthSession
from compass.counseling.continuity_rules import is_head

from . import case_continuity_rules as rules
from . import case_handoff_content as content
from . import case_transfer_services as transfers
from .case_handoff_models import (
    CaseHandoffUnavailableReason,
    CounselingCaseHandoff,
    CounselingCaseHandoffAddendum,
    CounselingCaseHandoffException,
    CounselingCaseHandoffReceipt,
)
from .case_transfer_projections import person


def plan_digest(item):
    tasks = list(
        item.task_plans.order_by("task_id").values(
            "task_id",
            "task_version",
            "disposition",
            "source_kind",
            "source_id",
            "assignee_id",
            "due_at",
            "successor_title_ciphertext",
            "successor_due_at",
        )
    )
    appointments = list(
        item.appointment_plans.order_by("link_id").values(
            "link_id", "disposition", "retention_reason", "provider_id", "starts_at", "ends_at"
        )
    )
    value = {
        "receiver": item.receiving_counselor_id,
        "reason": item.reason,
        "owner": item.outgoing_counselor_id,
        "tasks": tasks,
        "appointments": appointments,
    }
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def work_snapshot(item):
    tasks = []
    for plan in item.task_plans.select_related("task", "assignee"):
        incoming = plan.disposition in {"TRANSFER", "HAND_OVER_AS_NEW"}
        tasks.append(
            {
                "task_id": str(plan.task_id),
                "category": plan.task.category,
                "source_kind": plan.source_kind,
                "disposition": plan.disposition,
                "due_at": (
                    plan.successor_due_at if plan.disposition == "HAND_OVER_AS_NEW" else plan.due_at
                ).isoformat(),
                "responsible": person(item.receiving_counselor if incoming else plan.assignee),
            }
        )
    appointments = []
    for plan in item.appointment_plans.select_related("link__appointment__provider"):
        appointment = plan.link.appointment
        appointments.append(
            {
                "appointment_id": str(appointment.pk),
                "reference_code": appointment.reference_code,
                "starts_at": plan.starts_at.isoformat(),
                "ends_at": plan.ends_at.isoformat(),
                "disposition": plan.disposition,
                "responsible": person(
                    item.receiving_counselor
                    if plan.disposition == "REASSIGN"
                    else appointment.provider
                ),
            }
        )
    return json.loads(json.dumps({"tasks": tasks, "appointments": appointments}, default=str))


def may_write(actor, item, now=None):
    now = now or timezone.now()
    return bool(
        actor.pk == item.outgoing_counselor_id == item.case.primary_counselor_id
        and actor.pk != item.receiving_counselor_id
        and item.case.status == "ACTIVE"
        and item.state in {"PREPARED", "AUTHORIZED"}
        and rules.receiver_eligible(actor, now)
        and actor.has_capability("counseling.handoff.manage_own", at=now)
    )


def may_record_exception(actor, item, now=None):
    now = now or timezone.now()
    if (
        not is_head(actor)
        or not actor.is_active
        or not actor.has_capability("counseling.continuity.approve", at=now)
        or actor.pk == item.receiving_counselor_id
        or item.case.status != "ACTIVE"
        or item.case.primary_counselor_id != item.outgoing_counselor_id
        or item.state not in {"PREPARED", "AUTHORIZED"}
        or (item.case_handoff is not None and item.case_handoff.state == "SUBMITTED")
    ):
        return False
    try:
        route = rules.authorization_route(
            requester=item.prepared_by, receiver=item.receiving_counselor, case=item.case, now=now
        )
    except rules.CaseContinuityError:
        return False
    if route == "OWNER_TO_HEAD":
        return False
    return (
        actor.pk == item.prepared_by_id == item.outgoing_counselor_id
        if route == "DIRECT_OUTGOING_HEAD"
        else actor.pk not in {item.prepared_by_id, item.receiving_counselor_id}
    )


def may_read(actor, item, handoff, now=None):
    now = now or timezone.now()
    if actor.role.code != "COUNSELOR" or not actor.is_active:
        return False
    if (
        handoff.transfer_id != item.pk
        or handoff.case_id != item.case_id
        or handoff.student_id != item.case.student_id
        or handoff.author_id == handoff.receiving_counselor_id
    ):
        return False
    if (
        actor.pk == handoff.author_id
        and actor.has_capability("counseling.handoff.manage_own", at=now)
        and actor.has_capability("counseling.view_assigned", at=now)
    ):
        return True
    if (
        handoff.state != "SUBMITTED"
        or not actor.has_capability("counseling.handoff.read_received", at=now)
        or not actor.has_capability("counseling.view_assigned", at=now)
    ):
        return False
    if item.state == "ACCEPTED":
        return item.case.primary_counselor_id == actor.pk and item.case_handoff_id == handoff.pk
    return bool(
        rules.state_at(item, now) == "AUTHORIZED"
        and item.authorized_version == item.version
        and item.case.status == "ACTIVE"
        and item.case.primary_counselor_id == item.outgoing_counselor_id
        and actor.pk == item.receiving_counselor_id == handoff.receiving_counselor_id
        and rules.receiver_eligible(actor, now)
        and actor.has_capability("counseling.continuity.read_selected", at=now)
        and item.case_handoff_id == handoff.pk
        and handoff.plan_digest == plan_digest(item)
    )


def require_ready(item, *, new_submission=False, now=None, verify_content=False):
    if not new_submission and item.handoff_required_at is None:
        return  # A real offer submitted before CW-3b keeps its documented behavior.
    digest = plan_digest(item)
    handoff = item.case_handoff
    if handoff is not None and handoff.state == "SUBMITTED":
        if (
            handoff.transfer_id == item.pk
            and handoff.case_id == item.case_id
            and handoff.student_id == item.case.student_id
            and handoff.author_id == item.outgoing_counselor_id
            and handoff.receiving_counselor_id == item.receiving_counselor_id
            and handoff.plan_digest == digest
        ):
            if verify_content:
                content.read(handoff)
            return
    exception = item.handoff_exception
    if (
        exception is not None
        and exception.transfer_id == item.pk
        and exception.plan_digest == digest
    ):
        head = exception.recorded_by
        if item.state in {"ACCEPTED", "DECLINED", "CANCELLED"} or may_record_exception(
            head, item, now
        ):
            return
    rules.fail(
        "handoff_required",
        "Submit the structured handoff or have an eligible Head record why it is unavailable.",
    )


def metadata(item, actor, now=None):
    now = now or timezone.now()
    handoff = item.case_handoff
    value = None
    if handoff is not None:
        value = {
            "id": handoff.pk,
            "version": handoff.version,
            "state": handoff.state,
            "author": person(handoff.author),
            "submitted_at": handoff.submitted_at,
            "received_at": handoff.receipts.filter(reader_id=handoff.receiving_counselor_id)
            .values_list("received_at", flat=True)
            .first(),
        }
    exception = item.handoff_exception
    try:
        require_ready(item, new_submission=True, now=now)
        ready = True
    except rules.CaseContinuityError:
        ready = False
    readable = handoff is not None and may_read(actor, item, handoff, now)
    return {
        "handoff": value,
        "handoff_exception": {
            "reason": exception.reason,
            "recorded_by": person(exception.recorded_by),
            "recorded_at": exception.created_at,
        }
        if exception
        else None,
        "handoff_ready": ready,
        "handoff_required": item.handoff_required_at is not None,
        "can_write_handoff": may_write(actor, item, now)
        and (handoff is None or handoff.state == "DRAFT"),
        "can_read_handoff": readable,
        "can_record_handoff_exception": may_record_exception(actor, item, now),
    }


def invalidate(item, *, actor, context):
    if item.state not in {"PREPARED", "AUTHORIZED"}:
        return
    item.state = "PREPARED"
    item.submitted_at = item.authorized_at = item.authorized_by = item.authorized_version = (
        item.review_expires_at
    ) = None
    item.authorization_route = ""
    item.independent_authorization = True
    item.handoff_required_at = item.handoff_required_at or timezone.now()
    transfers._save(item)
    transfers.audit(item, "updated", actor=actor, context=context)


def save_prepared_draft(item, *, actor, sections, context):
    """Attach the form's draft inside the case preparation transaction, without returning a body."""
    if not may_write(actor, item):
        rules.fail(
            "handoff_write_denied",
            "Office preparation cannot include counseling handoff content.",
            403,
        )
    handoff = CounselingCaseHandoff(
        transfer=item,
        case=item.case,
        student_id=item.case.student_id,
        author=actor,
        receiving_counselor=item.receiving_counselor,
        plan_digest=plan_digest(item),
    )
    handoff.content_ciphertext = content.encrypt(handoff, sections, work_snapshot(item))
    handoff.save(force_insert=True)
    item.case_handoff = handoff
    item.save(update_fields=["case_handoff"])
    audit(actor, handoff, "draft_saved", context, transfer=item)


def audit(actor, handoff, verb, context, *, transfer, extra=None):
    context = context or AuditContext.user(actor)
    if context.actor_type != "USER" or context.actor.pk != actor.pk:
        raise ValueError("Case handoff Audit actor must match")
    record_event(
        context=context,
        action="counseling.case_handoff." + verb,
        outcome=AuditOutcome.SUCCESS,
        target_type="counseling.counselingcasehandoffexception"
        if verb == "unavailable_recorded"
        else "counseling.counselingcasehandoff",
        target_id=handoff.pk,
        metadata={
            "transfer_id": str(transfer.pk),
            "case_id": str(transfer.case_id),
            "student_id": str(transfer.case.student_id),
            "version": transfer.version,
            **(extra or {}),
        },
    )


def session_current(session, actor, digest, now):
    if session is not None and (
        session.user_id != actor.pk
        or session.revoked_at is not None
        or now >= session.expires_at
        or (digest is not None and session.token_digest != digest)
    ):
        rules.fail("session_unavailable", "Sign in again to open this protected handoff.", 401)


def operate(
    *,
    actor,
    transfer_id,
    operation,
    expected_transfer_version=None,
    handoff_id=None,
    expected_handoff_version=None,
    sections=None,
    addendum=None,
    exception_reason=None,
    context=None,
    actor_session_id=None,
    actor_session_digest=None,
    addenda_page=1,
):
    if type(addenda_page) is not int or not 1 <= addenda_page <= 1000:
        rules.fail("handoff_page_invalid", "Choose a valid addendum page.", 422)
    try:
        with transaction.atomic(durable=True):
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL lock_timeout = '1000ms'")
            actor = rules.current_actor(actor)
            hint = transfers.transfers().filter(pk=transfer_id).first()
            if hint is None:
                rules.fail("arrangement_not_found", "The transfer is unavailable.", 404)
            case = rules.lock_case(hint.case_id)
            item = transfers.transfers().select_for_update(of=("self",)).get(pk=hint.pk)
            item.case = case
            ids = transfers.lock_work(item) | {actor.pk}
            people = rules.lock_people(ids)
            actor = rules.current_actor(people[actor.pk])
            context = context or AuditContext.user(actor)
            item.prepared_by = people[item.prepared_by_id]
            item.receiving_counselor = people[item.receiving_counselor_id]
            item.outgoing_counselor = people[item.outgoing_counselor_id]
            session = None
            if actor_session_id is not None:
                session = (
                    AuthSession.objects.select_for_update(of=("self",), nowait=True)
                    .filter(pk=actor_session_id)
                    .first()
                )
                if session is None:
                    rules.fail(
                        "session_unavailable", "Sign in again to open this protected handoff.", 401
                    )
            now = timezone.now()
            session_current(session, actor, actor_session_digest, now)
            if operation != "read":
                rules.require_version(item, expected_transfer_version)
            handoff = (
                CounselingCaseHandoff.objects.select_for_update(of=("self",))
                .filter(pk=handoff_id or item.case_handoff_id, transfer=item)
                .first()
            )
            if operation == "save":
                if not may_write(actor, item, now):
                    rules.fail(
                        "handoff_write_denied",
                        "Only the current outgoing Counselor can write this handoff.",
                        403,
                    )
                if handoff is None:
                    if expected_handoff_version is not None:
                        rules.fail("changed", "The handoff changed. Review the latest plan.")
                    handoff = CounselingCaseHandoff(
                        transfer=item,
                        case=case,
                        student_id=case.student_id,
                        author=actor,
                        receiving_counselor=item.receiving_counselor,
                        plan_digest=plan_digest(item),
                    )
                else:
                    if handoff.state != "DRAFT":
                        rules.fail(
                            "handoff_immutable",
                            "The submitted handoff is immutable. Add an attributed addendum.",
                        )
                    if (
                        handoff.version != expected_handoff_version
                        or handoff.plan_digest != plan_digest(item)
                    ):
                        rules.fail("changed", "The handoff or reviewed plan changed.")
                    handoff.version += 1
                handoff.content_ciphertext = content.encrypt(handoff, sections, work_snapshot(item))
                handoff.save()
                item.case_handoff, item.handoff_exception = handoff, None
                invalidate(item, actor=actor, context=context)
                audit(actor, handoff, "draft_saved", context, transfer=item)
            elif operation == "exception":
                if not may_record_exception(actor, item, now):
                    rules.fail(
                        "handoff_exception_denied",
                        "An eligible Head must record this exception. "
                        "It is unavailable for the personal request to the receiving Head.",
                        403,
                    )
                if exception_reason not in CaseHandoffUnavailableReason.values:
                    rules.fail(
                        "handoff_exception_reason_required",
                        "Choose why the handoff cannot be obtained.",
                        422,
                    )
                exception = CounselingCaseHandoffException.objects.create(
                    transfer=item,
                    recorded_by=actor,
                    reason=exception_reason,
                    plan_digest=plan_digest(item),
                )
                item.case_handoff, item.handoff_exception = None, exception
                invalidate(item, actor=actor, context=context)
                audit(
                    actor,
                    exception,
                    "unavailable_recorded",
                    context,
                    transfer=item,
                    extra={"reason_code": exception_reason},
                )
                transfers.notify_next_actor(item)
                result = {"transfer_version": item.version}
            else:
                if handoff is None or not may_read(actor, item, handoff, now):
                    rules.fail(
                        "handoff_not_found",
                        "The protected handoff is unavailable to this account.",
                        404,
                    )
                if operation == "submit":
                    if not may_write(actor, item, now) or handoff.state != "DRAFT":
                        rules.fail(
                            "handoff_immutable",
                            "Only the outgoing author can submit a Draft handoff.",
                        )
                    if (
                        handoff.version != expected_handoff_version
                        or handoff.plan_digest != plan_digest(item)
                    ):
                        rules.fail("changed", "The handoff or reviewed plan changed.")
                    body = content.read(handoff)
                    content.validate_sections(body["sections"], submitted=True)
                    handoff.state, handoff.submitted_at = "SUBMITTED", timezone.now()
                    handoff.version += 1
                    handoff.save()
                    item.handoff_exception = None
                    invalidate(item, actor=actor, context=context)
                    audit(actor, handoff, "submitted", context, transfer=item)
                elif operation == "addendum":
                    if (
                        handoff.state != "SUBMITTED"
                        or not actor.has_capability("counseling.handoff.manage_own", at=now)
                        or actor.pk not in {handoff.author_id, case.primary_counselor_id}
                    ):
                        rules.fail(
                            "handoff_addendum_denied",
                            "Only an authorized author or current case owner "
                            "can add to a submitted handoff.",
                            403,
                        )
                    addition = CounselingCaseHandoffAddendum(handoff=handoff, author=actor)
                    addition.content_ciphertext = content.encrypt_addendum(addition, addendum)
                    addition.save(force_insert=True)
                    if item.state == "ACCEPTED":
                        # Preserve effective responsibility, while preventing a concurrent or
                        # unconfirmed same-version addendum from being recorded twice.
                        transfers._save(item)
                    else:
                        invalidate(item, actor=actor, context=context)
                    audit(
                        actor,
                        handoff,
                        "addendum_added",
                        context,
                        transfer=item,
                        extra={"addendum_id": str(addition.pk)},
                    )
                elif operation != "read":
                    rules.fail("action_invalid", "Choose a supported handoff action.", 422)
            if operation != "exception":
                if (
                    operation == "read"
                    and item.state == "AUTHORIZED"
                    and actor.pk != handoff.author_id
                ):
                    transfers.require_current_authorization(item, people, timezone.now())
                body = content.read(handoff)
                offset = (addenda_page - 1) * 20
                addition_rows = list(
                    handoff.addenda.select_related("author").order_by("-created_at", "-pk")[
                        offset : offset + 21
                    ]
                )
                additions = [
                    {
                        "id": row.pk,
                        "author": person(row.author),
                        "created_at": row.created_at,
                        "content": content.read_addendum(row),
                    }
                    for row in addition_rows[:20]
                ]
                if operation == "read":
                    if actor.pk != handoff.author_id:
                        CounselingCaseHandoffReceipt.objects.get_or_create(
                            handoff=handoff, reader=actor
                        )
                    audit(actor, handoff, "read", context, transfer=item)
                result = {
                    "id": handoff.pk,
                    "state": handoff.state,
                    "version": handoff.version,
                    "author": person(handoff.author),
                    "submitted_at": handoff.submitted_at,
                    "transfer_version": item.version,
                    "sections": body["sections"],
                    "work": body["work"],
                    "addenda": additions,
                    "addenda_page": addenda_page,
                    "addenda_has_next": len(addition_rows) > 20,
                    "can_edit": handoff.state == "DRAFT" and may_write(actor, item),
                    "can_addendum": handoff.state == "SUBMITTED"
                    and actor.has_capability("counseling.handoff.manage_own")
                    and actor.pk in {handoff.author_id, case.primary_counselor_id},
                }
                if not may_read(actor, item, handoff, timezone.now()):
                    rules.fail(
                        "handoff_not_found",
                        "Protected handoff access ended. Review the latest arrangement.",
                        404,
                    )
            session_current(session, actor, actor_session_digest, timezone.now())
        return result
    except OperationalError:
        rules.fail("busy", "This arrangement is changing. Review the latest details and try again.")
