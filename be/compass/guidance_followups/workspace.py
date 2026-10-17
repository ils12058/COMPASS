"""Authorized workspace options and aggregate projections, without protected free text."""

from dataclasses import dataclass
from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from compass.accounts.models import User
from compass.operational_students import list_scoped_operational_students
from compass.organization.access_scope import (
    is_head_guidance,
    resolve_operational_responsibility_scope,
)
from compass.organization.models import StudentAffiliation

from . import policy
from .errors import FollowUpInvalid, FollowUpNotFound
from .models import FollowUpCategory, FollowUpSource, FollowUpStatus, GuidanceFollowUp


@dataclass(frozen=True)
class OptionPage:
    items: tuple
    page: int
    page_size: int
    has_next: bool


def pagination(page, page_size):
    if not 1 <= page <= 100 or not 1 <= page_size <= 50:
        raise FollowUpInvalid("The requested page is unavailable.")


def eligible_students(*, actor, search=None, page=1, page_size=20):
    actor = policy.current_actor(actor, manage=True)
    pagination(page, page_size)
    return list_scoped_operational_students(
        college_ids=None
        if is_head_guidance(actor)
        else resolve_operational_responsibility_scope(actor).college_ids,
        search=search,
        page=page,
        page_size=page_size,
    )


def source_context(*, actor, source_kind, source_id):
    actor = policy.current_actor(actor)
    if source_kind == FollowUpSource.COUNSELING_ENCOUNTER:
        from compass.counseling.models import CounselingEncounter

        source = CounselingEncounter.objects.filter(pk=source_id).first()
    elif source_kind == FollowUpSource.ROUTINE_INTERVIEW:
        from compass.routine_interviews.models import RoutineInterview

        source = RoutineInterview.objects.filter(pk=source_id).first()
    elif source_kind == FollowUpSource.REFERRAL:
        from compass.referrals.models import Referral

        source = Referral.objects.filter(pk=source_id).first()
    else:
        raise FollowUpInvalid("The related record is unsupported.")
    if source is None:
        raise FollowUpNotFound("The related record is unavailable.")
    student = policy.valid_student(source.student_id)
    policy.require_source(actor, kind=source_kind, source_id=source_id, student_id=student.pk)
    can_create = actor.has_capability("guidance_followups.manage")
    if can_create:
        try:
            policy.require_source(
                actor, kind=source_kind, source_id=source_id, student_id=student.pk, manage=True
            )
        except FollowUpNotFound:
            can_create = False
    category = (
        FollowUpCategory.REFERRAL_ACTION
        if source_kind == FollowUpSource.REFERRAL
        else FollowUpCategory.COUNSELING
    )
    return {
        "source_kind": source_kind,
        "source_id": source_id,
        "student_id": student.pk,
        "student_name": student.get_full_name(),
        "category": category,
        "visibility": policy.classify(source_kind=source_kind, category=category),
        "can_create": can_create,
    }


def eligible_assignees(
    *, actor, student_id, category, source_kind=None, source_id=None, page=1, page_size=20
):
    actor = policy.current_actor(actor, manage=True)
    pagination(page, page_size)
    student = policy.valid_student(student_id)
    classification = policy.classify(source_kind=source_kind, category=category)
    if source_kind:
        policy.require_source(
            actor, kind=source_kind, source_id=source_id, student_id=student.pk, manage=True
        )
    elif not policy.in_operational_scope(actor, student.pk):
        raise FollowUpNotFound("The Student is unavailable.")
    candidates = User.objects.filter(is_active=True, role__code__in=policy.ROLES).select_related(
        "role"
    )
    if classification == "COUNSELOR_CONFIDENTIAL":
        candidates = candidates.filter(pk=actor.pk)
    else:
        college_id = (
            StudentAffiliation.objects.filter(
                student=student, college__is_active=True, college__campus__is_active=True
            )
            .values_list("college_id", flat=True)
            .first()
        )
        head = Q(designation_assignments__designation__code="HEAD_GUIDANCE_COUNSELOR")
        candidates = candidates.filter(
            head
            | Q(organization_counselor_responsibilities__college_id=college_id)
            | Q(
                organization_staff_supervision__supervisor__organization_counselor_responsibilities__college_id=college_id
            )
            | Q(
                organization_staff_supervision__supervisor__designation_assignments__designation__code="HEAD_GUIDANCE_COUNSELOR"
            )
        ).distinct()
    # Scope the small staff directory in SQL first. Effective capability overrides and inherited
    # responsibility are then rechecked before the page boundary; memory stays bounded.
    end = page * page_size
    accepted = []
    count = 0
    for candidate in candidates.order_by("last_name", "first_name", "id").iterator(chunk_size=50):
        try:
            policy.require_assignee(
                candidate.pk,
                student_id=student.pk,
                visibility=classification,
                source_kind=source_kind,
                source_id=source_id,
            )
        except FollowUpInvalid:
            continue
        if count >= (page - 1) * page_size:
            accepted.append(candidate)
        count += 1
        if count > end:
            break
    return OptionPage(tuple(accepted[:page_size]), page, page_size, count > end)


def reporting(*, actor, period_start=None, period_end=None, horizon_days=7):
    actor = policy.current_actor(actor)
    now = timezone.now()
    if not 1 <= horizon_days <= 90:
        raise FollowUpInvalid("Choose a reporting horizon between 1 and 90 days.")
    start = period_start or now - timedelta(days=30)
    end = period_end or now
    if (
        timezone.is_naive(start)
        or timezone.is_naive(end)
        or not start < end
        or end - start > timedelta(days=366)
    ):
        raise FollowUpInvalid("Choose an aware reporting period of at most 366 days.")
    qs = policy.scope(actor, GuidanceFollowUp.objects.all())
    pending = Q(status=FollowUpStatus.PENDING)
    totals = qs.aggregate(
        pending=Count("pk", filter=pending),
        completed=Count("pk", filter=Q(status="COMPLETED")),
        cancelled=Count("pk", filter=Q(status="CANCELLED")),
        overdue=Count("pk", filter=pending & Q(due_at__lt=now)),
        due_soon=Count(
            "pk",
            filter=pending & Q(due_at__gte=now, due_at__lte=now + timedelta(days=horizon_days)),
        ),
        completed_in_period=Count(
            "pk", filter=Q(status="COMPLETED", completed_at__gte=start, completed_at__lt=end)
        ),
    )
    categories = list(qs.values("category").annotate(count=Count("pk")).order_by("category"))
    return {
        **totals,
        "period_start": start,
        "period_end": end,
        "horizon_days": horizon_days,
        "generated_at": now,
        "categories": categories,
    }
