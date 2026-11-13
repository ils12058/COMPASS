"""Deliberate case closure and reopening; outstanding work retains its own workflow."""

from django.db import OperationalError, connection, transaction
from django.utils import timezone

from compass.accounts.models import User
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.authentication.models import AuthSession
from compass.guidance_followups import policy
from compass.guidance_followups.content import decrypt_text
from compass.guidance_followups.errors import FollowUpError
from compass.guidance_followups.models import GuidanceFollowUp

from . import case_closure_content as content
from . import case_continuity_rules as rules
from .case_closure_models import (
    CaseClosureOutcome,
    CaseClosureReason,
    CaseReopenReason,
    CounselingCaseClosure,
)
from .case_models import CounselingCase, CounselingCaseAppointment
from .case_services import (
    MANAGE_CAPABILITY,
    VIEW_CAPABILITY,
    CounselingCaseChanged,
    CounselingCaseClosed,
    CounselingCaseError,
    CounselingCaseInvalid,
    CounselingCaseNotFound,
    _expected_version,
    _require_actor,
)


class CaseCloseBlocked(CounselingCaseError):
    code = "counseling_case_close_blocked"

    def __init__(self, blockers):
        self.blockers = blockers
        super().__init__("Resolve the outstanding case work before closing this case.")


def _owner(case, actor, *, manage=True, now=None):
    _require_actor(actor, MANAGE_CAPABILITY if manage else VIEW_CAPABILITY, at=now)
    if case.primary_counselor_id != actor.pk:
        raise CounselingCaseNotFound("The requested case was not found.")


def _lock(case_id, actor, *, expected_version=None, manage=True, extra_people=()):
    case = CounselingCase.objects.select_for_update(of=("self",)).filter(pk=case_id).first()
    if case is None or case.primary_counselor_id != actor.pk:
        raise CounselingCaseNotFound("The requested case was not found.")
    # Case, source Encounters, work, then Users and authority. NOWAIT avoids task-writer inversions.
    tasks = list(GuidanceFollowUp.objects.filter(case=case, status="PENDING"))
    from .models import CounselingEncounter

    rules.locked_rows(
        CounselingEncounter.objects.filter(
            pk__in=[row.source_id for row in tasks if row.source_kind == "COUNSELING_ENCOUNTER"]
        )
    )
    tasks = rules.locked_rows(
        GuidanceFollowUp.objects.select_related("student__role", "assigned_to__role").filter(
            case=case, status="PENDING"
        )
    )
    links = rules.locked_rows(
        CounselingCaseAppointment.objects.filter(case=case, removed_at__isnull=True)
    )
    from compass.appointments.models import Appointment

    rules.locked_rows(Appointment.objects.filter(pk__in=[row.appointment_id for row in links]))
    people = rules.lock_people(
        {actor.pk, case.student_id, *extra_people} | {row.assigned_to_id for row in tasks}
    )
    actor = people[actor.pk]
    _owner(case, actor, manage=manage, now=timezone.now())
    if expected_version is not None and case.version != _expected_version(expected_version):
        raise CounselingCaseChanged("This case changed. Review the latest details.")
    return case, actor


def _current_designation(task):
    # Reopening does not undo an administrative disposition or its explicit task responsibility.
    return task.post_closure_designated_at is not None


