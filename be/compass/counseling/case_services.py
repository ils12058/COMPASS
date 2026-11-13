"""Counseling case workflows (CW-1): opening, session links and authorized projections.

Rules this module owns:

* A case is one episode of support. A Student may have several, and nothing here groups records
  by Student. A session joins a case only through an explicit link.
* Only the case's primary Counselor reads or changes it. Being Head, holding a College, having
  authored a session or being assigned a task grants nothing here.
* A Counselor links only their own Encounters. Another Counselor's record needs the approved
  disclosure route (CW-3); a matching Student or owning the case is not enough.
* An Encounter belongs to at most one case at a time. A wrong link is corrected explicitly and
  the removed link stays in history.
* Links never change an Encounter, its author, its Appointment or its published summary, and a
  case link never widens access to the linked record's content.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import Count, Exists, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce, Greatest
from django.utils import timezone

from compass.accounts.models import User
from compass.appointments.models import Appointment, AppointmentStatus
from compass.audit.actions import (
    COUNSELING_CASE_OPENED,
    COUNSELING_CASE_SESSION_LINKED,
    COUNSELING_CASE_SESSION_UNLINKED,
)
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.common.institutional_time import institution_zone
from compass.common.ordering import parse_ordering
from compass.service_catalog.canonical import COUNSELING_SERVICE_CODE
from compass.service_catalog.services import service_counselor_eligible

from .case_models import (
    CounselingCase,
    CounselingCaseAppointment,
    CounselingCaseEvent,
    CounselingCaseEventKind,
    CounselingCaseOrigin,
    CounselingCaseReferenceCounter,
    CounselingCaseSession,
    CounselingCaseSessionRemovalReason,
    CounselingCaseStatus,
)
from .case_next_actions import CaseNextActions
from .models import CounselingEncounter
from .services import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    MAX_STUDENT_SEARCH_LENGTH,
    CounselingConfigurationConflict,
    CounselingError,
    CounselingNotPermitted,
    _lock_users,
    get_counseling_service,
)

VIEW_CAPABILITY = "counseling.view_assigned"
MANAGE_CAPABILITY = "counseling.manage_assigned"
MAX_REFERENCE_SEQUENCE = 999_999
# A request names the active cases the Counselor was shown. More than this is not a real review.
MAX_KNOWN_ACTIVE_CASES = 50


class CounselingCaseError(CounselingError):
    """A safe, public case failure: ``code`` and ``status`` are the API error contract."""

    code = "counseling_case_error"
    status = 409


class CounselingCaseNotPermitted(CounselingCaseError):
    code = "permission_denied"
    status = 403


class CounselingCaseNotFound(CounselingCaseError):
    code = "counseling_case_not_found"
    status = 404


class CounselingCaseSourceNotFound(CounselingCaseError):
    code = "counseling_case_source_not_found"
    status = 404


class CounselingCaseSessionNotFound(CounselingCaseError):
    code = "counseling_case_session_not_found"
    status = 404


class CounselingCaseInvalid(CounselingCaseError):
    code = "counseling_case_invalid_request"
    status = 422


class CounselingCaseSourceInvalid(CounselingCaseError):
    code = "counseling_case_source_invalid"


class CounselingCaseReviewRequired(CounselingCaseError):
    """The Counselor's active cases for this Student differ from the ones they reviewed."""

    code = "counseling_case_review_required"


class CounselingCaseClosed(CounselingCaseError):
    code = "counseling_case_closed"


class CounselingCaseChanged(CounselingCaseError):
    code = "counseling_case_changed"


class CounselingCaseSessionAlreadyLinked(CounselingCaseError):
    code = "counseling_case_session_already_linked"


class CounselingCaseSessionStudentMismatch(CounselingCaseError):
    code = "counseling_case_session_student_mismatch"


class CounselingCaseReferenceExhausted(CounselingCaseError):
    code = "counseling_case_reference_exhausted"


class CounselingCaseOrdering(StrEnum):
    """Closed orderings for a Counselor's cases (ADR-090); the latest activity comes first."""

    LATEST_ACTIVITY = "LATEST_ACTIVITY"
    LATEST_OPENED = "LATEST_OPENED"
    OLDEST_OPENED = "OLDEST_OPENED"
    STUDENT_ASC = "STUDENT_ASC"
    STUDENT_DESC = "STUDENT_DESC"


_STUDENT_NAME = ("student__last_name", "student__first_name", "student__middle_name")
_CASE_ORDER_BY: dict[CounselingCaseOrdering, tuple[str, ...]] = {
    CounselingCaseOrdering.LATEST_ACTIVITY: ("-_last_activity_at", "-opened_at", "-id"),
    CounselingCaseOrdering.LATEST_OPENED: ("-opened_at", "-id"),
    CounselingCaseOrdering.OLDEST_OPENED: ("opened_at", "id"),
    CounselingCaseOrdering.STUDENT_ASC: (*_STUDENT_NAME, "-opened_at", "id"),
    CounselingCaseOrdering.STUDENT_DESC: (
        *(f"-{field}" for field in _STUDENT_NAME),
        "-opened_at",
        "-id",
    ),
}


