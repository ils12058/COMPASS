"""Transactional Routine Interview workflows and privacy/resource invariants."""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import F, Q
from django.utils import timezone

from compass.accounts.models import StudentLifecycleStatus, User
from compass.accounts.services import is_current_student
from compass.appointments.models import Appointment, AppointmentStatus
from compass.audit.actions import (
    ROUTINE_INTERVIEW_CREATED,
    ROUTINE_INTERVIEW_ENCOUNTER_LINKED,
    ROUTINE_INTERVIEW_EVALUATION_FINALIZED,
    ROUTINE_INTERVIEW_INTAKE_SUBMITTED,
)
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.common.ordering import parse_ordering
from compass.counseling.models import CounselingEncounter, CounselingEntryMode
from compass.counseling.services import (
    CounselingConfigurationConflict,
    get_counseling_service,
)
from compass.institutional_forms.services import (
    InstitutionalFormConflict,
    get_active_supported_form_revision,
)
from compass.inventory.models import StudentInventory
from compass.notifications.policy import NotificationEvent
from compass.notifications.services import create_notification_for_event
from compass.organization.academic_years import get_current_academic_year
from compass.organization.models import AcademicYear
from compass.service_catalog.models import DeliveryMode, Service
from compass.service_catalog.services import (
    service_counselor_eligible,
    service_supports_delivery_mode,
)

from .content import (
    EVALUATION_FIELDS,
    INTAKE_FIELDS,
    RATING_FIELDS,
    InvalidRoutineContent,
    initial_content,
    read_evaluation,
    read_intake,
    write_evaluation,
    write_intake,
)
from .errors import RoutineInterviewError
from .matching import (
    RoutineEncounterFacts,
    RoutineEncounterMatchIssue,
    routine_interview_encounter_match_issue,
    routine_interview_encounter_match_issue_for_facts,
    routine_interview_encounter_matches,
)
from .models import RoutineConcern, RoutineInterview

ROUTINE_FORM_FAMILY_KEY = "routine_interview"
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50
MAX_SEARCH_LENGTH = 160
DIRECT_ENTRY_MODES = frozenset(
    {
        CounselingEntryMode.WALK_IN,
        CounselingEntryMode.CALLED_IN,
        CounselingEntryMode.REFERRED,
    }
)


class RoutineInterviewNotFound(RoutineInterviewError):
    pass


class RoutineInterviewNotPermitted(RoutineInterviewError):
    pass


class InvalidRoutineInterviewInput(RoutineInterviewError):
    pass


class RoutineInterviewAppointmentInvalid(RoutineInterviewError):
    pass


class RoutineInterviewParentClosed(RoutineInterviewError):
    pass


class RoutineInterviewCurrentStudentRequired(RoutineInterviewError):
    pass


class RoutineInterviewIntakeSubmitted(RoutineInterviewError):
    pass


class RoutineInterviewIntakeRequired(RoutineInterviewError):
    pass


class RoutineInterviewEvaluationFinalized(RoutineInterviewError):
    pass


class RoutineInterviewEncounterRequired(RoutineInterviewError):
    pass


class RoutineInterviewEncounterMismatch(RoutineInterviewError):
    pass


class RoutineInterviewEncounterConflict(RoutineInterviewEncounterMismatch):
    """A different Encounter is already linked, or the Encounter belongs to another Routine."""


class RoutineInterviewCreationConflict(RoutineInterviewError):
    pass


class RoutineInterviewFormRevisionUnsupported(RoutineInterviewError):
    pass


class RoutineEncounterLinkSource(StrEnum):
    """How a Routine Interview's Counseling Encounter link was established (audit metadata)."""

    # Automatic: the Routine Interview and the Encounter share one Counseling Appointment.
    APPOINTMENT = "APPOINTMENT"
    # Automatic: the Encounter was recorded from this Routine Interview's Counseling context.
    ROUTINE_INTERVIEW_CONTEXT = "ROUTINE_INTERVIEW_CONTEXT"
    # Compatibility: an Appointment-backed record from before automatic linking, reconciled at
    # finalization against the single Encounter its Appointment admits.
    APPOINTMENT_RECONCILIATION = "APPOINTMENT_RECONCILIATION"
    # Exceptional recovery: a direct record whose Encounter was recorded outside its Routine
    # context, named explicitly by the assigned Counselor at finalization.
    COUNSELOR_RECOVERY = "COUNSELOR_RECOVERY"


class RoutineWorkflowState(StrEnum):
    ACTIVE = "ACTIVE"
    CLOSED_APPOINTMENT_CANCELLED = "CLOSED_APPOINTMENT_CANCELLED"
    CLOSED_APPOINTMENT_NO_SHOW = "CLOSED_APPOINTMENT_NO_SHOW"


class RoutineInterviewOrdering(StrEnum):
    """Closed orderings for a Counselor's assigned Routine Interviews (ADR-090).

    Pending evaluations are an action queue: waiting is measured from intake submission, so newer
    submissions never bury older unfinished evaluations.
    """

    OLDEST_WAITING = "OLDEST_WAITING"
    NEWEST_SUBMITTED = "NEWEST_SUBMITTED"
    RECENTLY_FINALIZED = "RECENTLY_FINALIZED"
    NEWEST_CREATED = "NEWEST_CREATED"
    STUDENT_ASC = "STUDENT_ASC"
    STUDENT_DESC = "STUDENT_DESC"


_ROUTINE_STUDENT_NAME = ("student__last_name", "student__first_name", "student__middle_name")
_ROUTINE_ORDER_BY: dict[RoutineInterviewOrdering, tuple] = {
    RoutineInterviewOrdering.OLDEST_WAITING: (
        F("intake_submitted_at").asc(nulls_last=True),
        "created_at",
        "id",
    ),
    RoutineInterviewOrdering.NEWEST_SUBMITTED: (
        F("intake_submitted_at").desc(nulls_last=True),
        "-created_at",
        "-id",
    ),
    RoutineInterviewOrdering.RECENTLY_FINALIZED: (
        F("evaluation_finalized_at").desc(nulls_last=True),
        F("intake_submitted_at").desc(nulls_last=True),
        "-id",
    ),
    RoutineInterviewOrdering.NEWEST_CREATED: ("-created_at", "-id"),
    RoutineInterviewOrdering.STUDENT_ASC: (*_ROUTINE_STUDENT_NAME, "id"),
    RoutineInterviewOrdering.STUDENT_DESC: (
        *(f"-{field}" for field in _ROUTINE_STUDENT_NAME),
        "-id",
    ),
}