def outstanding(case, actor, *, now=None, project=True):
    """Case lock serializes all link/create/continuity transitions; source rows are fenced above."""
    from .case_coverage_models import CounselingCaseCoverageTask
    from .case_coverage_services import state_at as coverage_state
    from .case_coverage_tasks import reconcile_returns

    reconcile_returns(actor=actor, case_id=case.pk)
    now = now or timezone.now()
    transfers = [
        row
        for row in case.transfers.all()
        if rules.state_at(row, now) in {"PREPARED", "AUTHORIZED"}
    ]
    coverages = [
        row
        for row in case.coverages.all()
        if coverage_state(row, now) in {"PREPARED", "AUTHORIZED", "SCHEDULED", "ACTIVE"}
    ]
    delegated = list(
        CounselingCaseCoverageTask.objects.filter(
            coverage__case=case, delegated_at__isnull=False, returned_at__isnull=True
        ).values_list("task_id", flat=True)
    )
    appointments = [
        row.appointment
        for row in case.appointment_links.select_related("appointment").filter(
            removed_at__isnull=True, appointment__status="SCHEDULED", appointment__starts_at__gt=now
        )
    ]
    tasks = list(
        GuidanceFollowUp.objects.filter(case=case, status="PENDING").select_related(
            "student__role", "assigned_to__role"
        )
    )
    blocking_tasks = []
    for row in tasks:
        valid = _current_designation(row)
        if valid:
            try:
                policy.require_assignee(
                    row.assigned_to_id,
                    student_id=row.student_id,
                    visibility=row.visibility,
                    source_kind=row.source_kind,
                    source_id=row.source_id,
                    case_id=row.case_id,
                    post_closure_designated=True,
                )
            except FollowUpError:
                valid = False
        if not valid:
            blocking_tasks.append(row.pk)
    blockers = [
        kind
        for kind, rows in (
            ("TRANSFER", transfers),
            ("COVERAGE", coverages),
            ("DELEGATED_TASK", delegated),
            ("APPOINTMENT", appointments),
            ("TASK", blocking_tasks),
        )
        if rows
    ]
    if not project:
        return blockers
    return {
        "case_id": case.pk,
        "version": case.version,
        "blockers": blockers,
        "transfers": [
            {"id": row.pk, "reference_code": row.reference_code, "state": rules.state_at(row, now)}
            for row in transfers
        ],
        "coverages": [
            {"id": row.pk, "reference_code": row.reference_code, "state": coverage_state(row, now)}
            for row in coverages
        ],
        "delegated_task_ids": delegated,
        "appointments": [
            {
                "id": row.pk,
                "reference_code": row.reference_code,
                "starts_at": row.starts_at,
                "ends_at": row.ends_at,
            }
            for row in appointments
        ],
        "tasks": [
            {
                "id": row.pk,
                "student_id": row.student_id,
                "category": row.category,
                "source_kind": row.source_kind,
                "source_id": row.source_id,
                "title": decrypt_text(row.pk, "title", row.title_ciphertext)
                if row.title_ciphertext and policy.authorized(actor, row)
                else None,
                "assigned_to_id": row.assigned_to_id,
                "assigned_to_name": row.assigned_to.get_full_name(),
                "due_at": row.due_at,
                "version": row.version,
                "post_closure_designated_at": row.post_closure_designated_at
                if _current_designation(row)
                else None,
                "can_designate": policy.authorized(actor, row, manage=True)
                and actor.has_capability("guidance_followups.manage"),
            }
            for row in tasks
        ],
        "can_close": not blockers,
    }


def get_closure_context(*, actor, case_id):
    try:
        with transaction.atomic():
            case, actor = _lock(case_id, actor)
            if case.status != "ACTIVE":
                raise CounselingCaseClosed(
                    "This case is closed. Reopen it before changing its work."
                )
            return outstanding(case, actor)
    except rules.CaseContinuityError as exc:
        raise CounselingCaseChanged(exc.message) from None


def _audit(case, actor, action, closure, context):
    record_event(
        context=context or AuditContext.user(actor),
        action="counseling.case." + action,
        outcome=AuditOutcome.SUCCESS,
        target_type="counseling.case",
        target_id=case.pk,
        metadata={
            "closure_id": str(closure.pk),
            "case_id": str(case.pk),
            "version": case.version,
            "reference_code": case.reference_code,
            "reason": closure.reason if action == "closed" else closure.reopen_reason,
            **({"outcome": closure.outcome} if action == "closed" else {}),
        },
    )