@dataclass(frozen=True, slots=True)
class CaseSummary:
    case: CounselingCase
    # Completed sessions currently linked to this case. Each Encounter counts once; its
    # Appointment or Routine Interview never adds another.
    session_count: int
    latest_session_at: datetime | None


@dataclass(frozen=True, slots=True)
class CasePage:
    items: tuple[CaseSummary, ...]
    page: int
    page_size: int
    has_next: bool
    ordering: CounselingCaseOrdering


@dataclass(frozen=True, slots=True)
class CaseSession:
    link: CounselingCaseSession
    # Whether this reader may open the linked Encounter record itself. Membership in the case is
    # not that permission.
    record_accessible: bool


@dataclass(frozen=True, slots=True)
class CaseOverview:
    summary: CaseSummary
    sessions: tuple[CaseSession, ...]
    events: tuple[CounselingCaseEvent, ...]
    can_manage: bool
    origin_appointment: Appointment | None
    origin_encounter_id: UUID | None
    origin_routine_interview_id: UUID | None
    # The originating context's own recorded session, when it exists, is the reader's, and is not
    # in any case yet. It is offered for an explicit link and never added automatically.
    unlinked_origin_session: CounselingEncounter | None
    appointments: tuple[CounselingCaseAppointment, ...]
    next_appointment: Appointment | None
    unlinked_appointment_sessions: tuple[CounselingEncounter, ...]
    next_actions: CaseNextActions
    can_link_appointments: bool


@dataclass(frozen=True, slots=True)
class CaseSessionCandidatePage:
    items: tuple[CounselingEncounter, ...]
    page: int
    page_size: int
    has_next: bool


@dataclass(frozen=True, slots=True)
class CaseOpeningContext:
    origin: str
    student: User
    appointment: Appointment | None
    encounter_id: UUID | None
    routine_interview_id: UUID | None
    # The recorded session that opening from this context would link.
    session: CounselingEncounter | None
    active_cases: tuple[CaseSummary, ...]


@dataclass(frozen=True, slots=True)
class EncounterCaseLink:
    """What one reader may know about an Encounter's case membership."""

    linked: bool
    case: CounselingCase | None


@dataclass(frozen=True, slots=True)
class _Opening:
    origin: str
    student_id: UUID
    appointment: Appointment | None
    encounter: CounselingEncounter | None
    routine_interview_id: UUID | None
    session: CounselingEncounter | None


def _require_actor(actor: User, capability: str, *, at: datetime | None = None) -> None:
    if (
        not getattr(actor, "pk", None)
        or not actor.is_active
        or actor.role.code != "COUNSELOR"
        or not actor.has_capability(capability, at=at)
    ):
        raise CounselingCaseNotPermitted("You don't have permission to use Counseling cases.")


def _accessible_cases(actor: User):
    """The single relationship rule: a case is its primary Counselor's."""

    return CounselingCase.objects.filter(primary_counselor_id=actor.pk)


def _current_links():
    return CounselingCaseSession.objects.filter(removed_at__isnull=True)


def _with_session_facts(queryset):
    links = _current_links().filter(case_id=OuterRef("pk"))
    return queryset.annotate(
        _session_count=Coalesce(
            Subquery(links.order_by().values("case_id").annotate(n=Count("id")).values("n")[:1]),
            0,
        ),
        _latest_session_at=Subquery(
            links.order_by("-encounter__started_at").values("encounter__started_at")[:1]
        ),
    ).annotate(
        _last_activity_at=Greatest("opened_at", Coalesce("_latest_session_at", "opened_at")),
    )


def _summary(case: CounselingCase) -> CaseSummary:
    return CaseSummary(
        case=case,
        session_count=case._session_count,
        latest_session_at=case._latest_session_at,
    )


def _case_queryset(actor: User):
    return _with_session_facts(
        _accessible_cases(actor).select_related(
            "student",
            "student__role",
            "primary_counselor",
            "primary_counselor__role",
            "opened_by",
        )
    )


def _validate_page(page: int, page_size: int) -> tuple[int, int]:
    if type(page) is not int or page < 1:
        raise CounselingCaseInvalid("page must be a positive integer")
    if type(page_size) is not int or not 1 <= page_size <= MAX_PAGE_SIZE:
        raise CounselingCaseInvalid(f"page_size must be between 1 and {MAX_PAGE_SIZE}")
    return page, page_size