def _routine_list_ordering(
    value: str | RoutineInterviewOrdering | None,
    *,
    intake_status: str | None,
    evaluation_status: str | None,
) -> RoutineInterviewOrdering:
    """Finalized evaluations read as history; submitted intakes awaiting evaluation as a queue."""

    if evaluation_status == "FINALIZED":
        default = RoutineInterviewOrdering.RECENTLY_FINALIZED
    elif intake_status == "SUBMITTED":
        default = RoutineInterviewOrdering.OLDEST_WAITING
    else:
        default = RoutineInterviewOrdering.NEWEST_CREATED
    return parse_ordering(
        value, RoutineInterviewOrdering, default=default, error=InvalidRoutineInterviewInput
    )


@dataclass(frozen=True, slots=True)
class RoutineInterviewPage:
    items: tuple[RoutineInterview, ...]
    page: int
    page_size: int
    has_next: bool
    ordering: RoutineInterviewOrdering | None = None


@dataclass(frozen=True, slots=True)
class RoutineDirectCreationOptions:
    service: Service
    delivery_modes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RoutineDirectStudentCandidate:
    student: User
    # The current Academic Year's submitted Inventory, when one exists. Never a draft.
    inventory: StudentInventory | None


@dataclass(frozen=True, slots=True)
class RoutineInitiationContext:
    academic_year: AcademicYear | None
    inventory: StudentInventory | None


@dataclass(frozen=True, slots=True)
class RoutineDirectStudentCandidatePage:
    items: tuple[RoutineDirectStudentCandidate, ...]
    page: int
    page_size: int
    has_next: bool


@dataclass(frozen=True, slots=True)
class RoutineEncounterCandidatePage:
    items: tuple[CounselingEncounter, ...]
    page: int
    page_size: int
    has_next: bool


def _queryset():
    return RoutineInterview.objects.select_related(
        "student",
        "student__role",
        "counselor",
        "counselor__role",
        "inventory",
        "inventory__academic_year",
        "academic_year",
        "appointment",
        "appointment__service",
        "counseling_encounter",
        "counseling_encounter__service",
        "form_revision",
        "form_revision__family",
        "created_by",
    )


CLOSED_PARENT_STATES = {
    AppointmentStatus.CANCELLED: RoutineWorkflowState.CLOSED_APPOINTMENT_CANCELLED,
    AppointmentStatus.NO_SHOW: RoutineWorkflowState.CLOSED_APPOINTMENT_NO_SHOW,
}


def actionable_parent_filter():
    """SQL equivalent of the canonical Routine parent actionability."""
    return ~Q(appointment__status__in=tuple(CLOSED_PARENT_STATES))


def routine_workflow_state(item: RoutineInterview) -> RoutineWorkflowState:
    """Derive Routine actionability from its authoritative parent Appointment outcome."""

    if item.appointment_id is None:
        return RoutineWorkflowState.ACTIVE
    return CLOSED_PARENT_STATES.get(item.appointment.status, RoutineWorkflowState.ACTIVE)


def _require_actionable_parent(
    item: RoutineInterview,
    *,
    lock_parent: bool = False,
) -> None:
    """Reject mutations when an Appointment-backed Routine has a terminal invalid parent."""

    if item.appointment_id is None:
        return
    queryset = Appointment.objects.only("status")
    if lock_parent:
        queryset = queryset.select_for_update(of=("self",))
    status = queryset.values_list("status", flat=True).get(pk=item.appointment_id)
    if CLOSED_PARENT_STATES.get(status) == RoutineWorkflowState.CLOSED_APPOINTMENT_CANCELLED:
        raise RoutineInterviewParentClosed(
            "This Routine Interview is no longer active because the Appointment was cancelled."
        )
    if CLOSED_PARENT_STATES.get(status) == RoutineWorkflowState.CLOSED_APPOINTMENT_NO_SHOW:
        raise RoutineInterviewParentClosed(
            "This Routine Interview is no longer active because the Appointment "
            "was marked as no-show."
        )


def _lock_users(*user_ids: UUID) -> dict[UUID, User]:
    unique_ids = sorted(set(user_ids), key=str)
    rows = list(
        User.objects.select_for_update(of=("self",))
        .select_related("role")
        .filter(pk__in=unique_ids)
        .order_by("pk")
    )
    by_id = {row.pk: row for row in rows}
    if len(by_id) != len(unique_ids):
        raise RoutineInterviewNotFound("A Routine Interview participant was not found.")
    return by_id


def _validate_student(student: User) -> None:
    if not student.is_active or student.role.code != "STUDENT":
        raise RoutineInterviewNotPermitted("An active Student account is required.")


def _require_current_student(student: User) -> None:
    if not is_current_student(student):
        raise RoutineInterviewCurrentStudentRequired(
            "Current Student lifecycle is required for this Routine Interview action."
        )


def _validate_counselor(counselor: User) -> None:
    if not counselor.is_active or counselor.role.code != "COUNSELOR":
        raise RoutineInterviewNotPermitted("An active Counselor account is required.")


def _normalize_delivery_mode(value: str | DeliveryMode) -> str:
    normalized = value.value if isinstance(value, DeliveryMode) else value
    if normalized not in DeliveryMode.values:
        raise InvalidRoutineInterviewInput("delivery_mode must be IN_PERSON or ONLINE.")
    return str(normalized)


def _normalize_direct_entry_mode(value: str | CounselingEntryMode) -> str:
    normalized = value.value if isinstance(value, CounselingEntryMode) else value
    if normalized not in DIRECT_ENTRY_MODES:
        raise InvalidRoutineInterviewInput(
            "Direct Routine Interview entry_mode must be WALK_IN, CALLED_IN, or REFERRED."
        )
    return str(normalized)


