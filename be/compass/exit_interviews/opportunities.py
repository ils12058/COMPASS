"""GCO admission and privacy-minimized Student workspace status.

All transitions lock the Student first, as do response corrections and F4 creation.
This fence also serializes admission with revocation when no opportunity row exists yet.
"""

from __future__ import annotations

from uuid import UUID

from django.db import transaction
from django.db.models import CharField, OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from compass.accounts.models import User
from compass.accounts.services import is_current_student
from compass.audit.actions import (
    EXIT_INTERVIEW_OPPORTUNITY_OPENED,
    EXIT_INTERVIEW_OPPORTUNITY_REVOKED,
)
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.inventory.models import StudentInventory
from compass.operational_students import (
    InvalidOperationalStudentQuery,
    list_scoped_operational_students,
)
from compass.organization.access_scope import (
    is_head_guidance,
    resolve_operational_responsibility_scope,
)
from compass.organization.models import AcademicYear

from .confidential_content import read_opportunity_note, write_opportunity_note
from .models import (
    ExitInterview,
    ExitInterviewOpportunity,
    ExitInterviewOpportunitySource,
    ExitInterviewOpportunityStatus,
    ExitInterviewStatus,
)
from .services import (
    ExitInterviewCurrentStudentRequired,
    ExitInterviewNotFound,
    ExitInterviewNotPermitted,
    ExitInterviewOpportunityConflict,
    InvalidExitInterviewInput,
    _clean_search,
    _clean_text,
    _current_year,
    _pagination,
    _summary_queryset,
    _validate_student,
)

CAPABILITY = "exit_interviews.manage_opportunities"


def _validate_operator(actor: User) -> None:
    if (
        not getattr(actor, "pk", None)
        or not actor.is_active
        or not actor.has_capability(CAPABILITY)
    ):
        raise ExitInterviewNotPermitted(
            "Guidance Exit Interview opportunity authority is required."
        )


def _queryset():
    response = ExitInterview.objects.filter(
        student_id=OuterRef("student_id"), academic_year_id=OuterRef("academic_year_id")
    )
    return ExitInterviewOpportunity.objects.annotate(
        workflow_status=Coalesce(
            Subquery(response.values("status")[:1]), Value("NOT_STARTED"), output_field=CharField()
        ),
        last_submitted_at=Subquery(response.values("last_submitted_at")[:1]),
    ).select_related(
        "student",
        "academic_year",
        "opened_by",
        "revoked_by",
    )


def _audit(item, *, action, transition, context):
    record_event(
        context=context,
        action=action,
        outcome=AuditOutcome.SUCCESS,
        target_type="exitinterviews.exitinterviewopportunity",
        target_id=item.pk,
        metadata={
            "academic_year_id": str(item.academic_year_id),
            "source": item.source,
            "transition": transition,
        },
    )


