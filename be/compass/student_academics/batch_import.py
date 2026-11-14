"""Batch CSV imports of Student term (academic period) records and graduation records.

Both follow the roster import: one bounded UTF-8 CSV, a dry-run preview, then an all-or-nothing
apply that writes every row through the same single-record service the forms use, so validation,
side effects and per-record audit events are identical. The apply step also requires the preview's
fingerprint: if any affected record changed after the preview, nothing is saved and the operator
validates again. Uploaded files are never stored, and audit metadata carries counts only.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import UUID

from django.db import IntegrityError, transaction

from compass.accounts.models import StudentLifecycleStatus, User
from compass.audit.actions import (
    STUDENT_ACADEMICS_GRADUATIONS_IMPORTED,
    STUDENT_ACADEMICS_PERIODS_IMPORTED,
)
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.organization.integrity import catalog_dependent_write
from compass.organization.models import AcademicYear, College, normalize_code
from compass.student_academics.models import (
    AcademicTerm,
    EnrollmentStatus,
    StudentAcademicPeriodRecord,
    StudentGraduationRecord,
)
from compass.student_academics.roster_import import (
    MAX_CSV_ROWS,
    RosterImportConflict,
    RosterImportDuplicateIdentity,
    RosterImportInvalidRows,
    RosterImportMalformed,
    RosterImportTooLarge,
    RosterImportUnsupportedHeaders,
    _decode_csv,
    _load_resolution,
    _RosterResolution,
)
from compass.student_academics.services import (
    InvalidStudentAcademicInput,
    StudentAcademicNotFound,
    record_academic_period,
    record_graduation,
)

PERIOD_HEADERS = (
    "institutional_id",
    "campus_code",
    "college_code",
    "year_level",
    "enrollment_status",
)
PERIOD_REQUIRED_HEADERS = frozenset({"institutional_id", "campus_code", "college_code"})
GRADUATION_HEADERS = ("institutional_id", "campus_code", "college_code", "graduation_date")
GRADUATION_REQUIRED_HEADERS = frozenset(GRADUATION_HEADERS)
MAX_VERIFICATION_SOURCE_LENGTH = 200
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_WHOLE_NUMBER = re.compile(r"^\d{1,2}$")


class BatchImportStale(RuntimeError):
    """Affected records changed after the preview; the operator must validate again."""


class BatchImportPreviewRequired(RuntimeError):
    """An apply request arrived without the fingerprint of the preview it confirms."""


class BatchImportConfirmationMismatch(RuntimeError):
    """The typed confirmation count does not match the Students the import will write."""


@dataclass(frozen=True, slots=True)
class BatchImportIssue:
    row_number: int
    institutional_id: str
    campus_code: str
    college_code: str
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class _RawRow:
    row_number: int
    values: dict[str, str]


@dataclass(frozen=True, slots=True)
class PeriodImportRow:
    row_number: int
    institutional_id: str
    campus_code: str
    college_code: str
    year_level: int | None
    enrollment_status: str


@dataclass(frozen=True, slots=True)
class PeriodImportRowResult:
    row_number: int
    institutional_id: str
    student_id: UUID | None
    student_name: str
    campus_code: str
    college_code: str
    year_level: int | None
    enrollment_status: str
    current_college_code: str | None
    current_year_level: int | None
    current_enrollment_status: str | None
    action: str
    message: str


@dataclass(frozen=True, slots=True)
class PeriodImportReport:
    valid: bool
    committed: bool
    total_rows: int
    create_count: int
    update_count: int
    noop_count: int
    conflict_count: int
    invalid_count: int
    preview_fingerprint: str
    rows: tuple[PeriodImportRowResult, ...]


@dataclass(frozen=True, slots=True)
class GraduationImportRow:
    row_number: int
    institutional_id: str
    campus_code: str
    college_code: str
    graduation_date: date


@dataclass(frozen=True, slots=True)
class GraduationImportRowResult:
    row_number: int
    institutional_id: str
    student_id: UUID | None
    student_name: str
    campus_code: str
    college_code: str
    graduation_date: str
    lifecycle_status: str | None
    current_placement_college_code: str | None
    previous_college_code: str | None
    previous_graduation_date: str | None
    action: str
    message: str


@dataclass(frozen=True, slots=True)
class GraduationImportReport:
    valid: bool
    committed: bool
    total_rows: int
    graduate_count: int
    update_count: int
    noop_count: int
    conflict_count: int
    invalid_count: int
    write_count: int
    placement_cleared_count: int
    preview_fingerprint: str
    rows: tuple[GraduationImportRowResult, ...]


# ── Parsing ─────────────────────────────────────────────────────────────────────────────────


def _headers(
    raw_headers: list[str], *, allowed: tuple[str, ...], required: frozenset[str]
) -> tuple[str, ...]:
    headers = tuple(value.strip() for value in raw_headers)
    if not headers or not any(headers):
        raise RosterImportMalformed("CSV header row is required")
    if len(set(headers)) != len(headers):
        raise RosterImportUnsupportedHeaders("CSV contains duplicate headers")
    missing = sorted(required - set(headers))
    if missing:
        raise RosterImportUnsupportedHeaders(
            "CSV is missing required headers: " + ", ".join(missing)
        )
    unknown = sorted(set(headers) - set(allowed))
    if unknown:
        raise RosterImportUnsupportedHeaders(
            "CSV contains unsupported headers: " + ", ".join(unknown)
        )
    return headers


def _read_rows(
    data: bytes, *, allowed: tuple[str, ...], required: frozenset[str]
) -> tuple[_RawRow, ...]:
    text = _decode_csv(data)
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    unreadable = "Couldn't read the CSV file. Check its format and try again."
    try:
        raw_headers = next(reader)
    except StopIteration as exc:
        raise RosterImportMalformed("CSV header row is required") from exc
    except csv.Error as exc:
        raise RosterImportMalformed(unreadable) from exc
    headers = _headers(raw_headers, allowed=allowed, required=required)
    rows: list[_RawRow] = []
    try:
        for physical_row_number, values in enumerate(reader, start=2):
            if not values or all(not value.strip() for value in values):
                continue
            if len(rows) >= MAX_CSV_ROWS:
                raise RosterImportTooLarge(f"CSV must not contain more than {MAX_CSV_ROWS} rows")
            if len(values) != len(headers):
                raise RosterImportMalformed(
                    f"CSV row {physical_row_number} does not match the header column count"
                )
            raw = {header: value.strip() for header, value in zip(headers, values, strict=True)}
            rows.append(_RawRow(physical_row_number, {name: raw.get(name, "") for name in allowed}))
    except csv.Error as exc:
        raise RosterImportMalformed(unreadable) from exc
    if not rows:
        raise RosterImportMalformed("CSV must contain at least one row")
    return tuple(rows)


def _identity(raw: _RawRow, seen: dict[str, int]) -> tuple[str, str, str] | BatchImportIssue:
    """Normalize the shared identity and placement columns, or explain why the row is invalid."""

    values = raw.values
    raw_id, raw_campus, raw_college = (
        values["institutional_id"],
        values["campus_code"],
        values["college_code"],
    )

    def issue(code: str, message: str, institutional_id: str = raw_id) -> BatchImportIssue:
        return BatchImportIssue(
            raw.row_number, institutional_id, raw_campus, raw_college, code, message
        )

    try:
        institutional_id = User.objects.normalize_institutional_id(raw_id)
        if institutional_id is None:
            raise ValueError
    except ValueError:
        return issue(
            "invalid_row",
            "institutional_id is required" if not raw_id else "institutional_id is invalid",
        )
    campus_code, college_code = normalize_code(raw_campus), normalize_code(raw_college)
    if not campus_code:
        return issue("invalid_row", "campus_code is required", institutional_id)
    if not college_code:
        return issue("invalid_row", "college_code is required", institutional_id)
    first = seen.get(institutional_id.casefold())
    if first is not None:
        return issue(
            "duplicate_identity",
            f"duplicate institutional_id in CSV; first occurrence is row {first}",
            institutional_id,
        )
    seen[institutional_id.casefold()] = raw.row_number
    return institutional_id, campus_code, college_code


def _parse_periods(
    data: bytes,
) -> tuple[tuple[PeriodImportRow, ...], tuple[BatchImportIssue, ...], int]:
    raw_rows = _read_rows(data, allowed=PERIOD_HEADERS, required=PERIOD_REQUIRED_HEADERS)
    rows: list[PeriodImportRow] = []
    issues: list[BatchImportIssue] = []
    seen: dict[str, int] = {}
    for raw in raw_rows:
        identity = _identity(raw, seen)
        if isinstance(identity, BatchImportIssue):
            issues.append(identity)
            continue
        institutional_id, campus_code, college_code = identity
        raw_level = raw.values["year_level"]
        raw_status = raw.values["enrollment_status"].upper()
        problem = None
        if raw_level and (not _WHOLE_NUMBER.match(raw_level) or not 1 <= int(raw_level) <= 8):
            problem = "year_level must be a whole number from 1 to 8, or blank"
        elif raw_status and raw_status not in EnrollmentStatus.values:
            problem = "enrollment_status must be ENROLLED, NOT_ENROLLED, UNKNOWN, or blank"
        if problem:
            issues.append(
                BatchImportIssue(
                    raw.row_number,
                    institutional_id,
                    campus_code,
                    college_code,
                    "invalid_row",
                    problem,
                )
            )
            continue
        rows.append(
            PeriodImportRow(
                row_number=raw.row_number,
                institutional_id=institutional_id,
                campus_code=campus_code,
                college_code=college_code,
                year_level=int(raw_level) if raw_level else None,
                enrollment_status=raw_status or EnrollmentStatus.UNKNOWN,
            )
        )
    return tuple(rows), tuple(issues), len(raw_rows)


def _parse_graduations(
    data: bytes,
) -> tuple[tuple[GraduationImportRow, ...], tuple[BatchImportIssue, ...], int]:
    raw_rows = _read_rows(data, allowed=GRADUATION_HEADERS, required=GRADUATION_REQUIRED_HEADERS)
    rows: list[GraduationImportRow] = []
    issues: list[BatchImportIssue] = []
    seen: dict[str, int] = {}
    for raw in raw_rows:
        identity = _identity(raw, seen)
        if isinstance(identity, BatchImportIssue):
            issues.append(identity)
            continue
        institutional_id, campus_code, college_code = identity
        raw_date = raw.values["graduation_date"]
        parsed: date | None = None
        if _ISO_DATE.match(raw_date):
            try:
                parsed = date.fromisoformat(raw_date)
            except ValueError:
                parsed = None
        if parsed is None:
            issues.append(
                BatchImportIssue(
                    raw.row_number,
                    institutional_id,
                    campus_code,
                    college_code,
                    "invalid_row",
                    "graduation_date is required as YYYY-MM-DD"
                    if not raw_date
                    else "graduation_date must be a real date as YYYY-MM-DD",
                )
            )
            continue
        rows.append(
            GraduationImportRow(raw.row_number, institutional_id, campus_code, college_code, parsed)
        )
    return tuple(rows), tuple(issues), len(raw_rows)


# ── Shared resolution ───────────────────────────────────────────────────────────────────────


def _student_and_college(
    row, resolution: _RosterResolution
) -> tuple[User | None, College | None, str]:
    """Apply the single-record rules: a Student account (inactive allowed) and an active College."""

    user = resolution.users.get(row.institutional_id)
    if user is None:
        return None, None, "institutional_id does not resolve to an existing account"
    if user.role.code != "STUDENT":
        return user, None, "the account does not have the STUDENT role"
    campus = resolution.campuses.get(row.campus_code)
    if campus is None or not campus.is_active:
        return user, None, "campus_code does not resolve to an active Campus"
    college = resolution.colleges.get((campus.pk, row.college_code))
    if college is None or not college.is_active or not college.campus.is_active:
        return user, None, "college_code does not resolve to an active College beneath that Campus"
    return user, college, ""


def _fingerprint(scope: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    encoded = json.dumps({"scope": scope, "rows": rows}, sort_keys=True, default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def _guarded(write: Callable[[], Any], *, what: str) -> Any:
    try:
        return write()
    except IntegrityError as exc:
        raise BatchImportStale(f"{what} changed while the import was saving") from exc


# ── Term (academic period) records ──────────────────────────────────────────────────────────


def _academic_year(academic_year_id: UUID) -> AcademicYear:
    academic_year = AcademicYear.objects.filter(pk=academic_year_id).first()
    if academic_year is None:
        raise StudentAcademicNotFound("The requested academic year was not found.")
    return academic_year


def _validate_term(term: str) -> str:
    if term not in AcademicTerm.values:
        raise InvalidStudentAcademicInput(f"term must be one of {', '.join(AcademicTerm.values)}")
    return term


def _classify_periods(
    rows: tuple[PeriodImportRow, ...],
    issues: tuple[BatchImportIssue, ...],
    total_rows: int,
    *,
    academic_year: AcademicYear,
    term: str,
    lock: bool,
    committed: bool = False,
) -> PeriodImportReport:
    resolution = _load_resolution(rows=rows, lock=lock)
    records_queryset = StudentAcademicPeriodRecord.objects.select_related("college").filter(
        academic_year=academic_year,
        term=term,
        student_id__in=[user.pk for user in resolution.users.values()],
    )
    if lock:
        records_queryset = records_queryset.select_for_update(of=("self",)).order_by("student_id")
    records = {record.student_id: record for record in records_queryset}
    results: list[PeriodImportRowResult] = []
    for row in rows:
        user, college, problem = _student_and_college(row, resolution)
        record = records.get(user.pk) if user is not None else None
        if problem:
            action, message = "CONFLICT", problem
        elif record is None:
            action, message = "CREATE", "the term record will be created"
        elif (record.college_id, record.year_level, record.enrollment_status) == (
            college.pk,
            row.year_level,
            row.enrollment_status,
        ):
            action, message = "NOOP", "the term record already matches"
        else:
            action, message = "UPDATE", "the term record will be updated"
        results.append(
            PeriodImportRowResult(
                row_number=row.row_number,
                institutional_id=row.institutional_id,
                student_id=user.pk if user is not None else None,
                student_name=user.get_full_name() if user is not None else "",
                campus_code=row.campus_code,
                college_code=row.college_code,
                year_level=row.year_level,
                enrollment_status=row.enrollment_status,
                current_college_code=record.college.code if record is not None else None,
                current_year_level=record.year_level if record is not None else None,
                current_enrollment_status=record.enrollment_status if record is not None else None,
                action=action,
                message=message,
            )
        )
    for issue in issues:
        results.append(
            PeriodImportRowResult(
                row_number=issue.row_number,
                institutional_id=issue.institutional_id,
                student_id=None,
                student_name="",
                campus_code=issue.campus_code,
                college_code=issue.college_code,
                year_level=None,
                enrollment_status="",
                current_college_code=None,
                current_year_level=None,
                current_enrollment_status=None,
                action="INVALID",
                message=issue.message,
            )
        )
    results.sort(key=lambda item: item.row_number)
    counts = {
        kind: sum(item.action == kind for item in results)
        for kind in ("CREATE", "UPDATE", "NOOP", "CONFLICT", "INVALID")
    }
    fingerprint = _fingerprint(
        {"kind": "periods", "academic_year_id": str(academic_year.pk), "term": term},
        [
            {
                "row": item.row_number,
                "action": item.action,
                "student_id": str(item.student_id) if item.student_id else None,
                "target": [item.college_code, item.year_level, item.enrollment_status],
                "current": [
                    item.current_college_code,
                    item.current_year_level,
                    item.current_enrollment_status,
                ],
            }
            for item in results
        ],
    )
    return PeriodImportReport(
        valid=counts["CONFLICT"] == 0 and counts["INVALID"] == 0,
        committed=committed,
        total_rows=total_rows,
        create_count=counts["CREATE"],
        update_count=counts["UPDATE"],
        noop_count=counts["NOOP"],
        conflict_count=counts["CONFLICT"],
        invalid_count=counts["INVALID"],
        preview_fingerprint=fingerprint,
        rows=tuple(results),
    )


@catalog_dependent_write
def import_student_academic_periods(
    *,
    context: AuditContext,
    data: bytes,
    academic_year_id: UUID,
    term: str,
    dry_run: bool,
    preview_fingerprint: str | None = None,
) -> PeriodImportReport:
    """Record one academic year and term for many Students. Current placement is never changed."""

    term = _validate_term(term)
    academic_year = _academic_year(academic_year_id)
    rows, issues, total_rows = _parse_periods(data)
    if dry_run:
        return _classify_periods(
            rows, issues, total_rows, academic_year=academic_year, term=term, lock=False
        )
    if not preview_fingerprint:
        raise BatchImportPreviewRequired("Validate the CSV before importing it.")
    if issues:
        if any(issue.code == "duplicate_identity" for issue in issues):
            raise RosterImportDuplicateIdentity(issues)
        raise RosterImportInvalidRows(issues)
    with transaction.atomic():
        report = _classify_periods(
            rows, issues, total_rows, academic_year=academic_year, term=term, lock=True
        )
        conflicts = tuple(item for item in report.rows if item.action == "CONFLICT")
        if conflicts:
            raise RosterImportConflict(conflicts)
        if report.preview_fingerprint != preview_fingerprint:
            raise BatchImportStale("Records changed after the preview. Validate the CSV again.")
        by_number = {row.row_number: row for row in rows}
        writes = sorted(
            (item for item in report.rows if item.action in {"CREATE", "UPDATE"}),
            key=lambda item: str(item.student_id),
        )
        colleges = _load_resolution(rows=rows, lock=False)
        for item in writes:
            row = by_number[item.row_number]
            campus = colleges.campuses[row.campus_code]
            college = colleges.colleges[(campus.pk, row.college_code)]
            _guarded(
                lambda item=item, row=row, college=college: record_academic_period(
                    student_id=item.student_id,
                    academic_year_id=academic_year.pk,
                    term=term,
                    college_id=college.pk,
                    year_level=row.year_level,
                    enrollment_status=row.enrollment_status,
                    context=context,
                ),
                what="A term record",
            )
        if writes:
            record_event(
                context=context,
                action=STUDENT_ACADEMICS_PERIODS_IMPORTED,
                outcome=AuditOutcome.SUCCESS,
                metadata={
                    "academic_year_id": str(academic_year.pk),
                    "term": term,
                    "total_rows": report.total_rows,
                    "create_count": report.create_count,
                    "update_count": report.update_count,
                    "noop_count": report.noop_count,
                },
            )
        return PeriodImportReport(**{**_asdict(report), "committed": True})


# ── Graduation records ──────────────────────────────────────────────────────────────────────


def _validate_source(verification_source: str) -> str:
    source = verification_source.strip() if isinstance(verification_source, str) else ""
    if not source:
        raise InvalidStudentAcademicInput("Enter the Verification source.")
    if len(source) > MAX_VERIFICATION_SOURCE_LENGTH:
        raise InvalidStudentAcademicInput("Verification source must be 200 characters or fewer.")
    return source


def _classify_graduations(
    rows: tuple[GraduationImportRow, ...],
    issues: tuple[BatchImportIssue, ...],
    total_rows: int,
    *,
    source: str,
    lock: bool,
    committed: bool = False,
) -> GraduationImportReport:
    resolution = _load_resolution(rows=rows, lock=lock)
    records_queryset = StudentGraduationRecord.objects.select_related("graduated_college").filter(
        student_id__in=[user.pk for user in resolution.users.values()]
    )
    if lock:
        records_queryset = records_queryset.select_for_update(of=("self",)).order_by("student_id")
    records = {record.student_id: record for record in records_queryset}
    results: list[GraduationImportRowResult] = []
    placement_cleared = 0
    for row in rows:
        user, college, problem = _student_and_college(row, resolution)
        record = records.get(user.pk) if user is not None else None
        profile = resolution.profiles.get(user.pk) if user is not None else None
        placement = (
            profile.current_college if profile is not None and profile.current_college_id else None
        )
        lifecycle = user.student_lifecycle_status if user is not None else None
        if problem:
            action, message = "CONFLICT", problem
        elif (
            record is not None
            and record.graduated_college_id == college.pk
            and record.graduated_program_id is None
            and record.graduation_date == row.graduation_date
            and record.verification_source == source
            and lifecycle == StudentLifecycleStatus.GRADUATED
            and placement is None
        ):
            action, message = "NOOP", "the graduation is already recorded"
        elif lifecycle != StudentLifecycleStatus.GRADUATED:
            action = "GRADUATE"
            message = (
                f"will become Graduated and leave the {placement.code} placement"
                if placement is not None
                else "will become Graduated"
            )
        else:
            action = "UPDATE"
            message = (
                "the graduation record will be updated"
                if record is not None
                else "the graduation record will be added"
            )
        if action in {"GRADUATE", "UPDATE"} and placement is not None:
            placement_cleared += 1
        results.append(
            GraduationImportRowResult(
                row_number=row.row_number,
                institutional_id=row.institutional_id,
                student_id=user.pk if user is not None else None,
                student_name=user.get_full_name() if user is not None else "",
                campus_code=row.campus_code,
                college_code=row.college_code,
                graduation_date=row.graduation_date.isoformat(),
                lifecycle_status=lifecycle,
                current_placement_college_code=placement.code if placement is not None else None,
                previous_college_code=record.graduated_college.code if record is not None else None,
                previous_graduation_date=record.graduation_date.isoformat()
                if record is not None
                else None,
                action=action,
                message=message,
            )
        )
    for issue in issues:
        results.append(
            GraduationImportRowResult(
                row_number=issue.row_number,
                institutional_id=issue.institutional_id,
                student_id=None,
                student_name="",
                campus_code=issue.campus_code,
                college_code=issue.college_code,
                graduation_date="",
                lifecycle_status=None,
                current_placement_college_code=None,
                previous_college_code=None,
                previous_graduation_date=None,
                action="INVALID",
                message=issue.message,
            )
        )
    results.sort(key=lambda item: item.row_number)
    counts = {
        kind: sum(item.action == kind for item in results)
        for kind in ("GRADUATE", "UPDATE", "NOOP", "CONFLICT", "INVALID")
    }
    fingerprint = _fingerprint(
        {"kind": "graduations", "verification_source": source},
        [
            {
                "row": item.row_number,
                "action": item.action,
                "student_id": str(item.student_id) if item.student_id else None,
                "target": [item.college_code, item.graduation_date],
                "current": [
                    item.lifecycle_status,
                    item.current_placement_college_code,
                    item.previous_college_code,
                    item.previous_graduation_date,
                ],
            }
            for item in results
        ],
    )
    return GraduationImportReport(
        valid=counts["CONFLICT"] == 0 and counts["INVALID"] == 0,
        committed=committed,
        total_rows=total_rows,
        graduate_count=counts["GRADUATE"],
        update_count=counts["UPDATE"],
        noop_count=counts["NOOP"],
        conflict_count=counts["CONFLICT"],
        invalid_count=counts["INVALID"],
        write_count=counts["GRADUATE"] + counts["UPDATE"],
        placement_cleared_count=placement_cleared,
        preview_fingerprint=fingerprint,
        rows=tuple(results),
    )


@catalog_dependent_write
def import_student_graduations(
    *,
    context: AuditContext,
    data: bytes,
    verification_source: str,
    dry_run: bool,
    preview_fingerprint: str | None = None,
    confirmed_count: int | None = None,
) -> GraduationImportReport:
    """Record graduations for many Students, with the single-record side effects for each.

    Each written Student becomes Graduated and leaves their current College placement. The apply
    step requires the preview fingerprint and the typed number of Students it will write.
    """

    source = _validate_source(verification_source)
    rows, issues, total_rows = _parse_graduations(data)
    if dry_run:
        return _classify_graduations(rows, issues, total_rows, source=source, lock=False)
    if not preview_fingerprint:
        raise BatchImportPreviewRequired("Validate the CSV before importing it.")
    if issues:
        if any(issue.code == "duplicate_identity" for issue in issues):
            raise RosterImportDuplicateIdentity(issues)
        raise RosterImportInvalidRows(issues)
    with transaction.atomic():
        report = _classify_graduations(rows, issues, total_rows, source=source, lock=True)
        conflicts = tuple(item for item in report.rows if item.action == "CONFLICT")
        if conflicts:
            raise RosterImportConflict(conflicts)
        if report.preview_fingerprint != preview_fingerprint:
            raise BatchImportStale("Records changed after the preview. Validate the CSV again.")
        if confirmed_count != report.write_count:
            raise BatchImportConfirmationMismatch(
                f"Type {report.write_count} to confirm the number of Students to record."
            )
        by_number = {row.row_number: row for row in rows}
        writes = sorted(
            (item for item in report.rows if item.action in {"GRADUATE", "UPDATE"}),
            key=lambda item: str(item.student_id),
        )
        colleges = _load_resolution(rows=rows, lock=False)
        for item in writes:
            row = by_number[item.row_number]
            campus = colleges.campuses[row.campus_code]
            college = colleges.colleges[(campus.pk, row.college_code)]
            _guarded(
                lambda item=item, row=row, college=college: record_graduation(
                    student_id=item.student_id,
                    graduated_college_id=college.pk,
                    graduation_date=row.graduation_date,
                    verification_source=source,
                    context=context,
                ),
                what="A graduation record",
            )
        if writes:
            record_event(
                context=context,
                action=STUDENT_ACADEMICS_GRADUATIONS_IMPORTED,
                outcome=AuditOutcome.SUCCESS,
                metadata={
                    "total_rows": report.total_rows,
                    "graduate_count": report.graduate_count,
                    "update_count": report.update_count,
                    "noop_count": report.noop_count,
                    "placement_cleared_count": report.placement_cleared_count,
                },
            )
        return GraduationImportReport(**{**_asdict(report), "committed": True})


def _asdict(report) -> dict[str, Any]:
    return {name: getattr(report, name) for name in report.__dataclass_fields__}


__all__ = [
    "GRADUATION_HEADERS",
    "MAX_VERIFICATION_SOURCE_LENGTH",
    "PERIOD_HEADERS",
    "BatchImportConfirmationMismatch",
    "BatchImportPreviewRequired",
    "BatchImportStale",
    "GraduationImportReport",
    "PeriodImportReport",
    "import_student_academic_periods",
    "import_student_graduations",
]
