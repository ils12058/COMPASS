"""One exact authorized Student/author, bounded structural selection; never body reads."""

from django.db import OperationalError, connection, transaction
from django.utils import timezone

from compass.accounts.models import User
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.counseling import continuity_services as grants
from compass.counseling.continuity_encounters import _lock_encounter
from compass.counseling.continuity_locks import (
    lock_authority_relations,
    lock_policy_for_selected_read,
)
from compass.counseling.continuity_policy import ContinuityError, require_policy
from compass.counseling.coverage_policy import ApprovedOfficeCase, require_workflow_policy
from compass.counseling.models import CounselingEncounter
from compass.routine_interviews.continuity import _lock_evaluation
from compass.routine_interviews.models import RoutineInterview


def _policies(actor, action="request"):
    now = timezone.now()
    actor = grants._actor(actor, action, now)
    policy = require_policy(now)
    workflow = require_workflow_policy(policy, now)
    return policy, workflow


@transaction.atomic(durable=True)
def configuration(*, actor):
    lock_policy_for_selected_read()
    grants._users(actor.pk)
    lock_authority_relations()
    actor = User.objects.select_related("role").get(pk=actor.pk)
    policy, workflow = _policies(actor, "view")
    office = actor.pk in policy.office_requester_ids
    if office:
        # Exact policy-named Head, never capability-only office enumeration.
        grants._head(actor, policy, timezone.now())
    return {
        "server_now": timezone.now(),
        "valid_until": min(policy.valid_until, workflow.valid_until),
        "maximum_duration_seconds": int(policy.maximum_duration.total_seconds()),
        "maximum_advance_seconds": int(policy.maximum_advance.total_seconds()),
        "reason_categories": sorted(policy.reason_categories),
        "can_request": actor.has_capability("counseling.continuity.request"),
        "can_approve": actor.pk in policy.approver_ids
        and grants.UserDesignation.objects.filter(
            user=actor, designation__code="HEAD_GUIDANCE_COUNSELOR"
        ).exists()
        and actor.has_capability("counseling.continuity.approve"),
        "office_cases": [
            {"student_id": c.student_id, "original_counselor_id": c.original_counselor_id}
            for c in workflow.office_cases
            if office
            and c.requester_id == actor.pk
            and grants.StudentAffiliation.objects.filter(
                student_id=c.student_id,
                college_id__in=workflow.college_ids.intersection(policy.college_ids),
                college__is_active=True,
                college__campus__is_active=True,
                student__is_active=True,
                student__role__code="STUDENT",
                student__student_lifecycle_status="CURRENT",
            ).exists()
        ],
    }


def select(*, actor, student_id, original_counselor_id, page=1, context=None):
    if type(page) is not int or not 1 <= page <= 10000:
        raise ContinuityError("invalid_pagination", 422)
    try:
        with transaction.atomic(durable=True):
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL lock_timeout = '1000ms'")
            lock_policy_for_selected_read()
            users = grants._users(actor.pk, student_id, original_counselor_id)
            lock_authority_relations()
            users = {u.pk: u for u in User.objects.select_related("role").filter(pk__in=users)}
            actor = users[actor.pk]
            policy, workflow = _policies(actor)
            grants._student(users.get(student_id), policy)
            if not grants.StudentAffiliation.objects.filter(
                student_id=student_id, college_id__in=workflow.college_ids
            ).exists():
                raise ContinuityError("source_not_found", 404)
            office = actor.pk != original_counselor_id
            if office:
                grants._head(actor, policy, timezone.now())
                if (
                    actor.pk not in policy.office_requester_ids
                    or ApprovedOfficeCase(actor.pk, student_id, original_counselor_id)
                    not in workflow.office_cases
                ):
                    raise ContinuityError("source_not_found", 404)
            original = users.get(original_counselor_id)
            if original is None or original.role.code != "COUNSELOR":
                raise ContinuityError("source_not_found", 404)
            # Source inventories are filtered to this exact approved Student + historical author.
            candidates = []
            if "ENCOUNTER" in workflow.source_kinds and (
                office or actor.has_capability("counseling.view_assigned")
            ):
                candidates += [
                    ("ENCOUNTER", i)
                    for i in CounselingEncounter.objects.filter(
                        student_id=student_id, counselor_id=original_counselor_id
                    )
                    .order_by("pk")
                    .values_list("pk", flat=True)[(page - 1) * 25 : page * 25 + 1]
                ]
            if "ROUTINE_EVALUATION" in workflow.source_kinds and (
                office or actor.has_capability("routine_interviews.view_assigned")
            ):
                candidates += [
                    ("ROUTINE_EVALUATION", i)
                    for i in RoutineInterview.objects.filter(
                        student_id=student_id,
                        counselor_id=original_counselor_id,
                        evaluation_finalized_at__isnull=False,
                    )
                    .order_by("pk")
                    .values_list("pk", flat=True)[(page - 1) * 25 : page * 25 + 1]
                ]
            items = []
            for kind, source_id in sorted(candidates):
                same_kind = [c for c in candidates if c[0] == kind]
                if (kind, source_id) not in same_kind[:25]:
                    continue
                try:
                    with transaction.atomic():
                        if kind == "ENCOUNTER":
                            source, _ = _lock_encounter(
                                encounter_id=source_id,
                                student_id=student_id,
                                original_counselor_id=original_counselor_id,
                                now=timezone.now(),
                            )
                            date, projection = source.started_at, "ENCOUNTER_METADATA_V1"
                        else:
                            source, _ = _lock_evaluation(
                                routine_interview_id=source_id,
                                student_id=student_id,
                                original_counselor_id=original_counselor_id,
                                now=timezone.now(),
                            )
                            date, projection = (
                                source.evaluation_finalized_at,
                                "FINALIZED_EVALUATION_V1",
                            )
                        items.append(
                            {
                                "resource_kind": kind,
                                "source_id": source_id,
                                "projection": projection,
                                "counselor_id": original_counselor_id,
                                "recorded_at": date,
                                "eligible": True,
                            }
                        )
                except ContinuityError as exc:
                    if exc.status != 404:
                        raise
            # No legitimate source relationship means no receiver directory disclosure either.
            if not candidates and not office:
                raise ContinuityError("source_not_found", 404)
            receivers = []
            for receiver in (
                User.objects.select_related("role")
                .filter(is_active=True, role__code="COUNSELOR")
                .exclude(pk=original_counselor_id)
                .order_by("id")[:200]
            ):
                try:
                    grants._receiver(receiver, timezone.now())
                    receivers.append({"id": receiver.pk, "name": receiver.get_full_name()})
                except ContinuityError:
                    pass
            context = context or AuditContext.user(actor)
            if context.actor_type != "USER" or context.actor.pk != actor.pk:
                raise ValueError("Selection Audit actor must match")
            record_event(
                context=context,
                action="counseling.continuity.selection_read",
                outcome=AuditOutcome.SUCCESS,
                target_type="accounts.user",
                target_id=student_id,
                metadata={
                    "student_id": str(student_id),
                    "original_counselor_id": str(original_counselor_id),
                    "policy_version": workflow.version,
                    "policy_evidence": workflow.selection_evidence,
                    "page": page,
                },
            )
            _policies(actor)
            return {
                "items": items[:50],
                "receivers": receivers,
                "page": page,
                "has_next": len(candidates) > 50
                or any(
                    len([c for c in candidates if c[0] == k]) > 25 for k in workflow.source_kinds
                ),
            }
    except OperationalError as exc:
        if getattr(exc.__cause__, "sqlstate", None) in {"55P03", "40P01"}:
            raise ContinuityError("source_busy", 409) from None
        raise
