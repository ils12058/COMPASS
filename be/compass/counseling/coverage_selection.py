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
)
from compass.counseling.continuity_rules import (
    MAX_ADVANCE,
    MAX_DURATION,
    REASON_CATEGORIES,
    SOURCE_KINDS,
    ContinuityError,
    active_college_ids,
    is_head,
    is_office_requester,
    office_can_select,
    office_college_ids,
)
from compass.counseling.models import CounselingEncounter
from compass.routine_interviews.continuity import _lock_evaluation
from compass.routine_interviews.models import RoutineInterview


def _authorize(actor, action="request"):
    return grants._actor(actor, action, timezone.now())


def _office_cases(actor):
    # Only structurally eligible cases in this requester's live responsibility. No plaintext.
    students = grants.StudentAcademicProfile.objects.filter(
        current_college_id__in=office_college_ids(actor),
        student__is_active=True,
        student__role__code="STUDENT",
        student__student_lifecycle_status="CURRENT",
    ).values("student_id")
    cases = (
        CounselingEncounter.objects.filter(
            student_id__in=students, counselor__role__code="COUNSELOR"
        )
        .values_list("student_id", "counselor_id")
        .distinct()
        .order_by("student_id", "counselor_id")
    )
    cases = list(cases[:200])
    people = grants.display_people([person for case in cases for person in case])
    return [
        {
            "student_id": student_id,
            "student_name": people.get(student_id, {}).get("name", "Name not available"),
            "student_institutional_id": people.get(student_id, {}).get("institutional_id"),
            "original_counselor_id": original_id,
            "original_counselor_name": people.get(original_id, {}).get(
                "name", "Name not available"
            ),
        }
        for student_id, original_id in cases
    ]


@transaction.atomic(durable=True)
def configuration(*, actor):
    grants._users(actor.pk)
    lock_authority_relations()
    actor = User.objects.select_related("role").get(pk=actor.pk)
    _authorize(actor, "view")
    office = is_office_requester(actor)
    return {
        "server_now": timezone.now(),
        "maximum_duration_seconds": int(MAX_DURATION.total_seconds()),
        "maximum_advance_seconds": int(MAX_ADVANCE.total_seconds()),
        "reason_categories": sorted(REASON_CATEGORIES),
        "can_request": actor.has_capability("counseling.continuity.request"),
        "can_approve": is_head(actor) and actor.has_capability("counseling.continuity.approve"),
        "office_cases": _office_cases(actor) if office else [],
    }


def select(*, actor, student_id, original_counselor_id, page=1, context=None):
    if type(page) is not int or not 1 <= page <= 10000:
        raise ContinuityError("invalid_pagination", 422)
    try:
        with transaction.atomic(durable=True):
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL lock_timeout = '1000ms'")
            users = grants._users(actor.pk, student_id, original_counselor_id)
            lock_authority_relations()
            users = {u.pk: u for u in User.objects.select_related("role").filter(pk__in=users)}
            actor = users[actor.pk]
            _authorize(actor)
            grants._student(users.get(student_id))
            if not grants.StudentAcademicProfile.objects.filter(
                student_id=student_id, current_college_id__in=active_college_ids()
            ).exists():
                raise ContinuityError("source_not_found", 404)
            office = actor.pk != original_counselor_id
            if office:
                if not office_can_select(actor, student_id):
                    raise ContinuityError("source_not_found", 404)
            original = users.get(original_counselor_id)
            if original is None or original.role.code != "COUNSELOR":
                raise ContinuityError("source_not_found", 404)
            # Source inventories are filtered to this exact eligible Student + historical author.
            candidates = []
            if "ENCOUNTER" in SOURCE_KINDS and (
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
            if "ROUTINE_EVALUATION" in SOURCE_KINDS and (
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
            if not candidates:
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
                    "page": page,
                },
            )
            _authorize(actor)
            people = grants.display_people([student_id, original_counselor_id])
            return {
                "student_name": people.get(student_id, {}).get("name", "Name not available"),
                "student_institutional_id": people.get(student_id, {}).get("institutional_id"),
                "original_counselor_name": people.get(original_counselor_id, {}).get(
                    "name", "Name not available"
                ),
                "items": items[:50],
                "receivers": receivers,
                "page": page,
                "has_next": len(candidates) > 50
                or any(len([c for c in candidates if c[0] == k]) > 25 for k in SOURCE_KINDS),
            }
    except OperationalError as exc:
        if getattr(exc.__cause__, "sqlstate", None) in {"55P03", "40P01"}:
            raise ContinuityError("source_busy", 409) from None
        raise
