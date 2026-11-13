"""Selected task authority follows time, not a scheduler or the stored assignee alone."""

from contextlib import contextmanager
from functools import wraps

from django.db import OperationalError, connection, transaction
from django.db.models import Exists, F, OuterRef, Q
from django.utils import timezone

from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.guidance_followups.models import GuidanceFollowUp, GuidanceFollowUpEvent

from . import case_continuity_rules as rules
from .case_coverage_models import CounselingCaseCoverageTask


def active_task_plans(now=None):
    at = now or timezone.now()
    return CounselingCaseCoverageTask.objects.filter(
        delegated_at__isnull=False,
        returned_at__isnull=True,
        coverage__state="ACCEPTED",
        coverage__starts_at__lte=at,
        coverage__expires_at__gt=at,
        coverage__case__status="ACTIVE",
        coverage__case__primary_counselor_id=F("coverage__primary_counselor_id"),
        task__case_id=F("coverage__case_id"),
        task__student_id=F("coverage__case__student_id"),
        task__assigned_to_id=F("coverage__primary_counselor_id"),
        task__category="COUNSELING",
        task__visibility="COUNSELOR_CONFIDENTIAL",
    ).filter(
        (
            Q(
                source_kind__isnull=True,
                task__source_kind__isnull=True,
                source_id__isnull=True,
                task__source_id__isnull=True,
            )
        )
        | Q(
            source_kind=F("task__source_kind"),
            source_id=F("task__source_id"),
            source_kind__isnull=False,
            source_id__isnull=False,
        )
    )


def active_delegation(task, now=None):
    return (
        active_task_plans(now)
        .select_related("coverage__receiving_counselor__role", "coverage__primary_counselor__role")
        .filter(task_id=task.pk)
        .first()
    )


def may_receive_task(actor, plan, *, manage=False, now=None):
    at = now or timezone.now()
    return bool(
        plan
        and actor.pk == plan.coverage.receiving_counselor_id
        and rules.receiver_eligible(actor, at)
        and actor.has_capability("counseling.continuity.read_selected", at=at)
        and actor.has_capability(
            "counseling.manage_assigned" if manage else "counseling.view_assigned", at=at
        )
    )


def effective_assignee(task, now=None):
    plan = active_delegation(task, now)
    return plan.coverage.receiving_counselor if plan else task.assigned_to


def scoped_assignments(actor, queryset, *, manage=False, include_owned_delegated=False):
    """The temporal assignment is evaluated in SQL before any page or title is loaded."""
    live = active_task_plans().filter(task_id=OuterRef("pk"))
    received = live.filter(coverage__receiving_counselor_id=actor.pk)
    queryset = queryset.alias(_cw_covered=Exists(live), _cw_received=Exists(received))
    own = Q(assigned_to_id=actor.pk)
    if not include_owned_delegated or manage:
        own &= Q(_cw_covered=False)
    eligible = (
        rules.receiver_eligible(actor, timezone.now())
        and actor.has_capability("counseling.continuity.read_selected")
        and actor.has_capability(
            "counseling.manage_assigned" if manage else "counseling.view_assigned"
        )
    )
    return queryset.filter(own | Q(_cw_received=True) if eligible else own), eligible


def task_event(task, coverage, *, actor, effective_at, old_assignee, new_assignee):
    task.version += 1
    task.save(update_fields=["version", "updated_at"])
    event = GuidanceFollowUpEvent.objects.create(
        followup=task,
        actor=actor,
        kind="REASSIGNED",
        revision=task.version,
        old_assignee=old_assignee,
        new_assignee=new_assignee,
        case_coverage=coverage,
        coverage_effective_at=effective_at,
    )
    from compass.realtime.publish import publish_to_user_on_commit

    for person in {old_assignee.pk, new_assignee.pk}:
        publish_to_user_on_commit(person, "followups.changed")
    return event


def _return_audit(coverage, actor, verb, count):
    record_event(
        context=AuditContext.user(actor),
        action="counseling.case_coverage." + verb,
        outcome=AuditOutcome.SUCCESS,
        target_type="counseling.case_coverage",
        target_id=coverage.pk,
        metadata={
            "case_id": str(coverage.case_id),
            "reference_code": coverage.reference_code,
            "version": coverage.version,
            "count": count,
            "independent_authorization": coverage.independent_authorization,
            "authorization_route": coverage.authorization_route,
        },
    )