def close_case(
    *, actor, case_id, expected_version, reason, outcome, note=None, context=None, now=None
):
    if reason not in CaseClosureReason.values or outcome not in CaseClosureOutcome.values:
        raise CounselingCaseInvalid("Choose a closure reason and outcome.")
    note = content.validate_note(note)
    if reason == "CONTACT_NOT_REESTABLISHED" and (note is None or len(note.strip()) < 20):
        raise CounselingCaseInvalid(
            "Describe the documented contact attempts in at least 20 characters."
        )
    try:
        with transaction.atomic():
            case, actor = _lock(case_id, actor, expected_version=expected_version)
            if case.status != "ACTIVE":
                raise CounselingCaseClosed("This case is already closed.")
            at = now or timezone.now()
            blockers = outstanding(case, actor, now=at, project=False)
            if blockers:
                raise CaseCloseBlocked(blockers)
            if case.closures.filter(reopened_at__isnull=True).exists():
                raise CounselingCaseChanged("This case's closure history needs review.")
            closure = CounselingCaseClosure(
                case=case, closed_by=actor, closed_at=at, reason=reason, outcome=outcome
            )
            if note is not None:
                closure.content_ciphertext = content.encrypt(closure, note)
            closure.save(force_insert=True)
            GuidanceFollowUp.objects.filter(
                case=case,
                status="PENDING",
                post_closure_designated_at__isnull=False,
                post_closure_closure__isnull=True,
            ).update(post_closure_closure=closure)
            case.status = "CLOSED"
            case.version += 1
            case.save(update_fields=["status", "version", "updated_at"])
            _audit(case, actor, "closed", closure, context)
            _owner(case, User.objects.select_related("role").get(pk=actor.pk), now=timezone.now())
            return case
    except rules.CaseContinuityError as exc:
        raise CounselingCaseChanged(exc.message) from None


def reopen_locked_case(*, case, actor, reason="FURTHER_SUPPORT_NEEDED", context=None, now=None):
    """Called by owner reopening or accepted REOPEN transfer, with case and Users already fenced."""
    if reason not in CaseReopenReason.values:
        raise CounselingCaseInvalid("Choose why the same episode needs to reopen.")
    if case.status != "CLOSED":
        raise CounselingCaseChanged("This case is no longer Closed.")
    closure = case.closures.select_for_update(of=("self",)).filter(reopened_at__isnull=True).first()
    if closure is None:
        raise CounselingCaseChanged("This case's closure history needs review.")
    closure.reopened_by, closure.reopened_at, closure.reopen_reason = (
        actor,
        now or timezone.now(),
        reason,
    )
    closure.save(update_fields=["reopened_by", "reopened_at", "reopen_reason"])
    case.status = "ACTIVE"
    case.version += 1
    case.save(update_fields=["status", "primary_counselor", "version", "updated_at"])
    _audit(case, actor, "reopened", closure, context)
    return case


def reopen_case(*, actor, case_id, expected_version, reason, context=None, now=None):
    try:
        with transaction.atomic():
            case, actor = _lock(case_id, actor, expected_version=expected_version)
            return reopen_locked_case(
                case=case, actor=actor, reason=reason, context=context, now=now
            )
    except rules.CaseContinuityError as exc:
        raise CounselingCaseChanged(exc.message) from None