def _clean_search(search: str | None) -> str:
    if search is None:
        return ""
    if not isinstance(search, str):
        raise CounselingCaseInvalid("search must be text")
    cleaned = search.strip()
    if len(cleaned) > MAX_STUDENT_SEARCH_LENGTH:
        raise CounselingCaseInvalid(
            f"search must be at most {MAX_STUDENT_SEARCH_LENGTH} characters"
        )
    return cleaned


def _normalize_status(value: str | CounselingCaseStatus | None) -> str | None:
    if value is None:
        return None
    normalized = value.value if isinstance(value, StrEnum) else value
    if normalized not in CounselingCaseStatus.values:
        raise CounselingCaseInvalid("status must be ACTIVE or CLOSED")
    return str(normalized)


def _normalize_origin(value: str | CounselingCaseOrigin) -> str:
    normalized = value.value if isinstance(value, StrEnum) else value
    if normalized not in CounselingCaseOrigin.values:
        raise CounselingCaseInvalid(
            "origin must be INTAKE, APPOINTMENT, ENCOUNTER, or ROUTINE_INTERVIEW"
        )
    return str(normalized)


def _normalize_removal_reason(value: str | CounselingCaseSessionRemovalReason) -> str:
    normalized = value.value if isinstance(value, StrEnum) else value
    if normalized not in CounselingCaseSessionRemovalReason.values:
        raise CounselingCaseInvalid("Choose why this session doesn't belong in the case.")
    return str(normalized)


def _expected_version(value: object) -> int:
    if type(value) is not int or value < 1:
        raise CounselingCaseInvalid("An expected version is required.")
    return value