def reconcile_returns(*, actor=None, case_id=None, task_id=None):
    """Idempotently record a derived end/return; never complete or cancel work.

    Case continuity, task reads/writes and the explicit management command call this.
    Event attribution uses the reader when involved, otherwise the accepting Counselor.
    No inactive-primary assignment is recovered through operational recovery.
    """
    from compass.counseling.continuity_rules import is_head
    from compass.guidance_followups import policy

    from .case_coverage_services import coverages, lock_work

    at = timezone.now()
    candidates = (
        CounselingCaseCoverageTask.objects.filter(delegated_at__isnull=False)
        .filter(Q(returned_at__isnull=True) | Q(recovery_required=True))
        .filter(
            Q(coverage__state="REVOKED")
            | Q(coverage__expires_at__lte=at)
            | ~Q(coverage__case__primary_counselor_id=F("coverage__primary_counselor_id"))
        )
    )
    if case_id is not None:
        candidates = candidates.filter(coverage__case_id=case_id)
    elif task_id is not None:
        candidates = candidates.filter(task_id=task_id)
    elif actor is not None and not is_head(actor):
        candidates = candidates.filter(
            Q(coverage__primary_counselor_id=actor.pk)
            | Q(coverage__receiving_counselor_id=actor.pk)
            | Q(coverage__prepared_by_id=actor.pk)
        )
    returned = recovered = 0
    case_ids = (
        candidates.order_by("coverage__case_id")
        .values_list("coverage__case_id", flat=True)
        .distinct()
    )

    # Stream bounded batches. A recovery flag can remain pending across runs; keyset paging
    # visits that case only once during this run, without retaining the full roster in memory.
    def identities():
        after = None
        while True:
            query = case_ids if after is None else case_ids.filter(coverage__case_id__gt=after)
            batch = tuple(query[:200])
            if not batch:
                return
            yield from batch
            after = batch[-1]

    for identity in identities():
        with transaction.atomic():
            case = rules.lock_case(identity)
            for coverage in coverages().filter(case=case, task_plans__in=candidates).distinct():
                coverage.case = case
                people = rules.lock_people(
                    lock_work(coverage)
                    | {
                        case.primary_counselor_id,
                        getattr(actor, "pk", None),
                    }
                )
                now = timezone.now()
                ended = (
                    coverage.state == "REVOKED"
                    or coverage.expires_at <= now
                    or case.primary_counselor_id != coverage.primary_counselor_id
                )
                if not ended:
                    continue
                primary = people[case.primary_counselor_id]
                attributable = actor and actor.pk in {
                    coverage.primary_counselor_id,
                    coverage.receiving_counselor_id,
                    coverage.prepared_by_id,
                    coverage.authorized_by_id,
                }
                by = people[actor.pk] if attributable else people[coverage.decided_by_id]
                plans = rules.locked_rows(coverage.task_plans.filter(delegated_at__isnull=False))
                tasks = {
                    row.pk: row
                    for row in rules.locked_rows(
                        GuidanceFollowUp.objects.select_related(
                            "student__role", "assigned_to__role"
                        ).filter(pk__in=[plan.task_id for plan in plans])
                    )
                }
                count = cleared = 0
                for plan in plans:
                    task = tasks[plan.task_id]
                    eligible = (
                        rules.receiver_eligible(primary, now)
                        and primary.has_capability("guidance_followups.manage", at=now)
                        and task.assigned_to_id == primary.pk
                        and policy.authorized(primary, task, manage=True)
                    )
                    if plan.returned_at is None:
                        if task.status == "PENDING":
                            task_event(
                                task,
                                coverage,
                                actor=by,
                                effective_at=min(coverage.revoked_at or coverage.expires_at, now),
                                old_assignee=people[coverage.receiving_counselor_id],
                                new_assignee=task.assigned_to,
                            )
                            count += 1
                        plan.returned_at, plan.returned_by = now, by
                        plan.recovery_required = task.status == "PENDING" and not eligible
                        plan.save()
                    elif plan.recovery_required and (task.status != "PENDING" or eligible):
                        plan.recovery_required = False
                        plan.recovered_at, plan.recovered_by = now, primary
                        plan.save()
                        cleared += 1
                if count:
                    _return_audit(coverage, by, "tasks_returned", count)
                if cleared:
                    _return_audit(coverage, by, "tasks_recovered", cleared)
                returned += count
                recovered += cleared
    return {"returned": returned, "recovered": recovered}