def designate_task(
    *,
    actor,
    case_id,
    task_id,
    expected_version,
    expected_task_version,
    administrative_action,
    assigned_to_id,
    due_at,
    context=None,
):
    from compass.guidance_followups.services import _audit as task_audit
    from compass.guidance_followups.services import _due, _event

    if administrative_action is not True:
        raise CounselingCaseInvalid(
            "Only an explicitly reviewed administrative action can remain after closure."
        )
    try:
        with transaction.atomic():
            case, actor = _lock(
                case_id, actor, expected_version=expected_version, extra_people=(assigned_to_id,)
            )
            if case.status != "ACTIVE":
                raise CounselingCaseClosed(
                    "Designate the administrative action before closing the case."
                )
            actor = policy.current_actor(actor, manage=True)
            task = (
                GuidanceFollowUp.objects.select_for_update(of=("self",))
                .select_related("student__role", "assigned_to__role")
                .filter(pk=task_id, case=case)
                .first()
            )
            if task is None:
                raise CounselingCaseNotFound("The case action was not found.")
            policy.require_followup(actor, task, manage=True)
            if task.version != _expected_version(expected_task_version) or task.status != "PENDING":
                raise CounselingCaseChanged("This action changed. Review the latest details.")
            _due(due_at, now=timezone.now())
            assignee = policy.require_assignee(
                assigned_to_id,
                student_id=task.student_id,
                visibility=task.visibility,
                source_kind=task.source_kind,
                source_id=task.source_id,
                case_id=case.pk,
            )
            previous, old_due = task.assigned_to, task.due_at
            task.assigned_to, task.due_at = assignee, due_at
            task.post_closure_designated_at, task.post_closure_closure = timezone.now(), None
            task.version += 1
            task.save(
                update_fields=[
                    "assigned_to",
                    "due_at",
                    "post_closure_designated_at",
                    "post_closure_closure",
                    "version",
                    "updated_at",
                ]
            )
            _event(
                task,
                actor=actor,
                kind="UPDATED",
                old_assignee=previous,
                new_assignee=assignee,
                old_due=old_due,
                new_due=due_at,
            )
            task_audit(
                context or AuditContext.user(actor),
                "updated",
                task,
                metadata={"fields": ["post_closure_designated_at", "assigned_to", "due_at"]},
            )
            case.version += 1
            case.save(update_fields=["version", "updated_at"])
            return case
    except rules.CaseContinuityError as exc:
        raise CounselingCaseChanged(exc.message) from None


def _session_current(session, actor, digest, at):
    if session is not None and (
        session.user_id != actor.pk
        or session.revoked_at is not None
        or session.expires_at <= at
        or session.token_digest != digest
    ):
        error = CounselingCaseError("Sign in again to read this case.")
        error.code, error.status = "authentication_required", 401
        raise error


def protected_closures(*, actor, case_id, actor_session_id=None, actor_session_digest=None):
    """Owner-only note reads, case/authority/session fenced and rechecked after decryption."""
    if not CounselingCaseClosure.objects.filter(case_id=case_id).exists():
        return []
    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL lock_timeout = '1000ms'")
            case = CounselingCase.objects.select_for_update(of=("self",)).filter(pk=case_id).first()
            if case is None:
                raise CounselingCaseNotFound("The requested case was not found.")
            people = rules.lock_people({actor.pk, case.primary_counselor_id})
            actor = people.get(actor.pk)
            _owner(case, actor, manage=False, now=timezone.now())
            session = None
            if actor_session_id is not None:
                session = (
                    AuthSession.objects.select_for_update(of=("self",), nowait=True)
                    .filter(pk=actor_session_id)
                    .first()
                )
                if session is None:
                    error = CounselingCaseError("Sign in again to read this case.")
                    error.code, error.status = "authentication_required", 401
                    raise error
            _session_current(session, actor, actor_session_digest, timezone.now())
            rows = list(
                case.closures.select_related("closed_by", "reopened_by").order_by("closed_at", "id")
            )
            result = [
                {
                    "id": row.pk,
                    "closed_at": row.closed_at,
                    "closed_by": {
                        "id": row.closed_by_id,
                        "display_name": row.closed_by.get_full_name(),
                    },
                    "reason": row.reason,
                    "outcome": row.outcome,
                    "note": content.read(row),
                    "reopened_at": row.reopened_at,
                    "reopened_by": {
                        "id": row.reopened_by_id,
                        "display_name": row.reopened_by.get_full_name(),
                    }
                    if row.reopened_by
                    else None,
                    "reopen_reason": row.reopen_reason,
                }
                for row in rows
            ]
            actor = User.objects.select_related("role").get(pk=actor.pk)
            _owner(case, actor, manage=False, now=timezone.now())
            _session_current(session, actor, actor_session_digest, timezone.now())
            return result
    except (OperationalError, rules.CaseContinuityError):
        raise CounselingCaseChanged(
            "Case authority is changing. Review the latest details."
        ) from None