def open_opportunity(
    *,
    actor: User,
    student_id: UUID,
    academic_year_id: UUID | None,
    source: str,
    note: str,
    context: AuditContext,
) -> ExitInterviewOpportunity:
    _validate_operator(actor)
    if source not in ExitInterviewOpportunitySource.values:
        raise InvalidExitInterviewInput("Choose Graduation or Manual as the opening reason.")
    note = _clean_text(note, "note", 1000)
    year = (
        _current_year()
        if academic_year_id is None
        else AcademicYear.objects.filter(pk=academic_year_id).first()
    )
    if year is None:
        raise InvalidExitInterviewInput("The selected Academic Year was not found.")
    with transaction.atomic():
        student = (
            User.objects.select_for_update(of=("self",))
            .select_related("role")
            .filter(pk=student_id)
            .first()
        )
        if student is None:
            raise ExitInterviewNotFound("The Student account was not found.")
        _validate_student(student)
        if not is_current_student(student):
            raise ExitInterviewCurrentStudentRequired(
                "Exit Interview access can only be opened for a current Student."
            )
        item = (
            ExitInterviewOpportunity.objects.select_for_update()
            .filter(student=student, academic_year=year)
            .first()
        )
        if item is not None:
            if item.source != source:
                raise ExitInterviewOpportunityConflict(
                    "An opportunity already exists for this Student and Academic Year with a "
                    "different source."
                )
            if item.status == ExitInterviewOpportunityStatus.COMPLETED:
                raise ExitInterviewOpportunityConflict(
                    "This Exit Interview is completed. Reopen the submitted response if a "
                    "correction is needed."
                )
            if item.status == ExitInterviewOpportunityStatus.OPEN:
                if read_opportunity_note(item) != note:
                    raise ExitInterviewOpportunityConflict(
                        "Access is already open. Review the existing opportunity before making "
                        "another change."
                    )
                return _queryset().get(pk=item.pk)
        record = ExitInterview.objects.filter(student=student, academic_year=year).first()
        if record is not None and record.status == ExitInterviewStatus.SUBMITTED:
            raise ExitInterviewOpportunityConflict(
                "This Student already has a submitted Exit Interview for the selected "
                "Academic Year."
            )
        now = timezone.now()
        if item is None:
            item = ExitInterviewOpportunity(
                student=student,
                academic_year=year,
                source=source,
                opened_by=actor,
                opened_at=now,
            )
            write_opportunity_note(item, note)
            item.save(force_insert=True)
            transition = "NONE -> OPEN"
        else:
            previous_note = read_opportunity_note(item)
            if previous_note != note:
                write_opportunity_note(item, note)
            item.status = ExitInterviewOpportunityStatus.OPEN
            item.opened_by = actor
            item.opened_at = now
            item.revoked_at = None
            item.revoked_by = None
            item.save(
                update_fields=[
                    "status",
                    "opened_by",
                    "opened_at",
                    "revoked_at",
                    "revoked_by",
                    "note_ciphertext",
                    "updated_at",
                ]
            )
            transition = "REVOKED -> OPEN"
        _audit(
            item, action=EXIT_INTERVIEW_OPPORTUNITY_OPENED, transition=transition, context=context
        )
        return _queryset().get(pk=item.pk)


def revoke_opportunity(
    *, actor: User, opportunity_id: UUID, context: AuditContext
) -> ExitInterviewOpportunity:
    _validate_operator(actor)
    with transaction.atomic():
        owner_id = (
            ExitInterviewOpportunity.objects.filter(pk=opportunity_id)
            .values_list("student_id", flat=True)
            .first()
        )
        if owner_id is None:
            raise ExitInterviewNotFound("The Exit Interview opportunity was not found.")
        User.objects.select_for_update().get(pk=owner_id)
        item = ExitInterviewOpportunity.objects.select_for_update().get(pk=opportunity_id)
        if item.status == ExitInterviewOpportunityStatus.REVOKED:
            return _queryset().get(pk=item.pk)
        if item.status != ExitInterviewOpportunityStatus.OPEN:
            raise ExitInterviewOpportunityConflict(
                "Only open Exit Interview access can be revoked."
            )
        read_opportunity_note(item)
        item.status = ExitInterviewOpportunityStatus.REVOKED
        item.revoked_at = timezone.now()
        item.revoked_by = actor
        item.save(update_fields=["status", "revoked_at", "revoked_by", "updated_at"])
        _audit(
            item,
            action=EXIT_INTERVIEW_OPPORTUNITY_REVOKED,
            transition="OPEN -> REVOKED",
            context=context,
        )
        return _queryset().get(pk=item.pk)


def get_opportunity(*, actor: User, opportunity_id: UUID) -> ExitInterviewOpportunity:
    _validate_operator(actor)
    item = _queryset().filter(pk=opportunity_id).first()
    if item is None:
        raise ExitInterviewNotFound("The Exit Interview opportunity was not found.")
    return item


