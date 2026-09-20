"""Purpose-built read-only projections for an authorized Counseling Context."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from compass.accounts.models import User
from compass.appointments.models import Appointment
from compass.call_slips.models import CallSlip
from compass.inventory.models import StudentInventory
from compass.inventory.services import InventoryStatus, get_current_inventory_status
from compass.organization.models import StudentAffiliation
from compass.referrals.models import Referral
from compass.routine_interviews.models import RoutineInterview
from compass.student_support.services import StudentSupportContext, build_student_support_context

from .context_access import CounselingContextAccess
from .models import CounselingSharedSummary


@dataclass(frozen=True, slots=True)
class ContextOrganizationReference:
    id: UUID
    code: str
    name: str


@dataclass(frozen=True, slots=True)
class ContextProgramReference:
    id: UUID
    code: str
    name: str


@dataclass(frozen=True, slots=True)
class ContextRoutineInterviewSummary:
    id: UUID
    entry_mode: str
    intake_status: str
    evaluation_status: str


@dataclass(frozen=True, slots=True)
class ContextEncounterSummary:
    id: UUID
    started_at: datetime
    ended_at: datetime


@dataclass(frozen=True, slots=True)
class CounselingContextOverview:
    student_id: UUID
    institutional_id: str | None
    display_name: str
    campus: ContextOrganizationReference | None
    college: ContextOrganizationReference | None
    program: ContextProgramReference | None
    year_level: int | None
    source_type: str
    source_id: UUID
    entry_mode: str
    delivery_mode: str
    valid_from: datetime
    valid_until: datetime
    routine_interview: ContextRoutineInterviewSummary | None
    encounter: ContextEncounterSummary | None
    available_sections: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CounselingContextInventoryResult:
    inventory_source_status: str
    available: bool
    inventory: StudentInventory | None


@dataclass(frozen=True, slots=True)
class CounselingContextHistoryItem:
    id: UUID
    kind: str
    occurred_at: datetime
    title: str
    status: str
    reference_code: str | None = None
    delivery_mode: str | None = None
    provider_id: UUID | None = None
    provider_display_name: str | None = None


@dataclass(frozen=True, slots=True)
class CounselingContextSharedSummary:
    id: UUID
    content: str
    published_at: datetime
    counseling_ended_at: datetime
    counselor_id: UUID
    counselor_display_name: str


def _student(access: CounselingContextAccess) -> User:
    return User.objects.select_related("role").get(pk=access.student_id)


def _routine_interview(access: CounselingContextAccess) -> RoutineInterview | None:
    if access.routine_interview_id is None:
        return None
    return (
        RoutineInterview.objects.select_related(
            "inventory__academic_year",
            "inventory__program",
            "counseling_encounter",
        )
        .filter(pk=access.routine_interview_id, student_id=access.student_id)
        .first()
    )


def _full_inventory_queryset():
    return StudentInventory.objects.select_related(
        "student",
        "student__role",
        "academic_year",
        "program",
        "program__college",
        "program__college__campus",
        "form_revision",
        "form_revision__family",
        "support_profile",
    ).prefetch_related(
        "family_members",
        "siblings",
        "education_entries",
        "organization_memberships",
        "transportation_entries",
        "geographic_locations",
        "reopen_events",
    )


def _inventory_source(
    access: CounselingContextAccess,
) -> tuple[str, StudentInventory | None]:
    routine = _routine_interview(access)
    if routine is not None:
        inventory = (
            _full_inventory_queryset()
            .filter(pk=routine.inventory_id, student_id=access.student_id)
            .first()
        )
        if inventory is None:
            return InventoryStatus.MISSING, None
        if inventory.submitted_at is None:
            return InventoryStatus.DRAFT, None
        return InventoryStatus.SUBMITTED, inventory

    status = get_current_inventory_status(_student(access))
    if status.status != InventoryStatus.SUBMITTED or status.inventory is None:
        return status.status, None
    return InventoryStatus.SUBMITTED, status.inventory


def _program_reference(inventory: StudentInventory | None) -> ContextProgramReference | None:
    if inventory is None or inventory.program is None:
        return None
    return ContextProgramReference(
        id=inventory.program_id,
        code=inventory.program.code,
        name=inventory.program.name,
    )


def get_context_overview(access: CounselingContextAccess) -> CounselingContextOverview:
    student = _student(access)
    affiliation = (
        StudentAffiliation.objects.select_related("college__campus")
        .filter(student_id=access.student_id)
        .first()
    )
    _status, inventory = _inventory_source(access)
    routine = _routine_interview(access)

    campus = None
    college = None
    if affiliation is not None:
        campus = ContextOrganizationReference(
            id=affiliation.college.campus_id,
            code=affiliation.college.campus.code,
            name=affiliation.college.campus.name,
        )
        college = ContextOrganizationReference(
            id=affiliation.college_id,
            code=affiliation.college.code,
            name=affiliation.college.name,
        )

    routine_summary = None
    if routine is not None:
        routine_summary = ContextRoutineInterviewSummary(
            id=routine.pk,
            entry_mode=routine.entry_mode,
            intake_status="SUBMITTED" if routine.intake_submitted_at else "DRAFT",
            evaluation_status="FINALIZED" if routine.evaluation_finalized_at else "DRAFT",
        )

    encounter_summary = None
    if access.encounter_id is not None:
        encounter = None
        if routine is not None and routine.counseling_encounter_id == access.encounter_id:
            encounter = routine.counseling_encounter
        if encounter is None:
            from .models import CounselingEncounter

            encounter = CounselingEncounter.objects.filter(pk=access.encounter_id).first()
        if encounter is not None:
            encounter_summary = ContextEncounterSummary(
                id=encounter.pk,
                started_at=encounter.started_at,
                ended_at=encounter.ended_at,
            )

    return CounselingContextOverview(
        student_id=student.pk,
        institutional_id=student.institutional_id,
        display_name=student.get_full_name(),
        campus=campus,
        college=college,
        program=_program_reference(inventory),
        year_level=inventory.year_level if inventory is not None else None,
        source_type=access.source_type.value,
        source_id=access.source_id,
        entry_mode=access.entry_mode,
        delivery_mode=access.delivery_mode,
        valid_from=access.valid_from,
        valid_until=access.valid_until,
        routine_interview=routine_summary,
        encounter=encounter_summary,
        available_sections=(
            "SUPPORT_INDICATORS",
            "INVENTORY",
            "HISTORY",
            "SHARED_SUMMARIES",
        ),
    )


def get_context_support_indicators(
    access: CounselingContextAccess,
) -> StudentSupportContext:
    return build_student_support_context(student=_student(access))


def get_context_inventory(
    access: CounselingContextAccess,
) -> CounselingContextInventoryResult:
    status, item = _inventory_source(access)
    if item is None or item.submitted_at is None:
        return CounselingContextInventoryResult(
            inventory_source_status=str(status),
            available=False,
            inventory=None,
        )
    return CounselingContextInventoryResult(
        inventory_source_status=InventoryStatus.SUBMITTED,
        available=True,
        inventory=item,
    )


def list_context_history(
    access: CounselingContextAccess,
    *,
    limit: int = 20,
) -> tuple[CounselingContextHistoryItem, ...]:
    bounded_limit = max(1, min(int(limit), 50))
    student_id = access.student_id
    rows: list[CounselingContextHistoryItem] = []

    appointments = (
        Appointment.objects.select_related("service", "provider")
        .filter(student_id=student_id)
        .order_by("-starts_at", "-id")[:bounded_limit]
    )
    rows.extend(
        CounselingContextHistoryItem(
            id=item.pk,
            kind="APPOINTMENT",
            occurred_at=item.starts_at,
            title=item.service.name,
            status=item.status,
            reference_code=item.reference_code,
            delivery_mode=item.delivery_mode,
            provider_id=item.provider_id,
            provider_display_name=item.provider.get_full_name(),
        )
        for item in appointments
    )

    referrals = Referral.objects.filter(student_id=student_id).order_by(
        "-received_at", "-created_at", "-id"
    )[:bounded_limit]
    rows.extend(
        CounselingContextHistoryItem(
            id=item.pk,
            kind="REFERRAL",
            occurred_at=item.received_at or item.created_at,
            title="Referral",
            status="RECEIVED" if item.received_at is not None else "RECORDED",
            reference_code=item.reference_code,
        )
        for item in referrals
    )

    call_slips = (
        CallSlip.objects.select_related("issued_by")
        .filter(student_id=student_id)
        .order_by("-report_at", "-id")[:bounded_limit]
    )
    rows.extend(
        CounselingContextHistoryItem(
            id=item.pk,
            kind="CALL_SLIP",
            occurred_at=item.report_at,
            title="Call Slip",
            status="ENDED" if item.interview_ended_at is not None else "PENDING",
            provider_id=item.issued_by_id,
            provider_display_name=item.issued_by.get_full_name(),
        )
        for item in call_slips
    )

    routine_interviews = (
        RoutineInterview.objects.select_related("counselor")
        .filter(student_id=student_id)
        .order_by("-created_at", "-id")[:bounded_limit]
    )
    rows.extend(
        CounselingContextHistoryItem(
            id=item.pk,
            kind="ROUTINE_INTERVIEW",
            occurred_at=item.created_at,
            title=f"{item.entry_mode.replace('_', ' ').title()} Routine Interview",
            status="SUBMITTED" if item.intake_submitted_at is not None else "DRAFT",
            delivery_mode=item.delivery_mode,
            provider_id=item.counselor_id,
            provider_display_name=item.counselor.get_full_name(),
        )
        for item in routine_interviews
    )

    rows.sort(key=lambda item: (item.occurred_at, str(item.id)), reverse=True)
    return tuple(rows[:bounded_limit])


def list_context_shared_summaries(
    access: CounselingContextAccess,
    *,
    limit: int = 20,
) -> tuple[CounselingContextSharedSummary, ...]:
    bounded_limit = max(1, min(int(limit), 50))
    rows = (
        CounselingSharedSummary.objects.select_related("encounter__counselor")
        .filter(
            encounter__student_id=access.student_id,
            published_at__isnull=False,
        )
        .order_by("-published_at", "-id")[:bounded_limit]
    )
    return tuple(
        CounselingContextSharedSummary(
            id=item.pk,
            content=item.content,
            published_at=item.published_at,
            counseling_ended_at=item.encounter.ended_at,
            counselor_id=item.encounter.counselor_id,
            counselor_display_name=item.encounter.counselor.get_full_name(),
        )
        for item in rows
    )


__all__ = [
    "ContextEncounterSummary",
    "ContextOrganizationReference",
    "ContextProgramReference",
    "ContextRoutineInterviewSummary",
    "CounselingContextHistoryItem",
    "CounselingContextInventoryResult",
    "CounselingContextOverview",
    "CounselingContextSharedSummary",
    "get_context_inventory",
    "get_context_overview",
    "get_context_support_indicators",
    "list_context_history",
    "list_context_shared_summaries",
]
