"""Thin Django Ninja routes for purpose-built administrative account management."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import NoReturn
from uuid import UUID

from ninja import File, Router, Schema, Status
from ninja.files import UploadedFile
from pydantic import ConfigDict

from compass.accounts.models import StudentLifecycleStatus, UserCapabilityOverride
from compass.accounts.policy import CAPABILITY_CODES, DESIGNATION_CODES, ROLE_CODES
from compass.audit.context import AuditContext
from compass.authentication.abuse import AuthenticationRateLimited
from compass.authentication.api import session_auth
from compass.authentication.email_change import (
    EmailChangeConflict,
    EmailChangeError,
    EmailChangeInvalid,
    EmailChangeNotFound,
    EmailChangePermissionDenied,
    request_administrative_email_change,
)
from compass.authentication.email_otp import EmailOTPInvalid, EmailOTPSecurityUnavailable
from compass.authentication.sessions import RecentMFARequired, require_recent_mfa
from compass.common.api import response_with_errors
from compass.common.errors import APIError

from .csv_import import (
    MAX_CSV_BYTES,
    CsvImportConflict,
    CsvImportDuplicateIdentity,
    CsvImportInvalidRows,
    CsvImportMalformed,
    CsvImportReport,
    CsvImportTooLarge,
    CsvImportUnsupportedHeaders,
    provision_accounts_from_csv,
)
from .services import (
    DEFAULT_PAGE_SIZE,
    AccountManagementError,
    AccountNotFound,
    AppointmentRelationshipConflict,
    AvailabilityRelationshipConflict,
    DesignationManagementNotAuthorized,
    DesignationRoleConflict,
    DuplicateEmail,
    DuplicateInstitutionalId,
    InvalidManagementInput,
    LastAccountManagerError,
    ManagementConfigurationError,
    ManagementNotAuthorized,
    OrganizationRelationshipConflict,
    PaginationError,
    SelfTargetForbidden,
    StudentLifecycleConflict,
    assign_designation,
    change_role,
    create_account,
    get_account,
    list_accounts,
    list_capability_overrides,
    list_designations,
    remove_capability_override,
    remove_designation,
    reset_account_mfa,
    revoke_account_sessions,
    revoke_account_trusted_sessions,
    serialize_account,
    set_account_active,
    set_capability_override,
    set_student_lifecycle,
    update_identity,
)

router = Router(tags=["accounts"])


def _code_enum(name: str, codes: frozenset[str]) -> type[Enum]:
    members = {code.replace(".", "_").replace("-", "_").upper(): code for code in sorted(codes)}
    return Enum(name, members, module=__name__, type=str)


RoleCode = _code_enum("RoleCode", ROLE_CODES)
DesignationCode = _code_enum("DesignationCode", DESIGNATION_CODES)
CapabilityCode = _code_enum("CapabilityCode", CAPABILITY_CODES)
StudentLifecycleCode = _code_enum("StudentLifecycleCode", frozenset(StudentLifecycleStatus.values))


class StrictSchema(Schema):
    model_config = ConfigDict(extra="forbid")


class AccountSummaryResponse(StrictSchema):
    id: UUID
    institutional_id: str | None
    email: str
    first_name: str
    middle_name: str
    last_name: str
    suffix: str
    full_name: str
    role: RoleCode
    student_lifecycle_status: StudentLifecycleCode | None
    designations: list[DesignationCode]
    is_active: bool
    password_configured: bool
    email_verified: bool
    created_at: datetime


class AccountDetailResponse(AccountSummaryResponse):
    updated_at: datetime
    email_verified_at: datetime | None
    mfa_enabled: bool


class AccountListResponse(StrictSchema):
    items: list[AccountSummaryResponse]
    page: int
    page_size: int
    has_next: bool


class AccountCreateRequest(StrictSchema):
    institutional_id: str
    email: str
    first_name: str
    last_name: str
    role: RoleCode
    middle_name: str = ""
    suffix: str = ""
    is_active: bool = True


class IdentityUpdateRequest(StrictSchema):
    institutional_id: str | None = None
    first_name: str | None = None
    middle_name: str | None = None
    last_name: str | None = None
    suffix: str | None = None


class ManagedEmailChangeRequest(StrictSchema):
    new_email: str
    turnstile_token: str | None = None


class ManagedEmailChangeResponse(StrictSchema):
    request_id: UUID
    challenge_id: UUID
    expires_at: datetime


class RoleUpdateRequest(StrictSchema):
    role: RoleCode


class StudentLifecycleUpdateRequest(StrictSchema):
    status: StudentLifecycleCode


class DesignationListResponse(StrictSchema):
    designations: list[DesignationCode]


class CapabilityOverrideCreateRequest(StrictSchema):
    effect: UserCapabilityOverride.Effect
    reason: str
    expires_at: datetime | None = None


class CapabilityOverrideCreatorResponse(StrictSchema):
    id: UUID
    email: str
    full_name: str


class CapabilityOverrideResponse(StrictSchema):
    capability: CapabilityCode
    effect: UserCapabilityOverride.Effect
    reason: str
    expires_at: datetime | None
    created_at: datetime
    created_by: CapabilityOverrideCreatorResponse | None


class CapabilityOverrideListResponse(StrictSchema):
    overrides: list[CapabilityOverrideResponse]


class OverrideRemovalResponse(StrictSchema):
    removed: bool


class RevocationResponse(StrictSchema):
    revoked_count: int


class MFAResetResponse(StrictSchema):
    reset: bool
    revoked_session_count: int
    revoked_trusted_session_count: int


class CsvImportRowResponse(StrictSchema):
    row_number: int
    institutional_id: str
    email: str
    action: str
    message: str


class CsvImportResponse(StrictSchema):
    valid: bool
    committed: bool
    total_rows: int
    create_count: int
    skip_count: int
    conflict_count: int
    invalid_count: int
    rows: list[CsvImportRowResponse]


def _require_management(request, *, recent_mfa: bool) -> None:
    user = request.auth_user
    if not user.has_capability("accounts.manage"):
        raise APIError(
            403,
            "permission_denied",
            "The accounts.manage capability is required.",
        )
    if recent_mfa:
        try:
            require_recent_mfa(request.auth_session)
        except RecentMFARequired as exc:
            raise APIError(403, "recent_mfa_required", "Recent MFA is required.") from exc


def _require_designation_management(request) -> None:
    _require_management(request, recent_mfa=True)
    if not request.auth_user.has_capability("institutional_designations.manage"):
        raise APIError(
            403,
            "institutional_designation_permission_denied",
            (
                "The accounts.manage and institutional_designations.manage capabilities "
                "are required."
            ),
        )


def _raise_management_error(exc: AccountManagementError) -> NoReturn:
    if isinstance(exc, DesignationManagementNotAuthorized):
        raise APIError(
            403,
            "institutional_designation_permission_denied",
            (
                "The accounts.manage and institutional_designations.manage capabilities "
                "are required."
            ),
        ) from exc
    if isinstance(exc, DesignationRoleConflict):
        raise APIError(409, "designation_role_conflict", str(exc)) from exc
    if isinstance(exc, AccountNotFound):
        raise APIError(404, "account_not_found", "The requested account was not found.") from exc
    if isinstance(exc, DuplicateEmail):
        raise APIError(409, "email_in_use", "An account with this email already exists.") from exc
    if isinstance(exc, DuplicateInstitutionalId):
        raise APIError(
            409,
            "institutional_id_in_use",
            "An account with this Institutional ID already exists.",
        ) from exc
    if isinstance(exc, LastAccountManagerError):
        raise APIError(
            409,
            "last_account_manager",
            "The operation must leave at least one active account manager.",
        ) from exc
    if isinstance(exc, OrganizationRelationshipConflict):
        raise APIError(
            409,
            "organization_relationship_conflict",
            str(exc),
        ) from exc
    if isinstance(exc, AvailabilityRelationshipConflict):
        raise APIError(
            409,
            "availability_relationship_conflict",
            str(exc),
        ) from exc
    if isinstance(exc, AppointmentRelationshipConflict):
        raise APIError(
            409,
            "appointment_relationship_conflict",
            str(exc),
        ) from exc
    if isinstance(exc, StudentLifecycleConflict):
        raise APIError(409, "student_lifecycle_conflict", str(exc)) from exc
    if isinstance(exc, SelfTargetForbidden):
        raise APIError(
            403,
            "self_target_forbidden",
            "This administrative operation cannot target the acting administrator.",
        ) from exc
    if isinstance(exc, ManagementNotAuthorized):
        raise APIError(
            403, "permission_denied", "The accounts.manage capability is required."
        ) from exc
    if isinstance(exc, ManagementConfigurationError):
        raise APIError(
            503,
            "identity_policy_unavailable",
            "The canonical identity policy is temporarily unavailable.",
        ) from exc
    if isinstance(exc, (InvalidManagementInput, PaginationError)):
        raise APIError(422, "invalid_account_request", str(exc)) from exc
    raise APIError(
        500, "internal_error", "The account-management operation could not be completed."
    ) from exc


def _detail(user_id) -> dict[str, object]:
    return serialize_account(get_account(user_id=user_id, detail=True), detail=True)


def _context(request) -> AuditContext:
    return AuditContext.from_request(request, actor=request.auth_user)


def _csv_report(report: CsvImportReport) -> dict[str, object]:
    return {
        "valid": report.valid,
        "committed": report.committed,
        "total_rows": report.total_rows,
        "create_count": report.create_count,
        "skip_count": report.skip_count,
        "conflict_count": report.conflict_count,
        "invalid_count": report.invalid_count,
        "rows": [
            {
                "row_number": row.row_number,
                "institutional_id": row.institutional_id,
                "email": row.email,
                "action": row.action,
                "message": row.message,
            }
            for row in report.rows
        ],
    }


def _csv_issue_details(exc: CsvImportInvalidRows) -> list[dict[str, object]]:
    return [
        {
            "row_number": issue.row_number,
            "institutional_id": issue.institutional_id,
            "email": issue.email,
            "message": issue.message,
        }
        for issue in exc.issues
    ]


@router.get(
    "",
    response=response_with_errors(AccountListResponse, 401, 403, 422),
    auth=session_auth,
    operation_id="accountsList",
    summary="List managed accounts",
)
def accounts(
    request,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    role: RoleCode | None = None,
    is_active: bool | None = None,
    designation: DesignationCode | None = None,
    email_verified: bool | None = None,
    search: str | None = None,
):
    _require_management(request, recent_mfa=False)
    try:
        result = list_accounts(
            page=page,
            page_size=page_size,
            role=role.value if role is not None else None,
            is_active=is_active,
            designation=designation.value if designation is not None else None,
            email_verified=email_verified,
            search=search,
        )
    except AccountManagementError as exc:
        _raise_management_error(exc)
    return {
        "items": [serialize_account(user) for user in result.items],
        "page": result.page,
        "page_size": result.page_size,
        "has_next": result.has_next,
    }


@router.post(
    "/imports/csv",
    response=response_with_errors(CsvImportResponse, 401, 403, 409, 422, 503),
    auth=session_auth,
    operation_id="accountsImportCsv",
    summary="Validate or commit a bounded CSV account import",
)
def account_csv_import(
    request,
    file: File[UploadedFile],
    dry_run: bool = True,
):
    _require_management(request, recent_mfa=True)
    data = file.read(MAX_CSV_BYTES + 1)
    try:
        report = provision_accounts_from_csv(
            actor=request.auth_user,
            actor_session=request.auth_session,
            context=_context(request),
            data=data,
            dry_run=dry_run,
        )
    except RecentMFARequired as exc:
        raise APIError(403, "recent_mfa_required", "Recent MFA is required.") from exc
    except CsvImportTooLarge as exc:
        raise APIError(422, "csv_import_too_large", str(exc)) from exc
    except CsvImportUnsupportedHeaders as exc:
        raise APIError(422, "csv_import_unsupported_headers", str(exc)) from exc
    except CsvImportMalformed as exc:
        raise APIError(422, "csv_import_malformed", str(exc)) from exc
    except CsvImportDuplicateIdentity as exc:
        raise APIError(
            422,
            "csv_import_duplicate_identity",
            str(exc),
            details=_csv_issue_details(exc),
        ) from exc
    except CsvImportInvalidRows as exc:
        raise APIError(
            422,
            "csv_import_invalid_rows",
            str(exc),
            details=_csv_issue_details(exc),
        ) from exc
    except CsvImportConflict as exc:
        raise APIError(
            409,
            "csv_import_conflict",
            str(exc),
            details=[
                {
                    "row_number": row.row_number,
                    "email": row.email,
                    "message": row.message,
                }
                for row in exc.rows
            ],
        ) from exc
    except AccountManagementError as exc:
        _raise_management_error(exc)
    return _csv_report(report)


@router.post(
    "",
    response=response_with_errors(
        AccountDetailResponse,
        401,
        403,
        409,
        422,
        503,
        success_status=201,
    ),
    auth=session_auth,
    operation_id="accountsCreate",
    summary="Create a managed account",
)
def account_create(request, payload: AccountCreateRequest):
    _require_management(request, recent_mfa=True)
    try:
        user = create_account(
            actor=request.auth_user,
            actor_session=request.auth_session,
            context=_context(request),
            institutional_id=payload.institutional_id,
            email=payload.email,
            first_name=payload.first_name,
            middle_name=payload.middle_name,
            last_name=payload.last_name,
            suffix=payload.suffix,
            role=payload.role.value,
            is_active=payload.is_active,
        )
    except RecentMFARequired as exc:
        raise APIError(403, "recent_mfa_required", "Recent MFA is required.") from exc
    except AccountManagementError as exc:
        _raise_management_error(exc)
    return Status(201, _detail(user.pk))


@router.patch(
    "/{user_id}/identity",
    response=response_with_errors(AccountDetailResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="accountsUpdateIdentity",
    summary="Update managed account identity",
)
def account_identity(request, user_id: UUID, payload: IdentityUpdateRequest):
    _require_management(request, recent_mfa=True)
    try:
        update_identity(
            actor=request.auth_user,
            actor_session=request.auth_session,
            target_id=user_id,
            context=_context(request),
            changes=payload.model_dump(exclude_unset=True),
        )
    except RecentMFARequired as exc:
        raise APIError(403, "recent_mfa_required", "Recent MFA is required.") from exc
    except AccountManagementError as exc:
        _raise_management_error(exc)
    return _detail(user_id)


@router.post(
    "/{user_id}/email-change",
    response=response_with_errors(
        ManagedEmailChangeResponse,
        401,
        403,
        404,
        409,
        422,
        429,
        503,
    ),
    auth=session_auth,
    operation_id="accountsRequestEmailChange",
    summary="Stage a managed account email change",
)
def account_email_change(request, user_id: UUID, payload: ManagedEmailChangeRequest):
    _require_management(request, recent_mfa=True)
    try:
        pending = request_administrative_email_change(
            actor=request.auth_user,
            actor_session=request.auth_session,
            target_id=user_id,
            new_email=payload.new_email,
            context=_context(request),
            request=request,
            turnstile_token=payload.turnstile_token,
        )
    except RecentMFARequired as exc:
        raise APIError(403, "recent_mfa_required", "Recent MFA is required.") from exc
    except AuthenticationRateLimited as exc:
        raise APIError(
            429,
            "rate_limited",
            "Too many authentication attempts. Please try again later.",
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc
    except EmailOTPSecurityUnavailable as exc:
        raise APIError(
            503,
            "security_unavailable",
            "Authentication is temporarily unavailable.",
        ) from exc
    except EmailChangePermissionDenied as exc:
        raise APIError(403, "permission_denied", "The accounts.manage capability is required.") from exc
    except EmailChangeNotFound as exc:
        raise APIError(404, "account_not_found", "The requested account was not found.") from exc
    except EmailChangeConflict as exc:
        raise APIError(409, "email_change_conflict", str(exc)) from exc
    except (EmailChangeInvalid, EmailOTPInvalid) as exc:
        raise APIError(
            422,
            "invalid_email_change_request",
            "The email change request could not be staged.",
        ) from exc
    except EmailChangeError as exc:
        raise APIError(
            500,
            "internal_error",
            "The email change operation could not be completed.",
        ) from exc
    return {
        "request_id": pending.request_id,
        "challenge_id": pending.challenge_id,
        "expires_at": pending.expires_at,
    }


@router.post(
    "/{user_id}/disable",
    response=response_with_errors(AccountDetailResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="accountsDisable",
    summary="Disable a managed account",
)
def account_disable(request, user_id: UUID):
    _require_management(request, recent_mfa=True)
    try:
        set_account_active(
            actor=request.auth_user,
            actor_session=request.auth_session,
            target_id=user_id,
            context=_context(request),
            is_active=False,
        )
    except RecentMFARequired as exc:
        raise APIError(403, "recent_mfa_required", "Recent MFA is required.") from exc
    except AccountManagementError as exc:
        _raise_management_error(exc)
    return _detail(user_id)


@router.post(
    "/{user_id}/enable",
    response=response_with_errors(AccountDetailResponse, 401, 403, 404, 422),
    auth=session_auth,
    operation_id="accountsEnable",
    summary="Enable a managed account",
)
def account_enable(request, user_id: UUID):
    _require_management(request, recent_mfa=True)
    try:
        set_account_active(
            actor=request.auth_user,
            actor_session=request.auth_session,
            target_id=user_id,
            context=_context(request),
            is_active=True,
        )
    except RecentMFARequired as exc:
        raise APIError(403, "recent_mfa_required", "Recent MFA is required.") from exc
    except AccountManagementError as exc:
        _raise_management_error(exc)
    return _detail(user_id)


@router.put(
    "/{user_id}/role",
    response=response_with_errors(AccountDetailResponse, 401, 403, 404, 409, 422, 503),
    auth=session_auth,
    operation_id="accountsChangeRole",
    summary="Change a managed account role",
)
def account_role(request, user_id: UUID, payload: RoleUpdateRequest):
    _require_management(request, recent_mfa=True)
    try:
        change_role(
            actor=request.auth_user,
            actor_session=request.auth_session,
            target_id=user_id,
            context=_context(request),
            role=payload.role.value,
        )
    except RecentMFARequired as exc:
        raise APIError(403, "recent_mfa_required", "Recent MFA is required.") from exc
    except AccountManagementError as exc:
        _raise_management_error(exc)
    return _detail(user_id)


@router.put(
    "/{user_id}/student-lifecycle",
    response=response_with_errors(AccountDetailResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="accountsUpdateStudentLifecycle",
    summary="Update managed Student lifecycle",
)
def account_student_lifecycle(
    request,
    user_id: UUID,
    payload: StudentLifecycleUpdateRequest,
):
    _require_management(request, recent_mfa=True)
    try:
        set_student_lifecycle(
            actor=request.auth_user,
            actor_session=request.auth_session,
            target_id=user_id,
            context=_context(request),
            status=payload.status.value,
        )
    except RecentMFARequired as exc:
        raise APIError(403, "recent_mfa_required", "Recent MFA is required.") from exc
    except AccountManagementError as exc:
        _raise_management_error(exc)
    return _detail(user_id)


@router.get(
    "/{user_id}/designations",
    response=response_with_errors(DesignationListResponse, 401, 403, 404, 422),
    auth=session_auth,
    operation_id="accountsListDesignations",
    summary="List managed account designations",
)
def account_designations(request, user_id: UUID):
    _require_management(request, recent_mfa=False)
    try:
        designations = list_designations(user_id=user_id)
    except AccountManagementError as exc:
        _raise_management_error(exc)
    return {"designations": designations}


@router.post(
    "/{user_id}/designations/{designation_code}",
    response=response_with_errors(AccountDetailResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="accountsAssignDesignation",
    summary="Assign a managed account designation",
)
def account_designation_assign(request, user_id: UUID, designation_code: DesignationCode):
    _require_designation_management(request)
    try:
        assign_designation(
            actor=request.auth_user,
            actor_session=request.auth_session,
            target_id=user_id,
            context=_context(request),
            designation=designation_code.value,
        )
    except RecentMFARequired as exc:
        raise APIError(403, "recent_mfa_required", "Recent MFA is required.") from exc
    except AccountManagementError as exc:
        _raise_management_error(exc)
    return _detail(user_id)


@router.delete(
    "/{user_id}/designations/{designation_code}",
    response=response_with_errors(AccountDetailResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="accountsRemoveDesignation",
    summary="Remove a managed account designation",
)
def account_designation_remove(request, user_id: UUID, designation_code: DesignationCode):
    _require_designation_management(request)
    try:
        remove_designation(
            actor=request.auth_user,
            actor_session=request.auth_session,
            target_id=user_id,
            context=_context(request),
            designation=designation_code.value,
        )
    except RecentMFARequired as exc:
        raise APIError(403, "recent_mfa_required", "Recent MFA is required.") from exc
    except AccountManagementError as exc:
        _raise_management_error(exc)
    return _detail(user_id)


@router.get(
    "/{user_id}/capability-overrides",
    response=response_with_errors(CapabilityOverrideListResponse, 401, 403, 404, 422),
    auth=session_auth,
    operation_id="accountsListCapabilityOverrides",
    summary="List managed account capability overrides",
)
def account_capability_overrides(request, user_id: UUID):
    _require_management(request, recent_mfa=False)
    try:
        overrides = list_capability_overrides(user_id=user_id)
    except AccountManagementError as exc:
        _raise_management_error(exc)
    return {"overrides": overrides}


@router.put(
    "/{user_id}/capability-overrides/{capability_code}",
    response=response_with_errors(CapabilityOverrideResponse, 401, 403, 404, 409, 422, 503),
    auth=session_auth,
    operation_id="accountsSetCapabilityOverride",
    summary="Set a managed account capability override",
)
def account_capability_override_set(
    request,
    user_id: UUID,
    capability_code: CapabilityCode,
    payload: CapabilityOverrideCreateRequest,
):
    _require_management(request, recent_mfa=True)
    try:
        result = set_capability_override(
            actor=request.auth_user,
            actor_session=request.auth_session,
            target_id=user_id,
            context=_context(request),
            capability=capability_code.value,
            effect=payload.effect,
            reason=payload.reason,
            expires_at=payload.expires_at,
        )
    except RecentMFARequired as exc:
        raise APIError(403, "recent_mfa_required", "Recent MFA is required.") from exc
    except AccountManagementError as exc:
        _raise_management_error(exc)
    assert result.override is not None
    return {
        "capability": result.override.capability.code,
        "effect": result.override.effect,
        "reason": result.override.reason,
        "expires_at": result.override.expires_at,
        "created_at": result.override.created_at,
        "created_by": {
            "id": result.override.created_by.pk,
            "email": result.override.created_by.email,
            "full_name": result.override.created_by.get_full_name(),
        }
        if result.override.created_by is not None
        else None,
    }


@router.delete(
    "/{user_id}/capability-overrides/{capability_code}",
    response=response_with_errors(OverrideRemovalResponse, 401, 403, 404, 409, 422),
    auth=session_auth,
    operation_id="accountsRemoveCapabilityOverride",
    summary="Remove a managed account capability override",
)
def account_capability_override_remove(request, user_id: UUID, capability_code: CapabilityCode):
    _require_management(request, recent_mfa=True)
    try:
        result = remove_capability_override(
            actor=request.auth_user,
            actor_session=request.auth_session,
            target_id=user_id,
            context=_context(request),
            capability=capability_code.value,
        )
    except RecentMFARequired as exc:
        raise APIError(403, "recent_mfa_required", "Recent MFA is required.") from exc
    except AccountManagementError as exc:
        _raise_management_error(exc)
    return {"removed": result.changed}


@router.post(
    "/{user_id}/security/revoke-sessions",
    response=response_with_errors(RevocationResponse, 401, 403, 404, 422),
    auth=session_auth,
    operation_id="accountsRevokeSessions",
    summary="Revoke all authentication sessions for a managed account",
)
def account_revoke_sessions(request, user_id: UUID):
    _require_management(request, recent_mfa=True)
    try:
        result = revoke_account_sessions(
            actor=request.auth_user,
            actor_session=request.auth_session,
            target_id=user_id,
            context=_context(request),
        )
    except RecentMFARequired as exc:
        raise APIError(403, "recent_mfa_required", "Recent MFA is required.") from exc
    except AccountManagementError as exc:
        _raise_management_error(exc)
    return {"revoked_count": result.revoked_count}


@router.post(
    "/{user_id}/security/revoke-trusted-sessions",
    response=response_with_errors(RevocationResponse, 401, 403, 404, 422),
    auth=session_auth,
    operation_id="accountsRevokeTrustedSessions",
    summary="Revoke all trusted sessions for a managed account",
)
def account_revoke_trusted_sessions(request, user_id: UUID):
    _require_management(request, recent_mfa=True)
    try:
        result = revoke_account_trusted_sessions(
            actor=request.auth_user,
            actor_session=request.auth_session,
            target_id=user_id,
            context=_context(request),
        )
    except RecentMFARequired as exc:
        raise APIError(403, "recent_mfa_required", "Recent MFA is required.") from exc
    except AccountManagementError as exc:
        _raise_management_error(exc)
    return {"revoked_count": result.revoked_count}


@router.post(
    "/{user_id}/security/reset-mfa",
    response=response_with_errors(MFAResetResponse, 401, 403, 404, 422),
    auth=session_auth,
    operation_id="accountsResetMfa",
    summary="Reset MFA for a managed account",
)
def account_reset_mfa(request, user_id: UUID):
    _require_management(request, recent_mfa=True)
    try:
        result = reset_account_mfa(
            actor=request.auth_user,
            actor_session=request.auth_session,
            target_id=user_id,
            context=_context(request),
        )
    except RecentMFARequired as exc:
        raise APIError(403, "recent_mfa_required", "Recent MFA is required.") from exc
    except AccountManagementError as exc:
        _raise_management_error(exc)
    return {
        "reset": result.reset,
        "revoked_session_count": result.invalidation.revoked_session_count,
        "revoked_trusted_session_count": result.invalidation.revoked_trusted_session_count,
    }


@router.get(
    "/{user_id}",
    response=response_with_errors(AccountDetailResponse, 401, 403, 404, 422),
    auth=session_auth,
    operation_id="accountsGet",
    summary="Inspect a managed account",
)
def account_detail(request, user_id: UUID):
    _require_management(request, recent_mfa=False)
    try:
        return _detail(user_id)
    except AccountManagementError as exc:
        _raise_management_error(exc)


__all__ = [
    "AccountCreateRequest",
    "AccountDetailResponse",
    "AccountListResponse",
    "AccountSummaryResponse",
    "router",
]