def list_my_cases(
    *,
    actor: User,
    status: str | None = None,
    student_id: UUID | None = None,
    search: str | None = None,
    ordering: str | CounselingCaseOrdering | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> CasePage:
    _require_actor(actor, VIEW_CAPABILITY)
    page, page_size = _validate_page(page, page_size)
    resolved = parse_ordering(
        ordering,
        CounselingCaseOrdering,
        default=CounselingCaseOrdering.LATEST_ACTIVITY,
        error=CounselingCaseInvalid,
    )
    queryset = _case_queryset(actor)
    normalized_status = _normalize_status(status)
    if normalized_status is not None:
        queryset = queryset.filter(status=normalized_status)
    if student_id is not None:
        queryset = queryset.filter(student_id=student_id)
    for token in _clean_search(search).split():
        queryset = queryset.filter(
            Q(reference_code__icontains=token)
            | Q(student__institutional_id__icontains=token)
            | Q(student__first_name__icontains=token)
            | Q(student__middle_name__icontains=token)
            | Q(student__last_name__icontains=token)
        )
    offset = (page - 1) * page_size
    rows = list(queryset.order_by(*_CASE_ORDER_BY[resolved])[offset : offset + page_size + 1])
    return CasePage(
        items=tuple(_summary(row) for row in rows[:page_size]),
        page=page,
        page_size=page_size,
        has_next=len(rows) > page_size,
        ordering=resolved,
    )


def _origin_session(case: CounselingCase, actor: User) -> CounselingEncounter | None:
    """The originating context's own Encounter, if it is the reader's and still unlinked."""

    own = CounselingEncounter.objects.filter(counselor_id=actor.pk, student_id=case.student_id)
    if case.origin == CounselingCaseOrigin.APPOINTMENT:
        own = own.filter(appointment_id=case.origin_appointment_id)
    elif case.origin == CounselingCaseOrigin.ROUTINE_INTERVIEW:
        own = own.filter(routine_interview__pk=case.origin_routine_interview_id)
    elif case.origin == CounselingCaseOrigin.ENCOUNTER:
        own = own.filter(pk=case.origin_encounter_id)
    else:
        return None
    return (
        own.annotate(_linked=Exists(_current_links().filter(encounter_id=OuterRef("pk"))))
        .filter(_linked=False)
        .select_related("counselor", "counselor__role", "appointment")
        .first()
    )


def get_case(*, actor: User, case_id: UUID, now: datetime | None = None) -> CaseOverview:
    _require_actor(actor, VIEW_CAPABILITY)
    case = (
        _case_queryset(actor)
        .select_related("origin_appointment", "origin_encounter", "origin_routine_interview")
        .filter(pk=case_id)
        .first()
    )
    if case is None:
        raise CounselingCaseNotFound("The requested case was not found.")
    from .case_continuity_rules import CaseContinuityError
    from .case_coverage_tasks import reconcile_returns

    try:
        reconcile_returns(actor=actor, case_id=case.pk)
    except CaseContinuityError as exc:
        raise CounselingCaseChanged(exc.message) from None
    links = list(
        _current_links()
        .filter(case_id=case.pk)
        .select_related(
            "encounter",
            "encounter__counselor",
            "encounter__counselor__role",
            "encounter__appointment",
            "linked_by",
        )
        .order_by("-encounter__started_at", "id")
    )
    events = list(
        CounselingCaseEvent.objects.filter(case_id=case.pk)
        .select_related("actor", "primary_counselor", "encounter")
        .order_by("-sequence")
    )
    appointment = case.origin_appointment
    routine = case.origin_routine_interview
    encounter = case.origin_encounter
    active = case.status == CounselingCaseStatus.ACTIVE
    from compass.service_catalog.canonical import COUNSELING_SERVICE_CODE

    from .case_next_actions import next_actions

    appointment_links = tuple(
        case.appointment_links.select_related(
            "appointment__service", "appointment__provider", "linked_by", "removed_by"
        ).order_by("-linked_at", "id")
    )
    next_appointment = (
        Appointment.objects.filter(
            student_id=case.student_id, service__code=COUNSELING_SERVICE_CODE, status="SCHEDULED"
        )
        .filter(
            case_links__case_id=case.pk,
            case_links__removed_at__isnull=True,
            starts_at__gt=now or timezone.now(),
        )
        .select_related("service", "provider")
        .order_by("starts_at", "id")
        .first()
    )
    appointment_sessions = (
        tuple(
            CounselingEncounter.objects.filter(
                counselor_id=actor.pk,
                student_id=case.student_id,
                appointment__case_links__case_id=case.pk,
                appointment__case_links__removed_at__isnull=True,
            )
            .alias(_linked=Exists(_current_links().filter(encounter_id=OuterRef("pk"))))
            .filter(_linked=False)
            .select_related("counselor", "counselor__role", "appointment")
            .order_by("-started_at", "id")
        )
        if active
        else ()
    )
    return CaseOverview(
        summary=_summary(case),
        sessions=tuple(
            CaseSession(link=link, record_accessible=link.encounter.counselor_id == actor.pk)
            for link in links
        ),
        events=tuple(events),
        can_manage=active and actor.has_capability(MANAGE_CAPABILITY),
        # Provenance is shown only while the originating record is still the reader's own.
        origin_appointment=(
            appointment if appointment is not None and appointment.provider_id == actor.pk else None
        ),
        origin_encounter_id=(
            encounter.pk if encounter is not None and encounter.counselor_id == actor.pk else None
        ),
        origin_routine_interview_id=(
            routine.pk if routine is not None and routine.counselor_id == actor.pk else None
        ),
        unlinked_origin_session=_origin_session(case, actor) if active else None,
        appointments=appointment_links,
        next_appointment=next_appointment,
        unlinked_appointment_sessions=appointment_sessions,
        next_actions=next_actions(actor=actor, case=case),
        can_link_appointments=(
            active
            and actor.has_capability(MANAGE_CAPABILITY)
            and actor.has_capability("appointments.view_self")
        ),
    )


def encounter_case_links(
    *, actor: User, encounter_ids: Iterable[UUID]
) -> dict[UUID, EncounterCaseLink]:
    """Case membership of Encounters the caller already authorized for this reader.

    The case itself is named only when the reader may open it; otherwise only the fact that the
    session is already in a case is reported, so it is not offered for another link.
    """

    ids = list(encounter_ids)
    result = {pk: EncounterCaseLink(linked=False, case=None) for pk in ids}
    if not ids:
        return result
    for link in _current_links().filter(encounter_id__in=ids).select_related("case"):
        accessible = link.case.primary_counselor_id == actor.pk
        result[link.encounter_id] = EncounterCaseLink(
            linked=True, case=link.case if accessible else None
        )
    return result


def list_session_candidates(
    *,
    actor: User,
    case_id: UUID,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> CaseSessionCandidatePage:
    """The reader's own recorded sessions with this Student that are in no case yet."""

    _require_actor(actor, MANAGE_CAPABILITY)
    page, page_size = _validate_page(page, page_size)
    case = _accessible_cases(actor).filter(pk=case_id).first()
    if case is None:
        raise CounselingCaseNotFound("The requested case was not found.")
    if case.status != CounselingCaseStatus.ACTIVE:
        raise CounselingCaseClosed("This case is closed. Sessions can't be added to it.")
    queryset = (
        CounselingEncounter.objects.select_related("counselor", "counselor__role", "appointment")
        .filter(counselor_id=actor.pk, student_id=case.student_id)
        .annotate(_linked=Exists(_current_links().filter(encounter_id=OuterRef("pk"))))
        .filter(_linked=False)
        .order_by("-started_at", "id")
    )
    offset = (page - 1) * page_size
    rows = list(queryset[offset : offset + page_size + 1])
    return CaseSessionCandidatePage(
        items=tuple(rows[:page_size]),
        page=page,
        page_size=page_size,
        has_next=len(rows) > page_size,
    )


def _resolve_opening(
    *,
    actor: User,
    origin: str,
    student_id: UUID | None,
    source_id: UUID | None,
) -> _Opening:
    """Identify the opening context from records that are the Counselor's own.

    A record that is missing and one that belongs to someone else are the same answer.
    """

    if origin == CounselingCaseOrigin.INTAKE:
        if source_id is not None:
            raise CounselingCaseInvalid("A Counseling intake doesn't name a source record.")
        if student_id is None:
            raise CounselingCaseInvalid("Choose the Student for this case.")
        return _Opening(origin, student_id, None, None, None, None)
    if source_id is None:
        raise CounselingCaseInvalid("Choose the record this case starts from.")

    appointment = None
    encounter = None
    routine_id = None
    session = None
    if origin == CounselingCaseOrigin.APPOINTMENT:
        appointment = (
            Appointment.objects.select_related("service")
            .filter(pk=source_id, provider_id=actor.pk)
            .first()
        )
        if appointment is None:
            raise CounselingCaseSourceNotFound("The requested Appointment was not found.")
        if appointment.service.code != COUNSELING_SERVICE_CODE:
            raise CounselingCaseSourceInvalid("Open a case from a Counseling Appointment.")
        if appointment.status not in {AppointmentStatus.SCHEDULED, AppointmentStatus.COMPLETED}:
            raise CounselingCaseSourceInvalid(
                "A cancelled or missed Appointment can't start a case."
            )
        source_student_id = appointment.student_id
        session = CounselingEncounter.objects.filter(
            appointment_id=appointment.pk,
            counselor_id=actor.pk,
            student_id=appointment.student_id,
        ).first()
    elif origin == CounselingCaseOrigin.ENCOUNTER:
        encounter = CounselingEncounter.objects.filter(pk=source_id, counselor_id=actor.pk).first()
        if encounter is None:
            raise CounselingCaseSourceNotFound("The requested session record was not found.")
        source_student_id = encounter.student_id
        session = encounter
    else:
        from compass.routine_interviews.models import RoutineInterview

        routine = (
            RoutineInterview.objects.select_related("counseling_encounter")
            .filter(pk=source_id, counselor_id=actor.pk)
            .first()
        )
        if routine is None:
            raise CounselingCaseSourceNotFound("The requested Routine Interview was not found.")
        routine_id = routine.pk
        source_student_id = routine.student_id
        linked = routine.counseling_encounter
        if (
            linked is not None
            and linked.counselor_id == actor.pk
            and linked.student_id == routine.student_id
        ):
            session = linked

    if student_id is not None and student_id != source_student_id:
        raise CounselingCaseSourceInvalid("The selected Student doesn't match this record.")
    return _Opening(origin, source_student_id, appointment, encounter, routine_id, session)


def _session_in_case_error(
    *, actor: User, link: CounselingCaseSession, case_id: UUID | None = None
) -> CounselingCaseSessionAlreadyLinked:
    if case_id is not None and link.case_id == case_id:
        return CounselingCaseSessionAlreadyLinked("This session is already in this case.")
    if link.case.primary_counselor_id == actor.pk:
        return CounselingCaseSessionAlreadyLinked(
            f"This session already belongs to case {link.case.reference_code}. "
            "Correct that link first if it is wrong."
        )
    return CounselingCaseSessionAlreadyLinked("This session already belongs to another case.")


def _validate_intake_counselor(counselor: User) -> None:
    """A case opened without a source record follows current Service coverage (ADR-089)."""

    try:
        service = get_counseling_service(require_active=True)
    except CounselingConfigurationConflict as exc:
        raise CounselingCaseSourceInvalid(str(exc)) from exc
    if not service_counselor_eligible(service, counselor):
        raise CounselingCaseSourceInvalid(
            "This Counselor isn't assigned to the Counseling Service."
        )


def get_opening_context(
    *,
    actor: User,
    origin: str,
    student_id: UUID | None = None,
    source_id: UUID | None = None,
) -> CaseOpeningContext:
    """What a Counselor reviews before opening a case: the Student, the source, and the active
    cases they already hold for that Student."""

    _require_actor(actor, MANAGE_CAPABILITY)
    normalized = _normalize_origin(origin)
    opening = _resolve_opening(
        actor=actor, origin=normalized, student_id=student_id, source_id=source_id
    )
    student = (
        User.objects.select_related("role")
        .filter(pk=opening.student_id, is_active=True, role__code="STUDENT")
        .first()
    )
    if student is None:
        if normalized == CounselingCaseOrigin.INTAKE:
            raise CounselingCaseSourceNotFound("The requested Student was not found.")
        raise CounselingCaseSourceInvalid("The Student's account isn't active.")
    if normalized == CounselingCaseOrigin.INTAKE:
        _validate_intake_counselor(actor)
    if opening.session is not None:
        link = _current_links().filter(encounter_id=opening.session.pk).select_related("case")
        current = link.first()
        if current is not None:
            raise _session_in_case_error(actor=actor, link=current)
    session = (
        CounselingEncounter.objects.select_related("counselor", "counselor__role", "appointment")
        .filter(pk=opening.session.pk)
        .first()
        if opening.session is not None
        else None
    )
    active = (
        _case_queryset(actor)
        .filter(student_id=student.pk, status=CounselingCaseStatus.ACTIVE)
        .order_by(*_CASE_ORDER_BY[CounselingCaseOrdering.LATEST_ACTIVITY])
    )
    return CaseOpeningContext(
        origin=normalized,
        student=student,
        appointment=opening.appointment,
        encounter_id=opening.encounter.pk if opening.encounter is not None else None,
        routine_interview_id=opening.routine_interview_id,
        session=session,
        active_cases=tuple(_summary(row) for row in active),
    )


def _append_event(
    *,
    case: CounselingCase,
    kind: str,
    actor: User,
    at: datetime,
    encounter_id: UUID | None = None,
    detail_code: str = "",
) -> CounselingCaseEvent:
    """Append the next event of a case the caller created or holds locked."""

    latest = (
        CounselingCaseEvent.objects.filter(case_id=case.pk)
        .order_by("-sequence")
        .values_list("sequence", flat=True)
        .first()
    )
    return CounselingCaseEvent.objects.create(
        case=case,
        sequence=(latest or 0) + 1,
        kind=kind,
        actor=actor,
        primary_counselor_id=case.primary_counselor_id,
        encounter_id=encounter_id,
        detail_code=detail_code,
        occurred_at=at,
    )


def _allocate_reference(*, at: datetime) -> str:
    year = at.astimezone(institution_zone()).year
    counter = CounselingCaseReferenceCounter.objects.select_for_update().filter(year=year).first()
    if counter is None:
        try:
            with transaction.atomic():
                CounselingCaseReferenceCounter.objects.create(year=year, next_value=2)
            return f"CASE-{year:04d}-{1:06d}"
        except IntegrityError:
            counter = CounselingCaseReferenceCounter.objects.select_for_update().get(year=year)
    number = counter.next_value
    if number > MAX_REFERENCE_SEQUENCE:
        raise CounselingCaseReferenceExhausted(
            "The case reference sequence is exhausted for this year."
        )
    counter.next_value = number + 1
    counter.save(update_fields=["next_value"])
    return f"CASE-{year:04d}-{number:06d}"


def _link(
    *,
    case: CounselingCase,
    encounter: CounselingEncounter,
    actor: User,
    at: datetime,
    context: AuditContext,
) -> CounselingCaseSession:
    try:
        with transaction.atomic():
            link = CounselingCaseSession.objects.create(
                case=case, encounter=encounter, linked_by=actor, linked_at=at
            )
    except IntegrityError as exc:
        # The partial unique constraint is the final word when two links race.
        raise CounselingCaseSessionAlreadyLinked(
            "This session already belongs to another case."
        ) from exc
    _append_event(
        case=case,
        kind=CounselingCaseEventKind.SESSION_LINKED,
        actor=actor,
        at=at,
        encounter_id=encounter.pk,
    )
    record_event(
        context=context,
        action=COUNSELING_CASE_SESSION_LINKED,
        outcome=AuditOutcome.SUCCESS,
        target_type="counseling.case",
        target_id=case.pk,
        metadata={"encounter_id": str(encounter.pk)},
    )
    from .case_call_slips import end_linked_call_slips

    # NS-1: the linked Appointment's case Call Slip is marked "interview ended" with the session.
    end_linked_call_slips(case=case, encounter=encounter, context=context, at=at)
    return link


def open_case(
    *,
    actor: User,
    origin: str,
    student_id: UUID | None = None,
    source_id: UUID | None = None,
    known_active_case_ids: Iterable[UUID] = (),
    context: AuditContext,
    now: datetime | None = None,
) -> CounselingCase:
    """Deliberately open one new Active case, with the opener as its primary Counselor.

    ``known_active_case_ids`` are the active cases for this Student the Counselor was shown. If the
    current set differs, nothing is created and the Counselor reviews again; this also makes a
    repeated submission of the same request harmless.
    """

    normalized = _normalize_origin(origin)
    known = set(known_active_case_ids)
    if len(known) > MAX_KNOWN_ACTIVE_CASES:
        raise CounselingCaseInvalid("Too many reviewed cases were supplied.")
    current = now or timezone.now()

    with transaction.atomic():
        opening = _resolve_opening(
            actor=actor, origin=normalized, student_id=student_id, source_id=source_id
        )
        if opening.appointment is not None:
            # Appointment links and lifecycle changes serialize before participant locks.
            Appointment.objects.select_for_update().get(pk=opening.appointment.pk)
        session = None
        if opening.session is not None:
            # Lock order everywhere in this module: case, then Encounter, then Users.
            session = (
                CounselingEncounter.objects.select_for_update()
                .filter(pk=opening.session.pk, counselor_id=actor.pk)
                .first()
            )
            if session is None:
                raise CounselingCaseSourceNotFound("The requested session record was not found.")
        try:
            locked = _lock_users(actor.pk, opening.student_id)
        except CounselingNotPermitted as exc:
            raise CounselingCaseSourceNotFound("The requested Student was not found.") from exc
        locked_actor = locked[actor.pk]
        locked_student = locked[opening.student_id]
        _require_actor(locked_actor, MANAGE_CAPABILITY, at=current)
        if not locked_student.is_active or locked_student.role.code != "STUDENT":
            if normalized == CounselingCaseOrigin.INTAKE:
                raise CounselingCaseSourceNotFound("The requested Student was not found.")
            raise CounselingCaseSourceInvalid("The Student's account isn't active.")
        if normalized == CounselingCaseOrigin.INTAKE:
            _validate_intake_counselor(locked_actor)

        # The source is read again now that its participants are locked.
        confirmed = _resolve_opening(
            actor=locked_actor, origin=normalized, student_id=student_id, source_id=source_id
        )
        if confirmed.student_id != opening.student_id or (
            (confirmed.session.pk if confirmed.session else None)
            != (session.pk if session else None)
        ):
            raise CounselingCaseSourceInvalid("This record changed. Review it and try again.")

        active = set(
            _accessible_cases(locked_actor)
            .filter(student_id=locked_student.pk, status=CounselingCaseStatus.ACTIVE)
            .values_list("pk", flat=True)
        )
        if active != known:
            raise CounselingCaseReviewRequired(
                "Your active cases for this Student changed. Review them before opening a case."
            )
        if session is not None:
            existing = (
                _current_links().filter(encounter_id=session.pk).select_related("case").first()
            )
            if existing is not None:
                raise _session_in_case_error(actor=locked_actor, link=existing)

        case = CounselingCase.objects.create(
            reference_code=_allocate_reference(at=current),
            student=locked_student,
            primary_counselor=locked_actor,
            origin=normalized,
            origin_appointment=confirmed.appointment,
            origin_encounter=confirmed.encounter,
            origin_routine_interview_id=confirmed.routine_interview_id,
            opened_by=locked_actor,
            opened_at=current,
        )
        _append_event(
            case=case,
            kind=CounselingCaseEventKind.OPENED,
            actor=locked_actor,
            at=current,
            detail_code=normalized,
        )
        record_event(
            context=context,
            action=COUNSELING_CASE_OPENED,
            outcome=AuditOutcome.SUCCESS,
            target_type="counseling.case",
            target_id=case.pk,
            metadata={
                "reference_code": case.reference_code,
                "origin": normalized,
                "student_id": str(locked_student.pk),
                "primary_counselor_id": str(locked_actor.pk),
            },
        )
        if session is not None:
            _link(case=case, encounter=session, actor=locked_actor, at=current, context=context)
        if confirmed.appointment is not None and confirmed.appointment.status == "SCHEDULED":
            from .case_appointment_services import create_link

            create_link(
                case=case,
                appointment=confirmed.appointment,
                actor=locked_actor,
                context=context,
                at=current,
            )
    return case


def _lock_case(*, actor: User, case_id: UUID, expected_version: int) -> CounselingCase:
    case = CounselingCase.objects.select_for_update().filter(pk=case_id).first()
    if case is None or case.primary_counselor_id != actor.pk:
        raise CounselingCaseNotFound("The requested case was not found.")
    if case.status != CounselingCaseStatus.ACTIVE:
        raise CounselingCaseClosed("This case is closed. Its sessions can't be changed.")
    if case.version != expected_version:
        raise CounselingCaseChanged("This case changed. Review the latest details.")
    return case


def _bump(case: CounselingCase) -> None:
    case.version += 1
    case.save(update_fields=["version", "updated_at"])


def lock_case_for_recording(*, actor: User, case_id: UUID) -> CounselingCase:
    """Lock the Counselor's own Active case before a session is recorded from it.

    Call this first in the recording transaction, before any other row is locked.
    """

    case = CounselingCase.objects.select_for_update().filter(pk=case_id).first()
    if case is None or case.primary_counselor_id != actor.pk:
        raise CounselingCaseNotFound("The requested case was not found.")
    if case.status != CounselingCaseStatus.ACTIVE:
        raise CounselingCaseClosed("This case is closed. Sessions can't be added to it.")
    return case


def link_recorded_session(
    *,
    case: CounselingCase,
    encounter: CounselingEncounter,
    actor: User,
    context: AuditContext,
    now: datetime | None = None,
) -> None:
    """Link the session just recorded from a locked case, inside the recording transaction."""

    if encounter.student_id != case.student_id or encounter.counselor_id != actor.pk:
        raise CounselingCaseSessionStudentMismatch(
            "This session is for a different Student than the case."
        )
    _link(case=case, encounter=encounter, actor=actor, at=now or timezone.now(), context=context)
    _bump(case)


def link_session(
    *,
    actor: User,
    case_id: UUID,
    encounter_id: UUID,
    expected_version: int,
    context: AuditContext,
    now: datetime | None = None,
) -> CounselingCase:
    """Add one of the Counselor's own recorded sessions to their Active case."""

    version = _expected_version(expected_version)
    current = now or timezone.now()
    with transaction.atomic():
        case = _lock_case(actor=actor, case_id=case_id, expected_version=version)
        encounter = (
            CounselingEncounter.objects.select_for_update()
            .filter(pk=encounter_id, counselor_id=actor.pk)
            .first()
        )
        if encounter is None:
            raise CounselingCaseSessionNotFound("The requested session record was not found.")
        locked_actor = _lock_users(actor.pk)[actor.pk]
        _require_actor(locked_actor, MANAGE_CAPABILITY, at=current)
        if encounter.student_id != case.student_id:
            raise CounselingCaseSessionStudentMismatch(
                "This session is for a different Student than the case."
            )
        existing = _current_links().filter(encounter_id=encounter.pk).select_related("case").first()
        if existing is not None:
            raise _session_in_case_error(actor=locked_actor, link=existing, case_id=case.pk)
        _link(case=case, encounter=encounter, actor=locked_actor, at=current, context=context)
        _bump(case)
    return case


def unlink_session(
    *,
    actor: User,
    case_id: UUID,
    encounter_id: UUID,
    reason: str,
    expected_version: int,
    context: AuditContext,
    now: datetime | None = None,
) -> CounselingCase:
    """Correct a wrong link. The session record is untouched and the removed link is kept."""

    version = _expected_version(expected_version)
    normalized_reason = _normalize_removal_reason(reason)
    current = now or timezone.now()
    with transaction.atomic():
        case = _lock_case(actor=actor, case_id=case_id, expected_version=version)
        locked_actor = _lock_users(actor.pk)[actor.pk]
        _require_actor(locked_actor, MANAGE_CAPABILITY, at=current)
        link = (
            CounselingCaseSession.objects.select_for_update()
            .filter(case_id=case.pk, encounter_id=encounter_id, removed_at__isnull=True)
            .first()
        )
        if link is None:
            raise CounselingCaseSessionNotFound("This session isn't in this case.")
        link.removed_at = current
        link.removed_by = locked_actor
        link.removal_reason = normalized_reason
        link.save(update_fields=["removed_at", "removed_by", "removal_reason"])
        _append_event(
            case=case,
            kind=CounselingCaseEventKind.SESSION_UNLINKED,
            actor=locked_actor,
            at=current,
            encounter_id=encounter_id,
            detail_code=normalized_reason,
        )
        record_event(
            context=context,
            action=COUNSELING_CASE_SESSION_UNLINKED,
            outcome=AuditOutcome.SUCCESS,
            target_type="counseling.case",
            target_id=case.pk,
            metadata={"encounter_id": str(encounter_id), "reason": normalized_reason},
        )
        _bump(case)
    return case


__all__ = [
    "MANAGE_CAPABILITY",
    "VIEW_CAPABILITY",
    "CaseOpeningContext",
    "CaseOverview",
    "CasePage",
    "CaseSession",
    "CaseSessionCandidatePage",
    "CaseSummary",
    "CounselingCaseChanged",
    "CounselingCaseClosed",
    "CounselingCaseError",
    "CounselingCaseInvalid",
    "CounselingCaseNotFound",
    "CounselingCaseNotPermitted",
    "CounselingCaseOrdering",
    "CounselingCaseReferenceExhausted",
    "CounselingCaseReviewRequired",
    "CounselingCaseSessionAlreadyLinked",
    "CounselingCaseSessionNotFound",
    "CounselingCaseSessionStudentMismatch",
    "CounselingCaseSourceInvalid",
    "CounselingCaseSourceNotFound",
    "EncounterCaseLink",
    "encounter_case_links",
    "get_case",
    "get_opening_context",
    "link_recorded_session",
    "link_session",
    "list_my_cases",
    "list_session_candidates",
    "lock_case_for_recording",
    "open_case",
    "unlink_session",
]