def _initiation_context(student: User) -> RoutineInitiationContext:
    """Resolve the optional context a new Routine Interview records at initiation (ADR-088).

    The configured current Academic Year, if any, and that year's submitted Inventory, if any.
    Neither is a prerequisite: a missing year, or a missing, draft, or reopened Inventory, binds
    nothing. The submitted row is locked so a concurrent reopen cannot make the binding false.
    """

    current = get_current_academic_year()
    if current is None:
        return RoutineInitiationContext(academic_year=None, inventory=None)
    inventory = (
        StudentInventory.objects.select_for_update(of=("self",))
        .filter(student_id=student.pk, academic_year_id=current.pk, submitted_at__isnull=False)
        .first()
    )
    return RoutineInitiationContext(academic_year=current, inventory=inventory)


def _optional_form_revision():
    try:
        return get_active_supported_form_revision(ROUTINE_FORM_FAMILY_KEY)
    except InstitutionalFormConflict as exc:
        raise RoutineInterviewFormRevisionUnsupported(
            "The active Routine Interview Form Revision is not supported by this COMPASS version."
        ) from exc


def _active_counseling_service(*, for_update: bool = False):
    try:
        return get_counseling_service(require_active=True, for_update=for_update)
    except CounselingConfigurationConflict as exc:
        raise RoutineInterviewAppointmentInvalid(str(exc)) from exc


def _validate_counseling_provider(*, service, counselor: User) -> None:
    """NEW direct Routine Interviews follow CURRENT Service qualification (ADR-089)."""

    if service.code != "COUNSELING" or not service.is_active:
        raise RoutineInterviewAppointmentInvalid(
            "Routine Interview requires the active canonical COUNSELING Service."
        )
    if not service_counselor_eligible(service, counselor):
        raise RoutineInterviewAppointmentInvalid(
            "The assigned provider is not eligible for the COUNSELING Service."
        )


def _validate_counseling_service(*, service, counselor: User, delivery_mode: str) -> None:
    _validate_counseling_provider(service=service, counselor=counselor)
    if not service_supports_delivery_mode(service, delivery_mode):
        raise RoutineInterviewAppointmentInvalid(
            "The COUNSELING Service does not support this delivery mode."
        )


def _validate_page(page: int, page_size: int) -> tuple[int, int]:
    if type(page) is not int or page < 1:
        raise InvalidRoutineInterviewInput("page must be at least 1.")
    if type(page_size) is not int or not 1 <= page_size <= MAX_PAGE_SIZE:
        raise InvalidRoutineInterviewInput(f"page_size must be between 1 and {MAX_PAGE_SIZE}.")
    return page, page_size


def _clean_search(search: str | None) -> str:
    if search is None:
        return ""
    if not isinstance(search, str):
        raise InvalidRoutineInterviewInput("search must be text.")
    cleaned = search.strip()
    if len(cleaned) > MAX_SEARCH_LENGTH:
        raise InvalidRoutineInterviewInput(
            f"search must be at most {MAX_SEARCH_LENGTH} characters."
        )
    return cleaned


def _academic_year_label(item: RoutineInterview) -> str | None:
    return item.academic_year.label if item.academic_year_id is not None else None


def _safe_creation_metadata(item: RoutineInterview) -> dict[str, object]:
    revision = item.form_revision
    return {
        "entry_mode": item.entry_mode,
        "academic_year": _academic_year_label(item),
        "inventory_bound": item.inventory_id is not None,
        "appointment_id": str(item.appointment_id) if item.appointment_id else None,
        "form_revision_id": str(revision.pk) if revision is not None else None,
    }


def ensure_for_appointment(
    *,
    student: User,
    appointment_id: UUID,
    context: AuditContext,
) -> RoutineInterview:
    _validate_student(student)
    with transaction.atomic():
        appointment = (
            Appointment.objects.select_for_update(of=("self",))
            .select_related("student__role", "provider__role", "service")
            .filter(pk=appointment_id)
            .first()
        )
        if appointment is None or appointment.student_id != student.pk:
            raise RoutineInterviewAppointmentInvalid(
                "The requested Counseling Appointment is not available to this Student."
            )

        existing = RoutineInterview.objects.filter(appointment_id=appointment.pk).first()
        if existing is not None:
            if existing.student_id != student.pk:
                raise RoutineInterviewAppointmentInvalid(
                    "The Appointment is already bound to another Routine Interview."
                )
            return _queryset().get(pk=existing.pk)

        _require_current_student(student)
        if appointment.status != AppointmentStatus.SCHEDULED:
            raise RoutineInterviewAppointmentInvalid("The Appointment must be SCHEDULED.")
        counselor = appointment.provider
        _validate_counselor(counselor)
        counseling_service = _active_counseling_service(for_update=True)
        if appointment.service_id != counseling_service.pk:
            raise RoutineInterviewAppointmentInvalid(
                "The Appointment does not use the canonical COUNSELING Service."
            )
        # The saved Appointment anchors the Routine Interview: later changes to the Service's
        # delivery modes or provider coverage do not undo it (ADR-089).

        initiation = _initiation_context(student)
        revision = _optional_form_revision()
        routine_interview_id = uuid.uuid4()
        try:
            with transaction.atomic():
                item = RoutineInterview.objects.create(
                    id=routine_interview_id,
                    student=student,
                    counselor=counselor,
                    inventory=initiation.inventory,
                    academic_year=initiation.academic_year,
                    appointment=appointment,
                    form_revision=revision,
                    entry_mode=CounselingEntryMode.APPOINTMENT,
                    delivery_mode=appointment.delivery_mode,
                    created_by=student,
                    **initial_content(routine_interview_id),
                )
        except IntegrityError:
            concurrent = RoutineInterview.objects.filter(appointment_id=appointment.pk).first()
            if concurrent is None:
                raise RoutineInterviewCreationConflict(
                    "The Routine Interview could not be created safely; retry the request."
                ) from None
            return _queryset().get(pk=concurrent.pk)

        record_event(
            context=context,
            action=ROUTINE_INTERVIEW_CREATED,
            outcome=AuditOutcome.SUCCESS,
            target_type="routine.interview",
            target_id=item.pk,
            metadata=_safe_creation_metadata(
                RoutineInterview.objects.select_related("academic_year", "form_revision").get(
                    pk=item.pk
                )
            ),
        )

        # An Encounter already recorded for this Appointment belongs to this Routine Interview.
        # SKIP LOCKED, because an Encounter correction holds that row while it waits for this
        # Appointment lock; it links the Encounter itself after this commits. In the rare case
        # another writer holds it, finalization reconciles the Appointment's single Encounter.
        encounter = (
            CounselingEncounter.objects.select_for_update(of=("self",), skip_locked=True)
            .select_related("service")
            .filter(appointment_id=appointment.pk)
            .first()
        )
        if encounter is not None:
            link_appointment_encounter(item=item, encounter=encounter, context=context)
        return _queryset().get(pk=item.pk)


