"""Bounded CSV reconciliation of current Student College placement."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from uuid import UUID

from django.db import IntegrityError, transaction

from compass.accounts.models import User
from compass.audit.actions import STUDENT_ACADEMICS_ROSTER_IMPORTED
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.organization.integrity import catalog_dependent_write
from compass.organization.models import Campus, College, normalize_code
from compass.student_academics.models import StudentAcademicProfile
from compass.student_academics.services import set_current_placement

MAX_CSV_BYTES = 1_048_576
MAX_CSV_ROWS = 1_000
REQUIRED_HEADERS = frozenset({"institutional_id", "campus_code", "college_code"})


class RosterImportError(RuntimeError):
    """Base class for expected roster import failures."""


class RosterImportMalformed(RosterImportError):
    """The uploaded CSV is structurally invalid or uses unsupported input."""


class RosterImportUnsupportedHeaders(RosterImportMalformed):
    """The CSV header contract is missing required fields or contains unsupported fields."""


class RosterImportTooLarge(RosterImportError):
    """The uploaded CSV exceeds the bounded import limits."""


class RosterImportInvalidRows(RosterImportError):
    """One or more rows contain invalid roster values."""

    def __init__(self, issues: tuple[RosterImportIssue, ...]) -> None:
        super().__init__("one or more CSV rows are invalid")
        self.issues = issues


class RosterImportDuplicateIdentity(RosterImportInvalidRows):
    """A normalized Institutional ID occurs more than once in the submitted CSV."""


class RosterImportConflict(RosterImportError):
    """One or more rows conflict with existing Student academic state."""

    def __init__(self, rows: tuple[RosterImportRowResult, ...]) -> None:
        super().__init__("one or more CSV rows conflict with existing Student academic state")
        self.rows = rows


@dataclass(frozen=True, slots=True)
class RosterImportIssue:
    row_number: int
    institutional_id: str
    campus_code: str
    college_code: str
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class RosterImportRow:
    row_number: int
    institutional_id: str
    campus_code: str
    college_code: str


@dataclass(frozen=True, slots=True)
class RosterImportRowResult:
    row_number: int
    institutional_id: str
    student_id: UUID | None
    student_name: str
    current_college_code: str | None
    campus_code: str
    college_code: str
    action: str
    message: str


@dataclass(frozen=True, slots=True)
class RosterImportReport:
    valid: bool
    committed: bool
    total_rows: int
    set_count: int
    noop_count: int
    conflict_count: int
    invalid_count: int
    rows: tuple[RosterImportRowResult, ...]


@dataclass(frozen=True, slots=True)
class ParsedRosterCsv:
    rows: tuple[RosterImportRow, ...]
    issues: tuple[RosterImportIssue, ...]
    total_rows: int


@dataclass(frozen=True, slots=True)
class _RosterResolution:
    users: dict[str, User]
    campuses: dict[str, Campus]
    colleges: dict[tuple[UUID, str], College]
    profiles: dict[UUID, StudentAcademicProfile]


def _decode_csv(data: bytes) -> str:
    if not isinstance(data, bytes):
        raise RosterImportMalformed("CSV content must be uploaded as bytes")
    if not data:
        raise RosterImportMalformed("CSV file is empty")
    if len(data) > MAX_CSV_BYTES:
        raise RosterImportTooLarge(f"CSV file must not exceed {MAX_CSV_BYTES} bytes")
    try:
        text = data.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError as exc:
        raise RosterImportMalformed("CSV must use UTF-8 encoding") from exc
    if "\x00" in text:
        raise RosterImportMalformed("CSV contains unsupported NUL characters")
    return text


def _headers(raw_headers: list[str]) -> tuple[str, ...]:
    headers = tuple(value.strip() for value in raw_headers)
    if not headers or not any(headers):
        raise RosterImportMalformed("CSV header row is required")
    if len(set(headers)) != len(headers):
        raise RosterImportUnsupportedHeaders("CSV contains duplicate headers")
    missing = sorted(REQUIRED_HEADERS - set(headers))
    if missing:
        raise RosterImportUnsupportedHeaders(
            "CSV is missing required headers: " + ", ".join(missing)
        )
    unknown = sorted(set(headers) - REQUIRED_HEADERS)
    if unknown:
        raise RosterImportUnsupportedHeaders(
            "CSV contains unsupported headers: " + ", ".join(unknown)
        )
    return headers


def _parse_csv(data: bytes) -> ParsedRosterCsv:
    text = _decode_csv(data)
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    try:
        raw_headers = next(reader)
    except StopIteration as exc:
        raise RosterImportMalformed("CSV header row is required") from exc
    except csv.Error as exc:
        raise RosterImportMalformed(
            "Couldn't read the CSV file. Check its format and try again."
        ) from exc

    headers = _headers(raw_headers)
    rows: list[RosterImportRow] = []
    issues: list[RosterImportIssue] = []
    seen_institutional_ids: dict[str, int] = {}
    total_rows = 0

    try:
        for physical_row_number, values in enumerate(reader, start=2):
            if not values or all(not value.strip() for value in values):
                continue
            total_rows += 1
            if total_rows > MAX_CSV_ROWS:
                raise RosterImportTooLarge(f"CSV must not contain more than {MAX_CSV_ROWS} rows")
            if len(values) != len(headers):
                raise RosterImportMalformed(
                    f"CSV row {physical_row_number} does not match the header column count"
                )
            raw = {header: value.strip() for header, value in zip(headers, values, strict=True)}
            raw_institutional_id = raw["institutional_id"]
            raw_campus_code = raw["campus_code"]
            raw_college_code = raw["college_code"]
            try:
                institutional_id = User.objects.normalize_institutional_id(raw_institutional_id)
                if institutional_id is None:
                    raise ValueError("institutional_id is required")
            except ValueError:
                issues.append(
                    RosterImportIssue(
                        row_number=physical_row_number,
                        institutional_id=raw_institutional_id,
                        campus_code=raw_campus_code,
                        college_code=raw_college_code,
                        code="invalid_row",
                        message=(
                            "institutional_id is required"
                            if not raw_institutional_id
                            else "institutional_id is invalid"
                        ),
                    )
                )
                continue

            campus_code = normalize_code(raw_campus_code)
            college_code = normalize_code(raw_college_code)
            if not campus_code or not college_code:
                issues.append(
                    RosterImportIssue(
                        row_number=physical_row_number,
                        institutional_id=institutional_id,
                        campus_code=raw_campus_code,
                        college_code=raw_college_code,
                        code="invalid_row",
                        message=(
                            "campus_code is required"
                            if not campus_code
                            else "college_code is required"
                        ),
                    )
                )
                continue

            first_occurrence = seen_institutional_ids.get(institutional_id.casefold())
            if first_occurrence is not None:
                issues.append(
                    RosterImportIssue(
                        row_number=physical_row_number,
                        institutional_id=institutional_id,
                        campus_code=campus_code,
                        college_code=college_code,
                        code="duplicate_identity",
                        message=(
                            "duplicate institutional_id in CSV; first occurrence is row "
                            f"{first_occurrence}"
                        ),
                    )
                )
                continue
            seen_institutional_ids[institutional_id.casefold()] = physical_row_number
            rows.append(
                RosterImportRow(
                    row_number=physical_row_number,
                    institutional_id=institutional_id,
                    campus_code=campus_code,
                    college_code=college_code,
                )
            )
    except csv.Error as exc:
        raise RosterImportMalformed(
            "Couldn't read the CSV file. Check its format and try again."
        ) from exc

    if total_rows == 0:
        raise RosterImportMalformed("CSV must contain at least one roster row")
    return ParsedRosterCsv(rows=tuple(rows), issues=tuple(issues), total_rows=total_rows)


def _load_resolution(*, rows: tuple[RosterImportRow, ...], lock: bool) -> _RosterResolution:
    institutional_ids = sorted({row.institutional_id for row in rows})
    campus_codes = sorted({row.campus_code for row in rows})
    college_codes = sorted({row.college_code for row in rows})

    users_queryset = User.objects.select_related("role").filter(
        institutional_id__in=institutional_ids
    )
    if lock:
        users_queryset = users_queryset.select_for_update(of=("self",)).order_by("pk")
    users = {
        user.institutional_id: user for user in users_queryset if user.institutional_id is not None
    }

    campuses_queryset = Campus.objects.filter(code__in=campus_codes)
    if lock:
        campuses_queryset = campuses_queryset.select_for_update().order_by("pk")
    campuses = {campus.code: campus for campus in campuses_queryset}

    colleges_queryset = College.objects.select_related("campus").filter(code__in=college_codes)
    if lock:
        colleges_queryset = colleges_queryset.select_for_update(of=("self", "campus")).order_by(
            "pk"
        )
    colleges = {(college.campus_id, college.code): college for college in colleges_queryset}
    for college in colleges.values():
        campuses[college.campus.code] = college.campus

    profiles_queryset = StudentAcademicProfile.objects.select_related("current_college").filter(
        student_id__in=[user.pk for user in users.values()]
    )
    if lock:
        profiles_queryset = profiles_queryset.select_for_update(of=("self",)).order_by("student_id")
    profiles = {profile.student_id: profile for profile in profiles_queryset}

    return _RosterResolution(
        users=users,
        campuses=campuses,
        colleges=colleges,
        profiles=profiles,
    )


def _result(
    row: RosterImportRow,
    *,
    action: str,
    message: str,
    user: User | None = None,
    profile: StudentAcademicProfile | None = None,
) -> RosterImportRowResult:
    return RosterImportRowResult(
        row_number=row.row_number,
        institutional_id=row.institutional_id,
        student_id=user.pk if user is not None else None,
        student_name=user.get_full_name() if user is not None else "",
        current_college_code=(
            profile.current_college.code
            if profile is not None and profile.current_college_id is not None
            else None
        ),
        campus_code=row.campus_code,
        college_code=row.college_code,
        action=action,
        message=message,
    )


def _classify(
    rows: tuple[RosterImportRow, ...], resolution: _RosterResolution
) -> tuple[RosterImportRowResult, ...]:
    results: list[RosterImportRowResult] = []
    for row in rows:
        user = resolution.users.get(row.institutional_id)
        if user is None:
            results.append(
                _result(
                    row,
                    action="CONFLICT",
                    message="institutional_id does not resolve to an existing account",
                )
            )
            continue
        profile = resolution.profiles.get(user.pk)
        if user.role.code != "STUDENT":
            results.append(
                _result(
                    row,
                    action="CONFLICT",
                    message="the account does not have the STUDENT role",
                    user=user,
                    profile=profile,
                )
            )
            continue
        if not user.is_active:
            results.append(
                _result(
                    row,
                    action="CONFLICT",
                    message="the Student account is inactive",
                    user=user,
                    profile=profile,
                )
            )
            continue
        campus = resolution.campuses.get(row.campus_code)
        if campus is None or not campus.is_active:
            results.append(
                _result(
                    row,
                    action="CONFLICT",
                    message="campus_code does not resolve to an active Campus",
                    user=user,
                    profile=profile,
                )
            )
            continue
        college = resolution.colleges.get((campus.pk, row.college_code))
        if college is None or not college.is_active or not college.campus.is_active:
            results.append(
                _result(
                    row,
                    action="CONFLICT",
                    message=(
                        "college_code does not resolve to an active College beneath that Campus"
                    ),
                    user=user,
                    profile=profile,
                )
            )
            continue
        if profile is not None and profile.current_college_id == college.pk:
            results.append(
                _result(
                    row,
                    action="NOOP",
                    message="the placement already matches",
                    user=user,
                    profile=profile,
                )
            )
            continue
        results.append(
            _result(
                row,
                action="SET",
                message=(
                    "the placement will be assigned"
                    if profile is None or profile.current_college_id is None
                    else "the placement will be updated"
                ),
                user=user,
                profile=profile,
            )
        )
    return tuple(results)


def _report(
    parsed: ParsedRosterCsv,
    classified: tuple[RosterImportRowResult, ...],
    *,
    committed: bool,
) -> RosterImportReport:
    invalid_rows = tuple(
        RosterImportRowResult(
            row_number=issue.row_number,
            institutional_id=issue.institutional_id,
            student_id=None,
            student_name="",
            current_college_code=None,
            campus_code=issue.campus_code,
            college_code=issue.college_code,
            action="INVALID",
            message=issue.message,
        )
        for issue in parsed.issues
    )
    rows = tuple(sorted((*classified, *invalid_rows), key=lambda item: item.row_number))
    set_count = sum(item.action == "SET" for item in rows)
    noop_count = sum(item.action == "NOOP" for item in rows)
    conflict_count = sum(item.action == "CONFLICT" for item in rows)
    invalid_count = sum(item.action == "INVALID" for item in rows)
    return RosterImportReport(
        valid=conflict_count == 0 and invalid_count == 0,
        committed=committed,
        total_rows=parsed.total_rows,
        set_count=set_count,
        noop_count=noop_count,
        conflict_count=conflict_count,
        invalid_count=invalid_count,
        rows=rows,
    )


def _commit(parsed: ParsedRosterCsv, *, context: AuditContext) -> RosterImportReport:
    try:
        with transaction.atomic():
            resolution = _load_resolution(rows=parsed.rows, lock=True)
            classified = _classify(parsed.rows, resolution)
            conflicts = tuple(item for item in classified if item.action == "CONFLICT")
            if conflicts:
                raise RosterImportConflict(conflicts)

            row_by_number = {row.row_number: row for row in parsed.rows}
            apply_rows = []
            for result in classified:
                if result.action != "SET":
                    continue
                row = row_by_number[result.row_number]
                campus = resolution.campuses[row.campus_code]
                college = resolution.colleges[(campus.pk, row.college_code)]
                apply_rows.append((result, resolution.users[result.institutional_id], college))
            apply_rows.sort(key=lambda item: item[1].pk)

            for _result_item, student, college in apply_rows:
                set_current_placement(
                    student_id=student.pk,
                    college_id=college.pk,
                    expected_campus_id=college.campus_id,
                    context=context,
                )

            report = _report(parsed, classified, committed=True)
            if report.set_count > 0:
                record_event(
                    context=context,
                    action=STUDENT_ACADEMICS_ROSTER_IMPORTED,
                    outcome=AuditOutcome.SUCCESS,
                    metadata={
                        "total_rows": report.total_rows,
                        "set_count": report.set_count,
                        "noop_count": report.noop_count,
                    },
                )
            return report
    except IntegrityError as exc:
        raise RosterImportConflict(
            (
                RosterImportRowResult(
                    row_number=0,
                    institutional_id="",
                    student_id=None,
                    student_name="",
                    current_college_code=None,
                    campus_code="",
                    college_code="",
                    action="CONFLICT",
                    message="student academic state changed while the roster import was committing",
                ),
            )
        ) from exc


@catalog_dependent_write
def import_student_academic_roster(
    *,
    context: AuditContext,
    data: bytes,
    dry_run: bool,
) -> RosterImportReport:
    parsed = _parse_csv(data)
    if dry_run:
        resolution = _load_resolution(rows=parsed.rows, lock=False)
        return _report(parsed, _classify(parsed.rows, resolution), committed=False)

    if parsed.issues:
        if any(issue.code == "duplicate_identity" for issue in parsed.issues):
            raise RosterImportDuplicateIdentity(parsed.issues)
        raise RosterImportInvalidRows(parsed.issues)
    return _commit(parsed, context=context)


__all__ = [
    "MAX_CSV_BYTES",
    "MAX_CSV_ROWS",
    "REQUIRED_HEADERS",
    "RosterImportConflict",
    "RosterImportDuplicateIdentity",
    "RosterImportError",
    "RosterImportInvalidRows",
    "RosterImportIssue",
    "RosterImportMalformed",
    "RosterImportReport",
    "RosterImportRow",
    "RosterImportRowResult",
    "RosterImportTooLarge",
    "RosterImportUnsupportedHeaders",
    "import_student_academic_roster",
]