@contextmanager
def task_read_guard(actor, item):
    """Fence covered-task decryption and discard results whose live authority ended.

    Primary/source reads retain their ordinary policy. Coverage never grants a case or
    source read. HTTP endpoints separately recheck their current session after projection.
    """
    if actor is None or not CounselingCaseCoverageTask.objects.filter(task_id=item.pk).exists():
        yield actor, item
        return
    from compass.guidance_followups import policy
    from compass.guidance_followups.errors import FollowUpConflict

    from .case_coverage_services import coverages, lock_work

    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL lock_timeout = '1000ms'")
            case = rules.lock_case(item.case_id)
            reconcile_returns(actor=actor, case_id=case.pk)
            offers = tuple(coverages().filter(case=case, task_plans__task_id=item.pk).distinct())
            ids = {actor.pk, case.primary_counselor_id, case.student_id}
            for offer in offers:
                ids |= lock_work(offer, task_ids=[item.pk])
            people = rules.lock_people(ids)
            actor = policy.current_actor(people[actor.pk])
            rows = rules.locked_rows(
                GuidanceFollowUp.objects.select_related(
                    "student__role",
                    "assigned_to__role",
                    "completed_by",
                    "cancelled_by",
                    "predecessor__student__role",
                ).filter(pk=item.pk)
            )
            item = policy.require_followup(actor, rows[0])
            yield actor, item
            actor = policy.current_actor(actor)
            policy.require_followup(actor, item)
    except (OperationalError, rules.CaseContinuityError) as exc:
        raise FollowUpConflict(
            "This task's coverage is changing. Review the latest details."
        ) from exc


def coverage_task_write(function):
    """Fence delegated writes case-first and recheck time after the last Audit write."""

    @wraps(function)
    def execute(**kwargs):
        task_id = kwargs["followup_id"]
        if not CounselingCaseCoverageTask.objects.filter(
            task_id=task_id, delegated_at__isnull=False
        ).exists():
            return function(**kwargs)
        from compass.guidance_followups import policy
        from compass.guidance_followups.errors import FollowUpConflict, FollowUpNotFound

        from .case_coverage_services import coverages, lock_work

        case_id = (
            GuidanceFollowUp.objects.filter(pk=task_id).values_list("case_id", flat=True).first()
        )
        with transaction.atomic():
            case = rules.lock_case(case_id)
            reconcile_returns(case_id=case.pk, actor=kwargs["actor"])
            offers = tuple(
                coverages().filter(
                    case=case,
                    state="ACCEPTED",
                    expires_at__gt=timezone.now(),
                    task_plans__task_id=task_id,
                )
            )
            ids = {kwargs["actor"].pk, case.primary_counselor_id, case.student_id}
            for offer in offers:
                ids |= lock_work(offer)
            people = rules.lock_people(ids)
            actor = policy.current_actor(people[kwargs["actor"].pk], manage=True)
            task = rules.locked_rows(
                GuidanceFollowUp.objects.select_related(
                    "student__role", "assigned_to__role"
                ).filter(pk=task_id)
            )[0]
            policy.require_followup(actor, task, manage=True)
            if offers and function.__name__ == "reassign_followup":
                raise FollowUpConflict("End the accepted coverage before reassigning this action.")
            result = function(**{**kwargs, "actor": actor})
            task.refresh_from_db()
            actor = policy.current_actor(actor, manage=True)
            if not policy.authorized(actor, task, manage=True):
                raise FollowUpNotFound(
                    "The task's coverage access ended before the change completed."
                )
            return result

    @wraps(function)
    def translated(**kwargs):
        from compass.guidance_followups.errors import FollowUpConflict

        try:
            return execute(**kwargs)
        except rules.CaseContinuityError as exc:
            raise FollowUpConflict(exc.message) from None

    return translated