def list_opportunities(
    *,
    actor: User,
    academic_year_id: UUID | None = None,
    current_year_only: bool = False,
    student_id: UUID | None = None,
    status: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 25,
):
    _validate_operator(actor)
    page, page_size = _pagination(page, page_size)
    term = _clean_search(search)
    queryset = _queryset()
    if academic_year_id:
        queryset = queryset.filter(academic_year_id=academic_year_id)
    if current_year_only:
        queryset = queryset.filter(academic_year__is_current=True)
    if student_id:
        queryset = queryset.filter(student_id=student_id)
    if status:
        if status not in ExitInterviewOpportunityStatus.values:
            raise InvalidExitInterviewInput("The opportunity status is not supported.")
        queryset = queryset.filter(status=status)
    if term:
        queryset = queryset.filter(
            Q(student__institutional_id__icontains=term)
            | Q(student__first_name__icontains=term)
            | Q(student__middle_name__icontains=term)
            | Q(student__last_name__icontains=term)
        )
    offset = (page - 1) * page_size
    rows = list(queryset.order_by("-opened_at", "id")[offset : offset + page_size + 1])
    return {
        "current_academic_year": AcademicYear.objects.filter(is_current=True).first(),
        "items": rows[:page_size],
        "page": page,
        "page_size": page_size,
        "has_next": len(rows) > page_size,
    }


def list_eligible_students(*, actor: User, search: str | None, page: int, page_size: int):
    _validate_operator(actor)
    try:
        return list_scoped_operational_students(
            college_ids=(
                None
                if is_head_guidance(actor)
                else resolve_operational_responsibility_scope(actor).college_ids
            ),
            search=search,
            page=page,
            page_size=page_size,
        )
    except InvalidOperationalStudentQuery as exc:
        raise InvalidExitInterviewInput(str(exc)) from exc


def has_student_workspace(student: User) -> bool:
    if (
        not student.is_active
        or student.role.code != "STUDENT"
        or not student.has_capability("exit_interviews.view_self")
    ):
        return False
    if ExitInterview.objects.filter(student_id=student.pk).exists():
        return True
    return (
        is_current_student(student)
        and ExitInterviewOpportunity.objects.filter(
            student_id=student.pk,
            academic_year__is_current=True,
            status=ExitInterviewOpportunityStatus.OPEN,
        ).exists()
    )


def get_my_status(student: User, *, structural: bool = False) -> dict[str, object]:
    _validate_student(student)
    year = AcademicYear.objects.filter(is_current=True).first()
    records = (
        ExitInterview.objects.only(
            "id", "status", "opportunity_id", "first_submitted_at", "last_submitted_at"
        )
        if structural
        else _summary_queryset()
    )
    opportunities = (
        ExitInterviewOpportunity.objects.only("id", "status", "source", "opened_at")
        if structural
        else _queryset()
    )
    record = records.filter(student=student, academic_year=year).first() if year else None
    opportunity = (
        opportunities.filter(student=student, academic_year=year).first() if year else None
    )
    inventory_submitted = bool(
        year
        and StudentInventory.objects.filter(
            student=student, academic_year=year, submitted_at__isnull=False
        ).exists()
    )
    current = is_current_student(student) and student.has_capability("exit_interviews.manage_self")
    opened = opportunity is not None and opportunity.status == ExitInterviewOpportunityStatus.OPEN
    graduation = (
        opportunity is not None and opportunity.source == ExitInterviewOpportunitySource.GRADUATION
    )
    return {
        "academic_year": year,
        "opportunity": opportunity,
        "current_record": record,
        "has_records": ExitInterview.objects.filter(student=student).exists(),
        "inventory_submitted": inventory_submitted,
        "can_start": bool(current and opened and inventory_submitted and record is None),
        "can_edit_current": bool(
            current
            and record
            and record.status == ExitInterviewStatus.DRAFT
            and (record.opportunity_id is None or record.first_submitted_at is not None or opened)
        ),
        "graduation_good_moral_blocked": bool(
            is_current_student(student)
            and graduation
            and (
                record is None
                or record.status != ExitInterviewStatus.SUBMITTED
                or record.last_submitted_at is None
            )
        ),
    }
