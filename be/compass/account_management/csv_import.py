"""Bounded CSV account provisioning for the Account Management domain."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass

from django.db import IntegrityError, transaction

from compass.accounts.models import Role, User
from compass.audit.actions import ACCOUNT_CREATED, ACCOUNT_CSV_IMPORTED
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event

from .services import (
    InvalidManagementInput,
    ManagementConfigurationError,
    _assert_manager,
    _assert_recent_mfa,
    _canonical_role_code,
    _clean_email,
    _clean_identity_text,
    _lock_management_mutex,
    _lock_users,
)

MAX_CSV_BYTES = 1_048_576
MAX_CSV_ROWS = 1_000
REQUIRED_HEADERS = frozenset({"email", "first_name", "last_name", "role"})
OPTIONAL_HEADERS = frozenset({"middle_name", "suffix"})
ALLOWED_HEADERS = REQUIRED_HEADERS | OPTIONAL_HEADERS


class CsvImportError(RuntimeError):
    """Base class for expected CSV provisioning failures."""


class CsvImportMalformed(CsvImportError):
    """The uploaded CSV is structurally invalid or uses unsupported input."""


class CsvImportUnsupportedHeaders(CsvImportMalformed):
    """The CSV header contract is missing required fields or contains unsupported fields."""


class CsvImportTooLarge(CsvImportError):
    """The uploaded CSV exceeds the bounded provisioning limits."""


class CsvImportInvalidRows(CsvImportError):
    """One or more rows contain invalid account-provisioning values."""

    def __init__(self, issues: tuple["CsvImportIssue", ...]) -> None:
        super().__init__("one or more CSV rows are invalid")
        self.issues = issues


class CsvImportDuplicateIdentity(CsvImportInvalidRows):
    """The same normalized email occurs more than once in the submitted CSV."""


class CsvImportConflict(CsvImportError):
    """One or more rows conflict with existing institutional account state."""

    def __init__(self, rows: tuple["CsvImportRowResult", ...]) -> None:
        super().__init__("one or more CSV rows conflict with existing account state")
        self.rows = rows


@dataclass(frozen=True, slots=True)
class CsvImportIssue:
    row_number: int
    email: str
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class CsvProvisionRow:
    row_number: int
    email: str
    first_name: str
    middle_name: str
    last_name: str
    suffix: str
    role: str


@dataclass(frozen=True, slots=True)
class CsvImportRowResult:
    row_number: int
    email: str
    action: str
    message: str = ""


@dataclass(frozen=True, slots=True)
class CsvImportReport:
    valid: bool
    committed: bool
    total_rows: int
    create_count: int
    skip_count: int
    conflict_count: int
    invalid_count: int
    rows: tuple[CsvImportRowResult, ...]


@dataclass(frozen=True, slots=True)
class ParsedCsv:
    rows: tuple[CsvProvisionRow, ...]
    issues: tuple[CsvImportIssue, ...]
    total_rows: int


def _decode_csv(data: bytes) -> str:
    if not isinstance(data, bytes):
        raise CsvImportMalformed("CSV content must be uploaded as bytes")
    if not data:
        raise CsvImportMalformed("CSV file is empty")
    if len(data) > MAX_CSV_BYTES:
        raise CsvImportTooLarge(f"CSV file must not exceed {MAX_CSV_BYTES} bytes")
    try:
        text = data.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError as exc:
        raise CsvImportMalformed("CSV must use UTF-8 encoding") from exc
    if "\x00" in text:
        raise CsvImportMalformed("CSV contains unsupported NUL characters")
    return text


def _headers(raw_headers: list[str]) -> tuple[str, ...]:
    headers = tuple(value.strip() for value in raw_headers)
    if not headers or not any(headers):
        raise CsvImportMalformed("CSV header row is required")
    if len(set(headers)) != len(headers):
        raise CsvImportUnsupportedHeaders("CSV contains duplicate headers")
    missing = sorted(REQUIRED_HEADERS - set(headers))
    if missing:
        raise CsvImportUnsupportedHeaders(
            "CSV is missing required headers: " + ", ".join(missing)
        )
    unknown = sorted(set(headers) - ALLOWED_HEADERS)
    if unknown:
        raise CsvImportUnsupportedHeaders(
            "CSV contains unsupported headers: " + ", ".join(unknown)
        )
    return headers


def _parse_csv(data: bytes) -> ParsedCsv:
    text = _decode_csv(data)
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    try:
        raw_headers = next(reader)
    except StopIteration as exc:
        raise CsvImportMalformed("CSV header row is required") from exc
    except csv.Error as exc:
        raise CsvImportMalformed("CSV could not be parsed") from exc

    headers = _headers(raw_headers)
    rows: list[CsvProvisionRow] = []
    issues: list[CsvImportIssue] = []
    seen_emails: dict[str, int] = {}
    total_rows = 0

    try:
        for physical_row_number, values in enumerate(reader, start=2):
            if not values or all(not value.strip() for value in values):
                continue
            total_rows += 1
            if total_rows > MAX_CSV_ROWS:
                raise CsvImportTooLarge(f"CSV must not contain more than {MAX_CSV_ROWS} rows")
            if len(values) != len(headers):
                raise CsvImportMalformed(
                    f"CSV row {physical_row_number} does not match the header column count"
                )
            raw = {header: value for header, value in zip(headers, values, strict=True)}
            raw_email = raw.get("email", "").strip()
            try:
                email = _clean_email(raw_email)
                first_name = _clean_identity_text(
                    "first_name", raw.get("first_name"), required=True
                )
                last_name = _clean_identity_text(
                    "last_name", raw.get("last_name"), required=True
                )
                middle_name = _clean_identity_text(
                    "middle_name", raw.get("middle_name", ""), allow_none=True
                )
                suffix = _clean_identity_text(
                    "suffix", raw.get("suffix", ""), allow_none=True
                )
                role = _canonical_role_code(raw.get("role", ""))
            except InvalidManagementInput as exc:
                issues.append(
                    CsvImportIssue(
                        row_number=physical_row_number,
                        email=raw_email,
                        code="invalid_row",
                        message=str(exc),
                    )
                )
                continue

            duplicate_of = seen_emails.get(email.casefold())
            if duplicate_of is not None:
                issues.append(
                    CsvImportIssue(
                        row_number=physical_row_number,
                        email=email,
                        code="duplicate_identity",
                        message=(
                            "duplicate email in CSV; first occurrence is row "
                            f"{duplicate_of}"
                        ),
                    )
                )
                continue
            seen_emails[email.casefold()] = physical_row_number
            rows.append(
                CsvProvisionRow(
                    row_number=physical_row_number,
                    email=email,
                    first_name=first_name,
                    middle_name=middle_name,
                    last_name=last_name,
                    suffix=suffix,
                    role=role,
                )
            )
    except csv.Error as exc:
        raise CsvImportMalformed("CSV could not be parsed") from exc

    if total_rows == 0:
        raise CsvImportMalformed("CSV must contain at least one account row")
    return ParsedCsv(rows=tuple(rows), issues=tuple(issues), total_rows=total_rows)


def _normalized_identity(row: CsvProvisionRow) -> tuple[str, str, str, str]:
    return tuple(
        value.strip().casefold()
        for value in (row.first_name, row.middle_name, row.last_name, row.suffix)
    )


def _existing_identity(user: User) -> tuple[str, str, str, str]:
    return tuple(
        value.strip().casefold()
        for value in (user.first_name, user.middle_name, user.last_name, user.suffix)
    )


def _classify_rows(
    rows: tuple[CsvProvisionRow, ...],
    *,
    lock_existing: bool,
) -> tuple[CsvImportRowResult, ...]:
    emails = tuple(row.email for row in rows)
    queryset = User.objects.select_related("role").filter(email__in=emails)
    if lock_existing:
        queryset = queryset.select_for_update()
    existing = {user.email.casefold(): user for user in queryset}
    results: list[CsvImportRowResult] = []

    for row in rows:
        current = existing.get(row.email.casefold())
        if current is None:
            results.append(
                CsvImportRowResult(
                    row_number=row.row_number,
                    email=row.email,
                    action="CREATE",
                )
            )
            continue
        if (
            current.is_active
            and current.role.code == row.role
            and _existing_identity(current) == _normalized_identity(row)
        ):
            results.append(
                CsvImportRowResult(
                    row_number=row.row_number,
                    email=row.email,
                    action="SKIP",
                )
            )
            continue
        reason = "existing account is disabled"
        if current.is_active and current.role.code != row.role:
            reason = "existing account has a different role"
        elif current.is_active:
            reason = "existing account has different identity fields"
        results.append(
            CsvImportRowResult(
                row_number=row.row_number,
                email=row.email,
                action="CONFLICT",
                message=reason,
            )
        )
    return tuple(results)


def _report(
    parsed: ParsedCsv,
    classified: tuple[CsvImportRowResult, ...],
    *,
    committed: bool,
) -> CsvImportReport:
    invalid_rows = tuple(
        CsvImportRowResult(
            row_number=issue.row_number,
            email=issue.email,
            action="INVALID",
            message=issue.message,
        )
        for issue in parsed.issues
    )
    rows = tuple(sorted((*classified, *invalid_rows), key=lambda item: item.row_number))
    create_count = sum(item.action == "CREATE" for item in rows)
    skip_count = sum(item.action == "SKIP" for item in rows)
    conflict_count = sum(item.action == "CONFLICT" for item in rows)
    invalid_count = sum(item.action == "INVALID" for item in rows)
    return CsvImportReport(
        valid=conflict_count == 0 and invalid_count == 0,
        committed=committed,
        total_rows=parsed.total_rows,
        create_count=create_count,
        skip_count=skip_count,
        conflict_count=conflict_count,
        invalid_count=invalid_count,
        rows=rows,
    )


def provision_accounts_from_csv(
    *,
    actor: User,
    actor_session,
    context: AuditContext,
    data: bytes,
    dry_run: bool,
) -> CsvImportReport:
    parsed = _parse_csv(data)

    if dry_run:
        with transaction.atomic():
            locked_actor, _target = _lock_users(actor_id=actor.pk)
            _assert_manager(locked_actor)
            _assert_recent_mfa(actor=locked_actor, actor_session=actor_session)
            classified = _classify_rows(parsed.rows, lock_existing=False)
        return _report(parsed, classified, committed=False)

    if parsed.issues:
        if any(issue.code == "duplicate_identity" for issue in parsed.issues):
            raise CsvImportDuplicateIdentity(parsed.issues)
        raise CsvImportInvalidRows(parsed.issues)

    with transaction.atomic():
        _lock_management_mutex()
        locked_actor, _target = _lock_users(actor_id=actor.pk)
        _assert_manager(locked_actor)
        _assert_recent_mfa(actor=locked_actor, actor_session=actor_session)

        classified = _classify_rows(parsed.rows, lock_existing=True)
        conflicts = tuple(item for item in classified if item.action == "CONFLICT")
        if conflicts:
            raise CsvImportConflict(conflicts)

        classification_by_row = {item.row_number: item for item in classified}
        create_rows = {
            row.row_number: row
            for row in parsed.rows
            if classification_by_row[row.row_number].action == "CREATE"
        }
        requested_roles = {row.role for row in create_rows.values()}
        role_records = {
            role.code: role for role in Role.objects.filter(code__in=requested_roles)
        }
        if set(role_records) != requested_roles:
            raise ManagementConfigurationError(
                "a requested canonical role is not synchronized; run sync_identity_policy first"
            )

        try:
            for row in create_rows.values():
                user = User.objects.create_user(
                    email=row.email,
                    password=None,
                    role=role_records[row.role],
                    first_name=row.first_name,
                    middle_name=row.middle_name,
                    last_name=row.last_name,
                    suffix=row.suffix,
                    is_active=True,
                )
                record_event(
                    context=context,
                    action=ACCOUNT_CREATED,
                    outcome=AuditOutcome.SUCCESS,
                    target_type="accounts.user",
                    target_id=user.pk,
                    metadata={"role": row.role},
                )
        except IntegrityError as exc:
            raise CsvImportConflict(
                (
                    CsvImportRowResult(
                        row_number=0,
                        email="",
                        action="CONFLICT",
                        message="account state changed while the CSV import was committing",
                    ),
                )
            ) from exc

        create_count = len(create_rows)
        skip_count = sum(item.action == "SKIP" for item in classified)
        record_event(
            context=context,
            action=ACCOUNT_CSV_IMPORTED,
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "created_count": create_count,
                "skipped_count": skip_count,
                "total_validated_rows": parsed.total_rows,
            },
        )

    return _report(parsed, classified, committed=True)


__all__ = [
    "ALLOWED_HEADERS",
    "CsvImportConflict",
    "CsvImportDuplicateIdentity",
    "CsvImportError",
    "CsvImportInvalidRows",
    "CsvImportIssue",
    "CsvImportMalformed",
    "CsvImportReport",
    "CsvImportRowResult",
    "CsvImportTooLarge",
    "CsvImportUnsupportedHeaders",
    "MAX_CSV_BYTES",
    "MAX_CSV_ROWS",
    "OPTIONAL_HEADERS",
    "REQUIRED_HEADERS",
    "provision_accounts_from_csv",
]