def _validate_idempotency_key(value: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 255:
        raise InvalidRoutineInterviewInput(
            "Idempotency-Key must be printable, trimmed, and at most 255 characters."
        )
    if value.strip() != value or not value.isprintable():
        raise InvalidRoutineInterviewInput(
            "Idempotency-Key must be printable, trimmed, and at most 255 characters."
        )
    return value


def _creation_digest(*, actor_id: UUID, key: str) -> str:
    return hashlib.sha256(f"{actor_id}\0{key}".encode()).hexdigest()


def create_direct(
    *,
    counselor: User,
    student_id: UUID,
    entry_mode: str,
    delivery_mode: str,
    idempotency_key: str,
    request_fingerprint: str,
    context: AuditContext,
) -> RoutineInterview:
    _validate_counselor(counselor)
    normalized_entry = _normalize_direct_entry_mode(entry_mode)
    normalized_delivery = _normalize_delivery_mode(delivery_mode)
    key = _validate_idempotency_key(idempotency_key)
    if len(request_fingerprint) != 64 or any(
        char not in "0123456789abcdef" for char in request_fingerprint
    ):
        raise InvalidRoutineInterviewInput("The direct-create request fingerprint is invalid.")
    digest = _creation_digest(actor_id=counselor.pk, key=key)

    with transaction.atomic():
        existing = (
            RoutineInterview.objects.select_for_update()
            .filter(direct_creation_key_digest=digest)
            .first()
        )
        if existing is not None:
            if existing.direct_request_fingerprint != request_fingerprint:
                raise RoutineInterviewCreationConflict(
                    "The Idempotency-Key was already used for a different "
                    "Routine Interview request."
                )
            return _queryset().get(pk=existing.pk)

        locked = _lock_users(counselor.pk, student_id)
        student = locked[student_id]
        locked_counselor = locked[counselor.pk]
        _validate_student(student)
        _require_current_student(student)
        _validate_counselor(locked_counselor)

        service = _active_counseling_service(for_update=True)
        _validate_counseling_service(
            service=service,
            counselor=locked_counselor,
            delivery_mode=normalized_delivery,
        )
        initiation = _initiation_context(student)
        revision = _optional_form_revision()
        routine_interview_id = uuid.uuid4()

        try:
            # Keep the uniqueness race inside its own savepoint. If PostgreSQL rejects the insert,
            # the outer transaction remains usable for the idempotent recovery lookup below.
            with transaction.atomic():
                item = RoutineInterview.objects.create(
                    id=routine_interview_id,
                    student=student,
                    counselor=locked_counselor,
                    inventory=initiation.inventory,
                    academic_year=initiation.academic_year,
                    appointment=None,
                    form_revision=revision,
                    entry_mode=normalized_entry,
                    delivery_mode=normalized_delivery,
                    created_by=locked_counselor,
                    direct_creation_key_digest=digest,
                    direct_request_fingerprint=request_fingerprint,
                    **initial_content(routine_interview_id),
                )
        except IntegrityError:
            concurrent = RoutineInterview.objects.filter(direct_creation_key_digest=digest).first()
            if concurrent is None:
                raise RoutineInterviewCreationConflict(
                    "The Routine Interview could not be created safely; retry the request."
                ) from None
            if concurrent.direct_request_fingerprint != request_fingerprint:
                raise RoutineInterviewCreationConflict(
                    "The Idempotency-Key was already used for a different "
                    "Routine Interview request."
                ) from None
            return _queryset().get(pk=concurrent.pk)

        item_for_audit = RoutineInterview.objects.select_related(
            "academic_year", "form_revision"
        ).get(pk=item.pk)
        record_event(
            context=context,
            action=ROUTINE_INTERVIEW_CREATED,
            outcome=AuditOutcome.SUCCESS,
            target_type="routine.interview",
            target_id=item.pk,
            metadata=_safe_creation_metadata(item_for_audit),
        )
        create_notification_for_event(
            recipient=student,
            event=NotificationEvent.ROUTINE_INTERVIEW_INTAKE_READY,
            source_type="routine_interview",
            source_id=item.pk,
            target_type="ROUTINE_INTERVIEW",
            target_id=item.pk,
        )
        return _queryset().get(pk=item.pk)


def list_my_appointment_candidates(student: User) -> tuple[Appointment, ...]:
    _validate_student(student)
    _require_current_student(student)
    _optional_form_revision()

    # Each scheduled Counseling Appointment includes a Routine Interview under its saved
    # provenance, whatever the Service's current delivery modes or provider coverage (ADR-089).
    service = _active_counseling_service()
    queryset = (
        Appointment.objects.select_related("provider", "provider__role", "service")
        .filter(
            student_id=student.pk,
            status=AppointmentStatus.SCHEDULED,
            service_id=service.pk,
            provider__is_active=True,
            provider__role__code="COUNSELOR",
            routine_interview__isnull=True,
        )
        .order_by("starts_at", "id")
    )
    return tuple(queryset)


def get_direct_creation_options(counselor: User) -> RoutineDirectCreationOptions:
    _validate_counselor(counselor)
    _optional_form_revision()
    service = _active_counseling_service()
    _validate_counseling_provider(service=service, counselor=counselor)
    delivery_modes = tuple(
        service.delivery_mode_assignments.order_by("mode").values_list("mode", flat=True)
    )
    if not delivery_modes:
        raise RoutineInterviewAppointmentInvalid(
            "The canonical COUNSELING Service has no supported delivery mode."
        )
    return RoutineDirectCreationOptions(service=service, delivery_modes=delivery_modes)


def list_direct_student_candidates(
    *,
    counselor: User,
    search: str | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> RoutineDirectStudentCandidatePage:
    _validate_counselor(counselor)
    _optional_form_revision()
    get_direct_creation_options(counselor)
    page, page_size = _validate_page(page, page_size)
    term = _clean_search(search)

    # Eligibility comes from the Student account, never from an Inventory (ADR-088).
    queryset = User.objects.select_related("role").filter(
        is_active=True,
        role__code="STUDENT",
        student_lifecycle_status=StudentLifecycleStatus.CURRENT,
    )
    for token in term.split():
        queryset = queryset.filter(
            Q(institutional_id__icontains=token)
            | Q(first_name__icontains=token)
            | Q(middle_name__icontains=token)
            | Q(last_name__icontains=token)
        )
    queryset = queryset.order_by("last_name", "first_name", "middle_name", "pk")
    offset = (page - 1) * page_size
    rows = list(queryset[offset : offset + page_size + 1])
    students = rows[:page_size]

    # Optional context only: the current year's submitted Inventory. Drafts and reopened
    # Inventories contribute nothing, and Program is never derived from affiliation.
    submitted: dict[UUID, StudentInventory] = {}
    current = get_current_academic_year()
    if current is not None and students:
        submitted = {
            item.student_id: item
            for item in StudentInventory.objects.select_related("academic_year").filter(
                academic_year_id=current.pk,
                submitted_at__isnull=False,
                student_id__in=[student.pk for student in students],
            )
        }
    return RoutineDirectStudentCandidatePage(
        tuple(
            RoutineDirectStudentCandidate(student=student, inventory=submitted.get(student.pk))
            for student in students
        ),
        page,
        page_size,
        len(rows) > page_size,
    )


def list_encounter_candidates(
    *,
    counselor: User,
    routine_interview_id: UUID,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> RoutineEncounterCandidatePage:
    _validate_counselor(counselor)
    page, page_size = _validate_page(page, page_size)

    item = (
        _queryset()
        .filter(
            pk=routine_interview_id,
            counselor_id=counselor.pk,
        )
        .first()
    )
    if item is None:
        raise RoutineInterviewNotFound("The requested Routine Interview was not found.")
    if item.intake_submitted_at is None:
        raise RoutineInterviewIntakeRequired(
            "Student Intake must be submitted before Counseling Encounter candidates are available."
        )
    if item.evaluation_finalized_at is not None:
        raise RoutineInterviewEvaluationFinalized(
            "The Counselor Evaluation is finalized and locked."
        )
    # Candidates exist only for reconciliation and recovery. A linked Routine Interview's
    # Encounter is already decided, so there is nothing to choose.
    if item.counseling_encounter_id is not None:
        return RoutineEncounterCandidatePage((), page, page_size, False)

    now = timezone.now()
    queryset = CounselingEncounter.objects.select_related(
        "service",
        "appointment",
    ).filter(
        student_id=item.student_id,
        counselor_id=item.counselor_id,
        service__code="COUNSELING",
        delivery_mode=item.delivery_mode,
        ended_at__lte=now,
        routine_interview__isnull=True,
    )
    if item.appointment_id is not None:
        queryset = queryset.filter(
            entry_mode=CounselingEntryMode.APPOINTMENT,
            appointment_id=item.appointment_id,
        )
    else:
        queryset = queryset.filter(
            entry_mode=item.entry_mode,
            appointment__isnull=True,
        )
    queryset = queryset.order_by("-ended_at", "id")

    offset = (page - 1) * page_size
    matched: list[CounselingEncounter] = []
    seen_matches = 0
    for encounter in queryset.iterator(chunk_size=max(page_size * 2, 20)):
        if not routine_interview_encounter_matches(
            item=item,
            encounter=encounter,
            now=now,
        ):
            continue
        if seen_matches < offset:
            seen_matches += 1
            continue
        matched.append(encounter)
        seen_matches += 1
        if len(matched) > page_size:
            break

    return RoutineEncounterCandidatePage(
        tuple(matched[:page_size]),
        page,
        page_size,
        len(matched) > page_size,
    )


def count_my_draft_intakes(student: User) -> int | None:
    if (
        not getattr(student, "pk", None)
        or not student.is_active
        or student.role.code != "STUDENT"
        or not student.has_capability("routine_interviews.manage_self")
        or not is_current_student(student)
    ):
        return None
    return RoutineInterview.objects.filter(
        student_id=student.pk,
        intake_submitted_at__isnull=True,
    ).count()


def count_pending_assigned_evaluations(counselor: User) -> int | None:
    if (
        not getattr(counselor, "pk", None)
        or not counselor.is_active
        or counselor.role.code != "COUNSELOR"
        or not counselor.has_capability("routine_interviews.view_assigned")
        or not counselor.has_capability("routine_interviews.manage_assigned")
    ):
        return None
    return RoutineInterview.objects.filter(
        counselor_id=counselor.pk,
        intake_submitted_at__isnull=False,
        evaluation_finalized_at__isnull=True,
    ).count()


def list_mine(student: User) -> tuple[RoutineInterview, ...]:
    _validate_student(student)
    return tuple(_queryset().filter(student_id=student.pk).order_by("-created_at", "id"))


def get_mine(*, student: User, routine_interview_id: UUID) -> RoutineInterview:
    _validate_student(student)
    item = _queryset().filter(pk=routine_interview_id, student_id=student.pk).first()
    if item is None:
        raise RoutineInterviewNotFound("The requested Routine Interview was not found.")
    return item


def list_assigned(
    *,
    counselor: User,
    student_id: UUID | None = None,
    academic_year_id: UUID | None = None,
    delivery_mode: str | DeliveryMode | None = None,
    intake_status: str | None = None,
    evaluation_status: str | None = None,
    search: str | None = None,
    ordering: str | RoutineInterviewOrdering | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> RoutineInterviewPage:
    _validate_counselor(counselor)
    if type(page) is not int or page < 1:
        raise InvalidRoutineInterviewInput("page must be at least 1.")
    if type(page_size) is not int or not 1 <= page_size <= MAX_PAGE_SIZE:
        raise InvalidRoutineInterviewInput(f"page_size must be between 1 and {MAX_PAGE_SIZE}.")
    term = ""
    if search is not None:
        if not isinstance(search, str):
            raise InvalidRoutineInterviewInput("search must be text.")
        term = search.strip()
        if len(term) > MAX_SEARCH_LENGTH:
            raise InvalidRoutineInterviewInput(
                f"search must be at most {MAX_SEARCH_LENGTH} characters."
            )

    queryset = _queryset().filter(counselor_id=counselor.pk)
    if student_id is not None:
        queryset = queryset.filter(student_id=student_id)
    if academic_year_id is not None:
        queryset = queryset.filter(academic_year_id=academic_year_id)
    if delivery_mode is not None:
        queryset = queryset.filter(delivery_mode=_normalize_delivery_mode(delivery_mode))
    if intake_status is not None:
        if intake_status not in {"DRAFT", "SUBMITTED"}:
            raise InvalidRoutineInterviewInput("intake_status must be DRAFT or SUBMITTED.")
        queryset = (
            queryset.filter(intake_submitted_at__isnull=True)
            if intake_status == "DRAFT"
            else queryset.filter(intake_submitted_at__isnull=False)
        )
    if evaluation_status is not None:
        if evaluation_status not in {"DRAFT", "FINALIZED"}:
            raise InvalidRoutineInterviewInput("evaluation_status must be DRAFT or FINALIZED.")
        queryset = (
            queryset.filter(evaluation_finalized_at__isnull=True)
            if evaluation_status == "DRAFT"
            else queryset.filter(evaluation_finalized_at__isnull=False)
        )
    for token in term.split():
        queryset = queryset.filter(
            Q(student__institutional_id__icontains=token)
            | Q(student__first_name__icontains=token)
            | Q(student__middle_name__icontains=token)
            | Q(student__last_name__icontains=token)
            | Q(appointment__reference_code__icontains=token)
        )
    resolved = _routine_list_ordering(
        ordering, intake_status=intake_status, evaluation_status=evaluation_status
    )
    queryset = queryset.order_by(*_ROUTINE_ORDER_BY[resolved])
    offset = (page - 1) * page_size
    rows = list(queryset[offset : offset + page_size + 1])
    return RoutineInterviewPage(
        tuple(rows[:page_size]),
        page,
        page_size,
        len(rows) > page_size,
        resolved,
    )


def get_assigned(*, counselor: User, routine_interview_id: UUID) -> RoutineInterview:
    _validate_counselor(counselor)
    item = _queryset().filter(pk=routine_interview_id, counselor_id=counselor.pk).first()
    if item is None:
        raise RoutineInterviewNotFound("The requested Routine Interview was not found.")
    return item


def _normalize_concerns(raw) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, (list, tuple)):
        raise InvalidRoutineInterviewInput("concerns must be a list of source-backed values.")
    allowed = set(RoutineConcern.values)
    normalized: list[str] = []
    for value in raw:
        candidate = value.value if isinstance(value, RoutineConcern) else str(value)
        if candidate not in allowed:
            raise InvalidRoutineInterviewInput("concerns contains an unsupported source value.")
        if candidate not in normalized:
            normalized.append(candidate)
    return normalized


def _validate_intake_submission(intake: dict[str, object]) -> None:
    concerns = intake["concerns"]
    specification = str(intake["other_concern_specification"]).strip()
    if RoutineConcern.OTHER in concerns and not specification:
        raise InvalidRoutineInterviewInput(
            "other_concern_specification is required when OTHER concern is selected."
        )
    meaningful_text = any(
        str(intake[field]).strip()
        for field in INTAKE_FIELDS
        if field not in {"concerns", "other_concern_specification"}
    )
    if not meaningful_text and not concerns and not specification:
        raise InvalidRoutineInterviewInput(
            "At least one Student Intake response or concern is required before submission."
        )


def replace_my_intake(
    *,
    student: User,
    routine_interview_id: UUID,
    values: dict[str, object],
) -> RoutineInterview:
    _validate_student(student)
    _require_current_student(student)
    unsupported = set(values) - set(INTAKE_FIELDS)
    if unsupported:
        raise InvalidRoutineInterviewInput("The Student Intake update contains unsupported fields.")

    with transaction.atomic():
        item = (
            RoutineInterview.objects.select_for_update()
            .filter(pk=routine_interview_id, student_id=student.pk)
            .first()
        )
        if item is None:
            raise RoutineInterviewNotFound("The requested Routine Interview was not found.")
        _require_actionable_parent(item, lock_parent=True)
        if item.intake_submitted_at is not None:
            raise RoutineInterviewIntakeSubmitted("A submitted Student Intake is locked.")

        intake = read_intake(item)
        for field in INTAKE_FIELDS:
            if field not in values:
                continue
            if field == "concerns":
                intake["concerns"] = _normalize_concerns(values[field])
            else:
                intake[field] = values[field]
        if RoutineConcern.OTHER not in intake["concerns"]:
            intake["other_concern_specification"] = ""

        try:
            write_intake(item, intake)
        except InvalidRoutineContent as exc:
            raise InvalidRoutineInterviewInput(
                "The Student Intake contains invalid values."
            ) from exc
        item.save(update_fields=["student_intake_ciphertext", "updated_at"])
        return _queryset().get(pk=item.pk)


def submit_my_intake(
    *,
    student: User,
    routine_interview_id: UUID,
    context: AuditContext,
) -> RoutineInterview:
    _validate_student(student)
    _require_current_student(student)
    with transaction.atomic():
        item = (
            RoutineInterview.objects.select_for_update(of=("self",))
            .select_related("academic_year")
            .filter(pk=routine_interview_id, student_id=student.pk)
            .first()
        )
        if item is None:
            raise RoutineInterviewNotFound("The requested Routine Interview was not found.")
        _require_actionable_parent(item, lock_parent=True)
        if item.intake_submitted_at is not None:
            return _queryset().get(pk=item.pk)
        # The Routine lifecycle is its own: a bound Inventory being reopened, resubmitted, or
        # absent never blocks the Intake (ADR-088).
        _validate_intake_submission(read_intake(item))
        item.intake_submitted_at = timezone.now()
        item.save(update_fields=["intake_submitted_at", "updated_at"])
        record_event(
            context=context,
            action=ROUTINE_INTERVIEW_INTAKE_SUBMITTED,
            outcome=AuditOutcome.SUCCESS,
            target_type="routine.interview",
            target_id=item.pk,
            metadata={
                "entry_mode": item.entry_mode,
                "academic_year": _academic_year_label(item),
                "appointment_id": str(item.appointment_id) if item.appointment_id else None,
            },
        )
        return _queryset().get(pk=item.pk)


def _validate_evaluation_values(evaluation: dict[str, object]) -> None:
    for field in RATING_FIELDS:
        value = evaluation[field]
        if value is not None and (type(value) is not int or not 1 <= value <= 10):
            raise InvalidRoutineInterviewInput(f"{field} must be between 1 and 10 when supplied.")


def replace_assigned_evaluation(
    *,
    counselor: User,
    routine_interview_id: UUID,
    values: dict[str, object],
) -> RoutineInterview:
    _validate_counselor(counselor)
    unsupported = set(values) - set(EVALUATION_FIELDS)
    if unsupported:
        raise InvalidRoutineInterviewInput(
            "The Counselor Evaluation update contains unsupported fields."
        )

    with transaction.atomic():
        item = (
            RoutineInterview.objects.select_for_update()
            .filter(pk=routine_interview_id, counselor_id=counselor.pk)
            .first()
        )
        if item is None:
            raise RoutineInterviewNotFound("The requested Routine Interview was not found.")
        _require_actionable_parent(item, lock_parent=True)
        if item.intake_submitted_at is None:
            raise RoutineInterviewIntakeRequired(
                "Student Intake must be submitted before Counselor Evaluation can be saved."
            )
        if item.evaluation_finalized_at is not None:
            raise RoutineInterviewEvaluationFinalized(
                "The Counselor Evaluation is finalized and locked."
            )
        evaluation = read_evaluation(item)
        for field in EVALUATION_FIELDS:
            if field in values:
                evaluation[field] = values[field]
        _validate_evaluation_values(evaluation)
        try:
            write_evaluation(item, evaluation)
        except InvalidRoutineContent as exc:
            raise InvalidRoutineInterviewInput(
                "The Counselor Evaluation contains invalid values."
            ) from exc
        item.save(update_fields=["counselor_evaluation_ciphertext", "updated_at"])
        return _queryset().get(pk=item.pk)


_MATCH_ISSUE_MESSAGES = {
    RoutineEncounterMatchIssue.STUDENT: "The Counseling Encounter belongs to another Student.",
    RoutineEncounterMatchIssue.COUNSELOR: "The Counseling Encounter belongs to another Counselor.",
    RoutineEncounterMatchIssue.SERVICE: (
        "The Counseling Encounter does not use the canonical COUNSELING Service."
    ),
    RoutineEncounterMatchIssue.DELIVERY_MODE: (
        "The Counseling Encounter delivery mode does not match the Routine Interview."
    ),
    RoutineEncounterMatchIssue.NOT_COMPLETED: (
        "The Counseling Encounter must represent a completed interaction."
    ),
}


def _raise_match_issue(item: RoutineInterview, issue: RoutineEncounterMatchIssue | None) -> None:
    if issue == RoutineEncounterMatchIssue.ENTRY_MODE:
        if item.appointment_id is not None:
            raise RoutineInterviewEncounterMismatch(
                "An Appointment-backed Routine Interview requires an APPOINTMENT Encounter."
            )
        raise RoutineInterviewEncounterMismatch(
            "The Counseling Encounter entry mode does not match the Routine Interview."
        )
    if issue == RoutineEncounterMatchIssue.APPOINTMENT:
        if item.appointment_id is None:
            raise RoutineInterviewEncounterMismatch(
                "A direct Routine Interview cannot link an Appointment-backed Encounter."
            )
        raise RoutineInterviewEncounterMismatch(
            "The Counseling Encounter Appointment does not match the Routine Interview."
        )
    if issue is not None:
        raise RoutineInterviewEncounterMismatch(_MATCH_ISSUE_MESSAGES[issue])


def _validate_encounter_match(*, item: RoutineInterview, encounter: CounselingEncounter) -> None:
    _raise_match_issue(
        item, routine_interview_encounter_match_issue(item=item, encounter=encounter)
    )


def _link_encounter(
    *,
    item: RoutineInterview,
    encounter: CounselingEncounter,
    source: RoutineEncounterLinkSource,
    context: AuditContext,
) -> bool:
    """Persist ``item.counseling_encounter`` inside the caller's transaction.

    The caller holds the Routine row lock and loaded ``encounter.service``. Linking the Encounter
    that is already linked is a no-op (``False``). A different existing link, or an Encounter that
    belongs to another Routine Interview, is rejected and never replaced.
    """

    if item.counseling_encounter_id == encounter.pk:
        return False
    if item.counseling_encounter_id is not None:
        raise RoutineInterviewEncounterConflict(
            "This Routine Interview is already linked to a different Counseling Encounter."
        )
    _validate_encounter_match(item=item, encounter=encounter)
    already_owned = RoutineInterview.objects.filter(counseling_encounter_id=encounter.pk).exclude(
        pk=item.pk
    )
    if already_owned.exists():
        raise RoutineInterviewEncounterConflict(
            "The Counseling Encounter is already linked to another Routine Interview."
        )
    try:
        # The one-to-one constraint stays authoritative for a concurrent link elsewhere.
        with transaction.atomic():
            item.counseling_encounter = encounter
            item.save(update_fields=["counseling_encounter", "updated_at"])
    except IntegrityError as exc:
        item.counseling_encounter = None
        raise RoutineInterviewEncounterConflict(
            "The Counseling Encounter is already linked to another Routine Interview."
        ) from exc

    record_event(
        context=context,
        action=ROUTINE_INTERVIEW_ENCOUNTER_LINKED,
        outcome=AuditOutcome.SUCCESS,
        target_type="routine.interview",
        target_id=item.pk,
        metadata={
            "link_source": source.value,
            "entry_mode": item.entry_mode,
            "appointment_id": str(item.appointment_id) if item.appointment_id else None,
            "encounter_id": str(encounter.pk),
        },
    )
    return True


def lock_routine_for_encounter_recording(
    *,
    counselor: User,
    routine_interview_id: UUID | None,
    appointment_id: UUID | None,
) -> RoutineInterview | None:
    """Lock the Routine Interview a new Counseling Encounter will belong to, if one is known.

    Called before the Encounter's Appointment is locked, matching the Routine → Appointment
    order of every Routine mutation. An explicit Routine context must be assigned to the
    recording Counselor; otherwise it is reported as not found.
    """

    if routine_interview_id is not None:
        item = (
            RoutineInterview.objects.select_for_update(of=("self",))
            .filter(pk=routine_interview_id, counselor_id=counselor.pk)
            .first()
        )
        if item is None:
            raise RoutineInterviewNotFound("The requested Routine Interview was not found.")
        return item
    if appointment_id is None:
        return None
    # A Routine Interview's Appointment never changes after creation, so this unlocked lookup
    # identifies the row to lock.
    routine_id = (
        RoutineInterview.objects.filter(appointment_id=appointment_id)
        .values_list("pk", flat=True)
        .first()
    )
    if routine_id is None:
        return None
    return RoutineInterview.objects.select_for_update(of=("self",)).filter(pk=routine_id).first()


def validate_encounter_for_routine_context(
    *,
    item: RoutineInterview,
    facts: RoutineEncounterFacts,
) -> None:
    """Reject an Encounter about to be recorded from ``item``'s context before it is written."""

    if item.counseling_encounter_id is not None:
        raise RoutineInterviewEncounterConflict(
            "A Counseling Encounter is already linked to this Routine Interview."
        )
    _require_actionable_parent(item)
    _raise_match_issue(
        item, routine_interview_encounter_match_issue_for_facts(item=item, facts=facts)
    )


def link_routine_context_encounter(
    *,
    item: RoutineInterview,
    encounter: CounselingEncounter,
    context: AuditContext,
) -> None:
    """Link an Encounter recorded from ``item``'s context; every failure fails the recording."""

    _link_encounter(
        item=item,
        encounter=encounter,
        source=RoutineEncounterLinkSource.ROUTINE_INTERVIEW_CONTEXT,
        context=context,
    )


def link_appointment_encounter(
    *,
    item: RoutineInterview | None,
    encounter: CounselingEncounter,
    context: AuditContext,
) -> bool:
    """Link an Appointment's Encounter to the same Appointment's Routine Interview.

    Sharing the Appointment makes the relationship deterministic, so COMPASS records it as soon
    as both exist. An Encounter that does not satisfy the Routine matching rules (for example a
    non-APPOINTMENT entry mode) stays independent: recording counseling never depends on the
    Routine Interview, and finalization still reports the mismatch. An existing different link is
    never replaced.
    """

    if encounter.appointment_id is None:
        return False
    if item is None:
        # The Routine Interview was created after the caller looked for it, before the caller
        # locked the Appointment. Lock it now; the Appointment lock keeps the set stable.
        item = (
            RoutineInterview.objects.select_for_update(of=("self",))
            .filter(appointment_id=encounter.appointment_id)
            .first()
        )
        if item is None:
            return False
    if item.appointment_id != encounter.appointment_id:
        return False
    if item.counseling_encounter_id == encounter.pk:
        return False
    if routine_interview_encounter_match_issue(item=item, encounter=encounter) is not None:
        return False
    return _link_encounter(
        item=item,
        encounter=encounter,
        source=RoutineEncounterLinkSource.APPOINTMENT,
        context=context,
    )


def finalize_assigned_evaluation(
    *,
    counselor: User,
    routine_interview_id: UUID,
    encounter_id: UUID | None,
    context: AuditContext,
) -> RoutineInterview:
    _validate_counselor(counselor)
    with transaction.atomic():
        item = (
            RoutineInterview.objects.select_for_update(of=("self",))
            .select_related("academic_year")
            .filter(pk=routine_interview_id, counselor_id=counselor.pk)
            .first()
        )
        if item is None:
            raise RoutineInterviewNotFound("The requested Routine Interview was not found.")
        _require_actionable_parent(item, lock_parent=True)
        if item.intake_submitted_at is None:
            raise RoutineInterviewIntakeRequired(
                "Student Intake must be submitted before Counselor Evaluation can be finalized."
            )
        if item.evaluation_finalized_at is not None:
            return _queryset().get(pk=item.pk)

        # Finalization locks the Evaluation permanently, so prove it is readable and valid first.
        _validate_evaluation_values(read_evaluation(item))
        encounters = CounselingEncounter.objects.select_for_update(of=("self",)).select_related(
            "service"
        )
        if item.counseling_encounter_id is not None:
            # Normal path: COMPASS linked the Encounter when the relationship became known.
            if encounter_id is not None and encounter_id != item.counseling_encounter_id:
                raise RoutineInterviewEncounterConflict(
                    "This Routine Interview is already linked to a different Counseling Encounter."
                )
            encounter = encounters.get(pk=item.counseling_encounter_id)
            _validate_encounter_match(item=item, encounter=encounter)
        elif item.appointment_id is not None:
            # Compatibility for records from before automatic linking. An Appointment admits at
            # most one Encounter, so the relationship is still deterministic.
            encounter = encounters.filter(appointment_id=item.appointment_id).first()
            if encounter is None:
                raise RoutineInterviewEncounterRequired(
                    "A completed Counseling Encounter for this Appointment is required."
                )
            if encounter_id is not None and encounter.pk != encounter_id:
                raise RoutineInterviewEncounterMismatch(
                    "The supplied Counseling Encounter does not match the Appointment."
                )
            _link_encounter(
                item=item,
                encounter=encounter,
                source=RoutineEncounterLinkSource.APPOINTMENT_RECONCILIATION,
                context=context,
            )
        else:
            # Exceptional recovery: the Encounter was recorded outside this direct Routine
            # Interview's context. COMPASS never chooses among matching Encounters itself.
            if encounter_id is None:
                raise RoutineInterviewEncounterRequired(
                    "No Counseling Encounter is linked to this Routine Interview. Record it from "
                    "the Routine Interview's Counseling workspace or name the recorded Encounter."
                )
            encounter = encounters.filter(pk=encounter_id).first()
            if encounter is None:
                raise RoutineInterviewEncounterRequired(
                    "The supplied Counseling Encounter was not found."
                )
            _link_encounter(
                item=item,
                encounter=encounter,
                source=RoutineEncounterLinkSource.COUNSELOR_RECOVERY,
                context=context,
            )

        item.evaluation_finalized_at = timezone.now()
        item.save(update_fields=["evaluation_finalized_at", "updated_at"])
        record_event(
            context=context,
            action=ROUTINE_INTERVIEW_EVALUATION_FINALIZED,
            outcome=AuditOutcome.SUCCESS,
            target_type="routine.interview",
            target_id=item.pk,
            metadata={
                "entry_mode": item.entry_mode,
                "academic_year": _academic_year_label(item),
                "appointment_id": str(item.appointment_id) if item.appointment_id else None,
                "encounter_id": str(encounter.pk),
            },
        )
        return _queryset().get(pk=item.pk)
