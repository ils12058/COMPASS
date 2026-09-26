"""Transactional services for COMPASS administrative account management."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from compass.accounts.models import (
    Capability,
    Designation,
    Role,
    StudentLifecycleStatus,
    User,
    UserCapabilityOverride,
    UserDesignation,
)
from compass.accounts.policy import (
    CAPABILITY_CODES,
    CAPABILITY_DEFINITIONS,
    DESIGNATION_CAPABILITY_GRANTS,
    DESIGNATION_CODES,
    ROLE_CAPABILITY_GRANTS,
    ROLE_CODES,
    designation_role_compatible,
)
from compass.accounts.services import (
    effective_capabilities,
    set_user_capability_override,
    user_has_capability,
)
from compass.audit.actions import (
    ACCOUNT_CAPABILITY_OVERRIDE_REMOVED,
    ACCOUNT_CAPABILITY_OVERRIDE_SET,
    ACCOUNT_CREATED,
    ACCOUNT_DESIGNATION_ASSIGNED,
    ACCOUNT_DESIGNATION_REMOVED,
    ACCOUNT_DISABLED,
    ACCOUNT_ENABLED,
    ACCOUNT_INSTITUTIONAL_ID_CHANGED,
    ACCOUNT_MFA_RESET,
    ACCOUNT_ROLE_CHANGED,
    ACCOUNT_STUDENT_LIFECYCLE_CHANGED,
    ACCOUNT_UPDATED,
)
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.authentication.mfa import MFAResetResult, has_active_totp_factor, reset_totp_state
from compass.authentication.security import (
    AuthStateInvalidation,
    invalidate_auth_state_after_authority_change,
)
from compass.authentication.sessions import (
    RecentMFARequired,
    require_recent_mfa,
    revoke_all_auth_sessions,
    revoke_all_trusted_sessions,
)
from compass.notifications.policy import NotificationEvent
from compass.notifications.services import create_notification_for_event

ACCOUNT_MANAGE_CAPABILITY = "accounts.manage"
INSTITUTIONAL_DESIGNATION_MANAGE_CAPABILITY = "institutional_designations.manage"
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50
MAX_PAGE_NUMBER = 100_000


def _create_account_security_notification(
    *,
    target: User,
    audit_event,
    event: NotificationEvent,
) -> None:
    create_notification_for_event(
        recipient=target,
        event=event,
        source_type="audit_event",
        source_id=audit_event.pk,
        target_type="ACCOUNT_SECURITY",
        target_id=target.pk,
    )


class AccountManagementError(RuntimeError):
    """Base class for expected administrative account-management failures."""


class ManagementNotAuthorized(AccountManagementError):
    """The actor does not currently have effective account-management authority."""


class DesignationManagementNotAuthorized(ManagementNotAuthorized):
    """The actor lacks the dedicated authority to record institutional designations."""


class AccountNotFound(AccountManagementError):
    """The requested account does not exist."""


class DuplicateEmail(AccountManagementError):
    """The requested email is already assigned to another account."""


class DuplicateInstitutionalId(AccountManagementError):
    """The requested Institutional ID is already assigned to another account."""


class InvalidManagementInput(AccountManagementError):
    """The request asks for a noncanonical or otherwise invalid management state."""


class StudentLifecycleConflict(AccountManagementError):
    """The requested Student lifecycle mutation is not valid for the target account."""


class ManagementConfigurationError(AccountManagementError):
    """Canonical identity policy has not been synchronized into the database."""


class LastAccountManagerError(AccountManagementError):
    """The mutation would leave no active account with accounts.manage."""


class SelfTargetForbidden(AccountManagementError):
    """The requested administrative target is the actor and is unsafe for this operation."""


class PaginationError(AccountManagementError):
    """The requested account page is outside the supported bounds."""


class OrganizationRelationshipConflict(AccountManagementError):
    """The role change would invalidate an Organization relationship."""


class AvailabilityRelationshipConflict(AccountManagementError):
    """The role change would strand provider-specific Availability configuration."""


class AppointmentRelationshipConflict(AccountManagementError):
    """The role change would strand an active or future Appointment reservation."""


class DesignationRoleConflict(AccountManagementError):
    """The requested role/designation combination is incompatible with canonical policy."""


@dataclass(frozen=True, slots=True)
class AccountPage:
    items: tuple[User, ...]
    page: int
    page_size: int
    has_next: bool


@dataclass(frozen=True, slots=True)
class MutationResult:
    user: User
    changed: bool


@dataclass(frozen=True, slots=True)
class OverrideMutationResult:
    override: UserCapabilityOverride | None
    changed: bool


@dataclass(frozen=True, slots=True)
class MFAResetMutationResult:
    reset: bool
    mfa: MFAResetResult
    invalidation: AuthStateInvalidation


@dataclass(frozen=True, slots=True)
class SecurityRevocationResult:
    revoked_count: int


def _validate_pagination(*, page: int, page_size: int) -> tuple[int, int]:
    if type(page) is not int or page < 1 or page > MAX_PAGE_NUMBER:
        raise PaginationError(f"page must be an integer between 1 and {MAX_PAGE_NUMBER}")
    if type(page_size) is not int or page_size < 1 or page_size > MAX_PAGE_SIZE:
        raise PaginationError(f"page_size must be an integer between 1 and {MAX_PAGE_SIZE}")
    return page, page_size


def _canonical_code(value: str, *, allowed: frozenset[str], label: str) -> str:
    if not isinstance(value, str):
        raise InvalidManagementInput(f"{label} must be a canonical code")
    normalized = value.strip()
    if normalized not in allowed:
        raise InvalidManagementInput(f"unknown {label}: {normalized}")
    return normalized


def _canonical_role_code(value: str) -> str:
    return _canonical_code(value, allowed=ROLE_CODES, label="role")


def _canonical_designation_code(value: str) -> str:
    return _canonical_code(value, allowed=DESIGNATION_CODES, label="designation")


def _canonical_capability_code(value: str) -> str:
    return _canonical_code(value, allowed=CAPABILITY_CODES, label="capability")


def _clean_identity_text(
    field_name: str,
    value: str | None,
    *,
    required: bool = False,
    allow_none: bool = False,
) -> str:
    if value is None:
        if allow_none:
            return ""
        raise InvalidManagementInput(f"{field_name} is required")
    if not isinstance(value, str):
        raise InvalidManagementInput(f"{field_name} must be a string")
    normalized = value.strip()
    if required and not normalized:
        raise InvalidManagementInput(f"{field_name} is required")
    try:
        User._meta.get_field(field_name).clean(normalized, None)
    except ValidationError as exc:
        raise InvalidManagementInput(f"{field_name} is invalid") from exc
    return normalized


def _clean_email(value: str) -> str:
    try:
        return User.objects.clean_email(value)
    except (TypeError, ValueError) as exc:
        raise InvalidManagementInput("a valid email address is required") from exc


def _clean_institutional_id(value: str | None, *, required: bool = True) -> str | None:
    try:
        normalized = User.objects.normalize_institutional_id(value)
    except (TypeError, ValueError) as exc:
        raise InvalidManagementInput("institutional_id is invalid") from exc
    if required and normalized is None:
        raise InvalidManagementInput("institutional_id is required")
    if normalized is not None:
        try:
            User._meta.get_field("institutional_id").clean(normalized, None)
        except ValidationError as exc:
            raise InvalidManagementInput("institutional_id is invalid") from exc
    return normalized


def _clean_expiry(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if timezone.is_naive(value):
        value = timezone.make_aware(value, timezone.get_current_timezone())
    if value <= timezone.now():
        raise InvalidManagementInput("expires_at must be in the future")
    return value


def _lock_management_mutex() -> None:
    """Serialize account mutations that can change effective manager authority."""

    try:
        Capability.objects.select_for_update().get(code=ACCOUNT_MANAGE_CAPABILITY)
    except Capability.DoesNotExist as exc:
        raise ManagementConfigurationError(
            "accounts.manage capability is not synchronized; run sync_identity_policy first"
        ) from exc
    # Keeping this as one small canonical policy-row lock serializes manager-count checks without
    # introducing a distributed lock.


def _lock_users(*, actor_id, target_id=None) -> tuple[User, User | None]:
    if not actor_id:
        raise ManagementNotAuthorized("a saved administrative actor is required")
    ids = {actor_id}
    if target_id is not None:
        ids.add(target_id)
    locked = (
        User.objects.select_for_update(of=("self",))
        .select_related("role")
        .filter(pk__in=ids)
        .order_by("id")
    )
    users = {user.pk: user for user in locked}
    actor = users.get(actor_id)
    if actor is None:
        raise ManagementNotAuthorized("the administrative actor is unavailable")
    target = users.get(target_id) if target_id is not None else None
    if target_id is not None and target is None:
        raise AccountNotFound("the requested account was not found")
    return actor, target


def _assert_manager(actor: User) -> None:
    if not actor.is_active or not user_has_capability(actor, ACCOUNT_MANAGE_CAPABILITY):
        raise ManagementNotAuthorized("accounts.manage is required")


def _assert_designation_manager(actor: User) -> None:
    if not user_has_capability(actor, INSTITUTIONAL_DESIGNATION_MANAGE_CAPABILITY):
        raise DesignationManagementNotAuthorized(
            "accounts.manage and institutional_designations.manage are required"
        )


def _assert_user_designations_compatible(*, user_id, role_code: str) -> None:
    designation_codes = tuple(
        UserDesignation.objects.filter(user_id=user_id)
        .select_related("designation")
        .values_list("designation__code", flat=True)
    )
    incompatible = tuple(
        code
        for code in designation_codes
        if not designation_role_compatible(
            designation_code=code,
            role_code=role_code,
        )
    )
    if incompatible:
        joined = ", ".join(sorted(incompatible))
        raise DesignationRoleConflict(
            f"role {role_code} is incompatible with existing designation(s): {joined}"
        )


def _assert_recent_mfa(*, actor: User, actor_session) -> None:
    if getattr(actor_session, "user_id", None) != actor.pk:
        raise ManagementNotAuthorized("the step-up session does not belong to the actor")
    try:
        require_recent_mfa(actor_session)
    except RecentMFARequired:
        raise


@contextmanager
def _admin_mutation(*, actor: User, actor_session, target_id=None, authority_change: bool = False):
    with transaction.atomic():
        if authority_change:
            _lock_management_mutex()
        locked_actor, locked_target = _lock_users(actor_id=actor.pk, target_id=target_id)
        _assert_manager(locked_actor)
        _assert_recent_mfa(actor=locked_actor, actor_session=actor_session)
        yield locked_actor, locked_target


def _active_manager_candidates():
    """Accounts that could hold accounts.manage through a role, designation, or grant override.

    Only these accounts need the exact effective-capability check; scanning every active account
    (thousands of Students) is unnecessary because none of them can hold the capability otherwise.
    """

    return (
        User.objects.filter(is_active=True)
        .filter(
            Q(role__capability_grants__capability__code=ACCOUNT_MANAGE_CAPABILITY)
            | Q(
                designation_assignments__designation__capability_grants__capability__code=(
                    ACCOUNT_MANAGE_CAPABILITY
                )
            )
            | Q(
                capability_overrides__capability__code=ACCOUNT_MANAGE_CAPABILITY,
                capability_overrides__effect=UserCapabilityOverride.Effect.GRANT,
            )
        )
        .distinct()
        .select_related("role")
        .order_by("id")
    )


def _active_manager_exists() -> bool:
    return any(
        user_has_capability(candidate, ACCOUNT_MANAGE_CAPABILITY)
        for candidate in _active_manager_candidates()
    )


def _ensure_active_manager_remains() -> None:
    if not _active_manager_exists():
        raise LastAccountManagerError(
            "the operation would leave no active account with accounts.manage"
        )


def _account_designation_codes(user: User) -> list[str]:
    return [designation.code for designation in user.designations.all()]


def serialize_account(user: User, *, detail: bool = False) -> dict[str, object]:
    """Return an allowlisted account representation with no credential-bearing fields."""

    payload: dict[str, object] = {
        "id": user.pk,
        "institutional_id": user.institutional_id,
        "email": user.email,
        "first_name": user.first_name,
        "middle_name": user.middle_name,
        "last_name": user.last_name,
        "suffix": user.suffix,
        "full_name": user.get_full_name(),
        "role": user.role.code,
        "student_lifecycle_status": user.student_lifecycle_status,
        "designations": _account_designation_codes(user),
        "is_active": user.is_active,
        "password_configured": user.has_usable_password(),
        "email_verified": user.email_verified_at is not None,
        "created_at": user.created_at,
    }
    if detail:
        payload.update(
            {
                "updated_at": user.updated_at,
                "email_verified_at": user.email_verified_at,
                "mfa_enabled": has_active_totp_factor(user.pk),
            }
        )
    return payload


def get_account(*, user_id, detail: bool = False) -> User:
    user = (
        User.objects.select_related("role")
        .prefetch_related("designations")
        .filter(pk=user_id)
        .first()
    )
    if user is None:
        raise AccountNotFound("the requested account was not found")
    return user


def list_accounts(
    *,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    role: str | None = None,
    is_active: bool | None = None,
    designation: str | None = None,
    email_verified: bool | None = None,
    search: str | None = None,
) -> AccountPage:
    page, page_size = _validate_pagination(page=page, page_size=page_size)
    queryset = (
        User.objects.select_related("role")
        .prefetch_related("designations")
        .order_by("-created_at", "-id")
    )
    if role is not None:
        queryset = queryset.filter(role__code=_canonical_role_code(role))
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)
    if designation is not None:
        queryset = queryset.filter(
            designations__code=_canonical_designation_code(designation)
        ).distinct()
    if email_verified is not None:
        queryset = queryset.filter(email_verified_at__isnull=not email_verified)
    if search is not None:
        if not isinstance(search, str):
            raise InvalidManagementInput("search must be a string")
        normalized_search = search.strip()
        if len(normalized_search) > 254:
            raise InvalidManagementInput("search is too long")
        if normalized_search:
            search_filter = (
                Q(institutional_id__icontains=normalized_search)
                | Q(email__icontains=normalized_search)
                | Q(first_name__icontains=normalized_search)
                | Q(middle_name__icontains=normalized_search)
                | Q(last_name__icontains=normalized_search)
            )
            queryset = queryset.filter(search_filter)

    offset = (page - 1) * page_size
    records = list(queryset[offset : offset + page_size + 1])
    has_next = len(records) > page_size
    return AccountPage(
        items=tuple(records[:page_size]),
        page=page,
        page_size=page_size,
        has_next=has_next,
    )


def list_designations(*, user_id) -> list[str]:
    user = get_account(user_id=user_id)
    return list(user.designations.order_by("code").values_list("code", flat=True))


def _override_payload(override: UserCapabilityOverride) -> dict[str, object]:
    creator = override.created_by
    return {
        "capability": override.capability.code,
        "effect": override.effect,
        "reason": override.reason,
        "expires_at": override.expires_at,
        "created_at": override.created_at,
        "created_by": (
            {
                "id": creator.pk,
                "email": creator.email,
                "full_name": creator.get_full_name(),
            }
            if creator is not None
            else None
        ),
    }


def list_capability_overrides(*, user_id) -> list[dict[str, object]]:
    get_account(user_id=user_id)
    overrides = UserCapabilityOverride.objects.filter(user_id=user_id).select_related(
        "capability", "created_by"
    )
    return [_override_payload(override) for override in overrides.order_by("capability__code")]


def inspect_account_access(
    *,
    user_id,
    at: datetime | None = None,
) -> dict[str, object]:
    """Explain one managed account's current scope-free effective access.

    Final effective truth comes only from effective_capabilities. Canonical Role and
    Designation grant maps are used solely to explain baseline provenance.
    """

    user = get_account(user_id=user_id)
    now = at if at is not None else timezone.now()
    effective = effective_capabilities(user, at=now)
    designation_codes = sorted(
        code for code in _account_designation_codes(user) if code in DESIGNATION_CODES
    )
    overrides = {
        override.capability.code: override
        for override in UserCapabilityOverride.objects.filter(
            user_id=user.pk,
            capability__code__in=CAPABILITY_CODES,
        )
        .select_related("capability", "created_by")
        .order_by("capability__code")
    }

    capability_rows: list[dict[str, object]] = []
    role_grants = ROLE_CAPABILITY_GRANTS.get(user.role.code, frozenset())
    for definition in sorted(CAPABILITY_DEFINITIONS, key=lambda item: item.code):
        sources: list[dict[str, str]] = []
        if definition.code in role_grants:
            sources.append({"type": "ROLE", "code": user.role.code})
        for designation_code in designation_codes:
            if definition.code in DESIGNATION_CAPABILITY_GRANTS.get(
                designation_code,
                frozenset(),
            ):
                sources.append({"type": "DESIGNATION", "code": designation_code})

        override = overrides.get(definition.code)
        override_payload = None
        if override is not None:
            override_payload = {
                **_override_payload(override),
                "active": override.expires_at is None or override.expires_at > now,
            }
            override_payload.pop("capability", None)

        capability_rows.append(
            {
                "code": definition.code,
                "name": definition.name,
                "description": definition.description,
                "effective": definition.code in effective,
                "baseline_sources": sources,
                "override": override_payload,
            }
        )

    return {
        "account": {
            "id": user.pk,
            "email": user.email,
            "full_name": user.get_full_name(),
            "is_active": user.is_active,
        },
        "role": user.role.code,
        "designations": designation_codes,
        "effective_capabilities": sorted(effective),
        "capabilities": capability_rows,
    }


def create_account(
    *,
    actor: User,
    actor_session,
    context: AuditContext,
    institutional_id: str,
    email: str,
    first_name: str,
    last_name: str,
    role: str,
    middle_name: str = "",
    suffix: str = "",
    is_active: bool = True,
) -> User:
    cleaned_institutional_id = _clean_institutional_id(institutional_id)
    cleaned_email = _clean_email(email)
    cleaned_first_name = _clean_identity_text("first_name", first_name, required=True)
    cleaned_last_name = _clean_identity_text("last_name", last_name, required=True)
    cleaned_middle_name = _clean_identity_text("middle_name", middle_name, allow_none=True)
    cleaned_suffix = _clean_identity_text("suffix", suffix, allow_none=True)
    role_code = _canonical_role_code(role)

    with transaction.atomic():
        _lock_management_mutex()
        locked_actor, _ = _lock_users(actor_id=actor.pk)
        _assert_manager(locked_actor)
        _assert_recent_mfa(actor=locked_actor, actor_session=actor_session)
        role_record = Role.objects.filter(code=role_code).first()
        if role_record is None:
            raise ManagementConfigurationError(
                "the requested canonical role is not synchronized; run sync_identity_policy first"
            )
        if User.objects.filter(email__iexact=cleaned_email).exists():
            raise DuplicateEmail("an account with this email already exists")
        if User.objects.filter(institutional_id__iexact=cleaned_institutional_id).exists():
            raise DuplicateInstitutionalId("an account with this institutional_id already exists")
        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    email=cleaned_email,
                    institutional_id=cleaned_institutional_id,
                    password=None,
                    role=role_record,
                    first_name=cleaned_first_name,
                    middle_name=cleaned_middle_name,
                    last_name=cleaned_last_name,
                    suffix=cleaned_suffix,
                    is_active=is_active,
                )
        except IntegrityError as exc:
            if User.objects.filter(institutional_id__iexact=cleaned_institutional_id).exists():
                raise DuplicateInstitutionalId(
                    "an account with this institutional_id already exists"
                ) from exc
            if User.objects.filter(email__iexact=cleaned_email).exists():
                raise DuplicateEmail("an account with this email already exists") from exc
            raise
        record_event(
            context=context,
            action=ACCOUNT_CREATED,
            outcome=AuditOutcome.SUCCESS,
            target_type="accounts.user",
            target_id=user.pk,
            metadata={"role": role_code},
        )
    return user


def update_identity(
    *,
    actor: User,
    actor_session,
    target_id,
    context: AuditContext,
    changes: Mapping[str, object],
) -> MutationResult:
    allowed_fields = ("institutional_id", "first_name", "middle_name", "last_name", "suffix")
    unknown_fields = set(changes) - set(allowed_fields)
    if unknown_fields:
        raise InvalidManagementInput("identity updates contain unsupported fields")
    if not changes:
        raise InvalidManagementInput("at least one identity field is required")

    with _admin_mutation(
        actor=actor,
        actor_session=actor_session,
        target_id=target_id,
        authority_change=False,
    ) as (_locked_actor, target):
        assert target is not None
        normalized: dict[str, object] = {}
        for field_name in allowed_fields:
            if field_name not in changes:
                continue
            value = changes[field_name]
            if field_name == "institutional_id":
                normalized[field_name] = _clean_institutional_id(value)  # type: ignore[arg-type]
            elif field_name in {"first_name", "last_name"}:
                normalized[field_name] = _clean_identity_text(
                    field_name,
                    value,  # type: ignore[arg-type]
                    required=True,
                )
            else:
                normalized[field_name] = _clean_identity_text(
                    field_name,
                    value,  # type: ignore[arg-type]
                    allow_none=True,
                )
        changed_fields = [
            field_name
            for field_name in allowed_fields
            if field_name in normalized and getattr(target, field_name) != normalized[field_name]
        ]
        if not changed_fields:
            return MutationResult(user=target, changed=False)

        for field_name in changed_fields:
            setattr(target, field_name, normalized[field_name])
        update_fields = [*changed_fields, "updated_at"]
        try:
            with transaction.atomic():
                target.save(update_fields=update_fields)
        except IntegrityError as exc:
            if "institutional_id" in changed_fields:
                raise DuplicateInstitutionalId(
                    "an account with this institutional_id already exists"
                ) from exc
            raise

        if "institutional_id" in changed_fields:
            record_event(
                context=context,
                action=ACCOUNT_INSTITUTIONAL_ID_CHANGED,
                outcome=AuditOutcome.SUCCESS,
                target_type="accounts.user",
                target_id=target.pk,
                metadata={"changed_fields": ["institutional_id"]},
            )
        record_event(
            context=context,
            action=ACCOUNT_UPDATED,
            outcome=AuditOutcome.SUCCESS,
            target_type="accounts.user",
            target_id=target.pk,
            metadata={"changed_fields": changed_fields},
        )
        return MutationResult(user=target, changed=True)


def set_account_active(
    *,
    actor: User,
    actor_session,
    target_id,
    context: AuditContext,
    is_active: bool,
) -> MutationResult:
    with _admin_mutation(
        actor=actor,
        actor_session=actor_session,
        target_id=target_id,
        authority_change=True,
    ) as (_locked_actor, target):
        assert target is not None
        if target.pk == actor.pk and not is_active:
            raise SelfTargetForbidden("an administrator cannot disable their own account")
        if target.is_active == is_active:
            if not is_active:
                invalidate_auth_state_after_authority_change(
                    user_id=target.pk,
                    context=context,
                    reason="account_disabled",
                    invalidate_email_security_challenges=True,
                )
            return MutationResult(user=target, changed=False)

        target.is_active = is_active
        target.save(update_fields=["is_active", "updated_at"])
        if not is_active:
            invalidate_auth_state_after_authority_change(
                user_id=target.pk,
                context=context,
                reason="account_disabled",
                invalidate_email_security_challenges=True,
            )
            _ensure_active_manager_remains()
            action = ACCOUNT_DISABLED
        else:
            action = ACCOUNT_ENABLED
        record_event(
            context=context,
            action=action,
            outcome=AuditOutcome.SUCCESS,
            target_type="accounts.user",
            target_id=target.pk,
            metadata={},
        )
        return MutationResult(user=target, changed=True)


def change_role(
    *,
    actor: User,
    actor_session,
    target_id,
    context: AuditContext,
    role: str,
) -> MutationResult:
    role_code = _canonical_role_code(role)
    with _admin_mutation(
        actor=actor,
        actor_session=actor_session,
        target_id=target_id,
        authority_change=True,
    ) as (_locked_actor, target):
        assert target is not None
        role_record = Role.objects.filter(code=role_code).first()
        if role_record is None:
            raise ManagementConfigurationError(
                "the requested canonical role is not synchronized; run sync_identity_policy first"
            )
        if target.role_id == role_record.pk:
            return MutationResult(user=target, changed=False)
        _assert_user_designations_compatible(user_id=target.pk, role_code=role_code)
        from compass.organization.services import (
            OrganizationRoleTransitionConflict,
            validate_role_transition,
        )

        try:
            validate_role_transition(user=target, new_role_code=role_code)
        except OrganizationRoleTransitionConflict as exc:
            raise OrganizationRelationshipConflict(str(exc)) from exc
        from compass.availability.services import (
            AvailabilityRoleTransitionConflict,
        )
        from compass.availability.services import (
            validate_role_transition as validate_availability_role_transition,
        )

        try:
            validate_availability_role_transition(user=target, new_role_code=role_code)
        except AvailabilityRoleTransitionConflict as exc:
            raise AvailabilityRelationshipConflict(str(exc)) from exc

        from compass.appointments.services import (
            AppointmentRoleTransitionConflict,
        )
        from compass.appointments.services import (
            validate_role_transition as validate_appointment_role_transition,
        )

        try:
            validate_appointment_role_transition(user=target, new_role_code=role_code)
        except AppointmentRoleTransitionConflict as exc:
            raise AppointmentRelationshipConflict(str(exc)) from exc

        from_role = target.role.code
        target.role = role_record
        update_fields = ["role", "updated_at"]
        if role_code == "STUDENT" and target.student_lifecycle_status is None:
            target.student_lifecycle_status = StudentLifecycleStatus.CURRENT
            update_fields.append("student_lifecycle_status")
        target.save(update_fields=update_fields)
        if target.pk == actor.pk and not user_has_capability(target, ACCOUNT_MANAGE_CAPABILITY):
            raise SelfTargetForbidden(
                "an administrator cannot remove their own management authority"
            )
        _ensure_active_manager_remains()
        invalidate_auth_state_after_authority_change(
            user_id=target.pk,
            context=context,
            reason="role_changed",
        )
        audit_event = record_event(
            context=context,
            action=ACCOUNT_ROLE_CHANGED,
            outcome=AuditOutcome.SUCCESS,
            target_type="accounts.user",
            target_id=target.pk,
            metadata={"from_role": from_role, "to_role": role_code},
        )
        _create_account_security_notification(
            target=target,
            audit_event=audit_event,
            event=NotificationEvent.SECURITY_ACCOUNT_ACCESS_CHANGED,
        )
        return MutationResult(user=target, changed=True)


def set_student_lifecycle(
    *,
    actor: User,
    actor_session,
    target_id,
    context: AuditContext,
    status: str,
) -> MutationResult:
    if status not in StudentLifecycleStatus.values:
        raise InvalidManagementInput("student lifecycle status is not supported")
    with _admin_mutation(
        actor=actor,
        actor_session=actor_session,
        target_id=target_id,
        authority_change=False,
    ) as (_locked_actor, target):
        assert target is not None
        if target.pk == actor.pk:
            raise SelfTargetForbidden("an administrator cannot change their own Student lifecycle")
        if target.role.code != "STUDENT":
            raise StudentLifecycleConflict(
                "Student lifecycle can only be changed for a STUDENT-role account."
            )
        if target.student_lifecycle_status == status:
            return MutationResult(user=target, changed=False)
        from_status = target.student_lifecycle_status
        target.student_lifecycle_status = status
        target.save(update_fields=["student_lifecycle_status", "updated_at"])
        record_event(
            context=context,
            action=ACCOUNT_STUDENT_LIFECYCLE_CHANGED,
            outcome=AuditOutcome.SUCCESS,
            target_type="accounts.user",
            target_id=target.pk,
            metadata={"from_status": from_status, "to_status": status},
        )
        return MutationResult(user=target, changed=True)


def assign_designation(
    *,
    actor: User,
    actor_session,
    target_id,
    context: AuditContext,
    designation: str,
) -> MutationResult:
    designation_code = _canonical_designation_code(designation)
    with _admin_mutation(
        actor=actor,
        actor_session=actor_session,
        target_id=target_id,
        authority_change=True,
    ) as (locked_actor, target):
        assert target is not None
        _assert_designation_manager(locked_actor)
        if target.pk == actor.pk:
            raise SelfTargetForbidden("an administrator cannot change their own designations")
        designation_record = Designation.objects.filter(code=designation_code).first()
        if designation_record is None:
            raise ManagementConfigurationError(
                "the requested canonical designation is not synchronized; run "
                "sync_identity_policy first"
            )
        if not designation_role_compatible(
            designation_code=designation_code,
            role_code=target.role.code,
        ):
            raise DesignationRoleConflict(
                f"designation {designation_code} is incompatible with role {target.role.code}"
            )
        assignment = (
            UserDesignation.objects.select_for_update()
            .filter(
                user_id=target.pk,
                designation_id=designation_record.pk,
            )
            .first()
        )
        if assignment is not None:
            return MutationResult(user=target, changed=False)
        UserDesignation.objects.create(user=target, designation=designation_record)
        _ensure_active_manager_remains()
        invalidate_auth_state_after_authority_change(
            user_id=target.pk,
            context=context,
            reason="designation_assigned",
        )
        audit_event = record_event(
            context=context,
            action=ACCOUNT_DESIGNATION_ASSIGNED,
            outcome=AuditOutcome.SUCCESS,
            target_type="accounts.user",
            target_id=target.pk,
            metadata={"designation": designation_code},
        )
        _create_account_security_notification(
            target=target,
            audit_event=audit_event,
            event=NotificationEvent.SECURITY_ACCOUNT_ACCESS_CHANGED,
        )
        return MutationResult(user=target, changed=True)


def remove_designation(
    *,
    actor: User,
    actor_session,
    target_id,
    context: AuditContext,
    designation: str,
) -> MutationResult:
    designation_code = _canonical_designation_code(designation)
    with _admin_mutation(
        actor=actor,
        actor_session=actor_session,
        target_id=target_id,
        authority_change=True,
    ) as (locked_actor, target):
        assert target is not None
        _assert_designation_manager(locked_actor)
        if target.pk == actor.pk:
            raise SelfTargetForbidden("an administrator cannot change their own designations")
        designation_record = Designation.objects.filter(code=designation_code).first()
        if designation_record is None:
            raise ManagementConfigurationError(
                "the requested canonical designation is not synchronized; run "
                "sync_identity_policy first"
            )
        assignment = (
            UserDesignation.objects.select_for_update()
            .filter(
                user_id=target.pk,
                designation_id=designation_record.pk,
            )
            .first()
        )
        if assignment is None:
            return MutationResult(user=target, changed=False)
        assignment.delete()
        _ensure_active_manager_remains()
        invalidate_auth_state_after_authority_change(
            user_id=target.pk,
            context=context,
            reason="designation_removed",
        )
        audit_event = record_event(
            context=context,
            action=ACCOUNT_DESIGNATION_REMOVED,
            outcome=AuditOutcome.SUCCESS,
            target_type="accounts.user",
            target_id=target.pk,
            metadata={"designation": designation_code},
        )
        _create_account_security_notification(
            target=target,
            audit_event=audit_event,
            event=NotificationEvent.SECURITY_ACCOUNT_ACCESS_CHANGED,
        )
        return MutationResult(user=target, changed=True)


def set_capability_override(
    *,
    actor: User,
    actor_session,
    target_id,
    context: AuditContext,
    capability: str,
    effect: UserCapabilityOverride.Effect | str,
    reason: str,
    expires_at: datetime | None = None,
) -> OverrideMutationResult:
    capability_code = _canonical_capability_code(capability)
    effect_value = effect.value if isinstance(effect, UserCapabilityOverride.Effect) else effect
    if effect_value not in UserCapabilityOverride.Effect.values:
        raise InvalidManagementInput("effect must be GRANT or REVOKE")
    if not isinstance(reason, str) or not reason.strip():
        raise InvalidManagementInput("reason is required for a capability override")
    cleaned_reason = reason.strip()
    try:
        UserCapabilityOverride._meta.get_field("reason").clean(cleaned_reason, None)
    except ValidationError as exc:
        raise InvalidManagementInput("reason is invalid") from exc
    cleaned_expiry = _clean_expiry(expires_at)

    with _admin_mutation(
        actor=actor,
        actor_session=actor_session,
        target_id=target_id,
        authority_change=True,
    ) as (locked_actor, target):
        assert target is not None
        if target.pk == locked_actor.pk:
            raise SelfTargetForbidden(
                "an administrator cannot change their own capability overrides"
            )
        capability_record = Capability.objects.filter(code=capability_code).first()
        if capability_record is None:
            raise ManagementConfigurationError(
                "the requested canonical capability is not synchronized; run "
                "sync_identity_policy first"
            )
        existing = (
            UserCapabilityOverride.objects.select_for_update()
            .filter(
                user_id=target.pk,
                capability_id=capability_record.pk,
            )
            .first()
        )
        if existing is not None and (
            existing.effect == effect_value
            and existing.reason == cleaned_reason
            and existing.expires_at == cleaned_expiry
            and existing.created_by_id == locked_actor.pk
        ):
            return OverrideMutationResult(override=existing, changed=False)
        override = set_user_capability_override(
            user=target,
            capability=capability_record,
            effect=effect_value,
            reason=cleaned_reason,
            expires_at=cleaned_expiry,
            created_by=locked_actor,
        )
        _ensure_active_manager_remains()
        invalidate_auth_state_after_authority_change(
            user_id=target.pk,
            context=context,
            reason="capability_override_changed",
        )
        audit_event = record_event(
            context=context,
            action=ACCOUNT_CAPABILITY_OVERRIDE_SET,
            outcome=AuditOutcome.SUCCESS,
            target_type="accounts.user",
            target_id=target.pk,
            metadata={
                "capability": capability_code,
                "effect": effect_value,
                "has_expiry": cleaned_expiry is not None,
            },
        )
        _create_account_security_notification(
            target=target,
            audit_event=audit_event,
            event=NotificationEvent.SECURITY_ACCOUNT_ACCESS_CHANGED,
        )
        return OverrideMutationResult(override=override, changed=True)


def remove_capability_override(
    *,
    actor: User,
    actor_session,
    target_id,
    context: AuditContext,
    capability: str,
) -> OverrideMutationResult:
    capability_code = _canonical_capability_code(capability)
    with _admin_mutation(
        actor=actor,
        actor_session=actor_session,
        target_id=target_id,
        authority_change=True,
    ) as (locked_actor, target):
        assert target is not None
        if target.pk == locked_actor.pk:
            raise SelfTargetForbidden(
                "an administrator cannot change their own capability overrides"
            )
        capability_record = Capability.objects.filter(code=capability_code).first()
        if capability_record is None:
            raise ManagementConfigurationError(
                "the requested canonical capability is not synchronized; run "
                "sync_identity_policy first"
            )
        override = (
            UserCapabilityOverride.objects.select_for_update()
            .filter(
                user_id=target.pk,
                capability_id=capability_record.pk,
            )
            .first()
        )
        if override is None:
            return OverrideMutationResult(override=None, changed=False)
        override.delete()
        _ensure_active_manager_remains()
        invalidate_auth_state_after_authority_change(
            user_id=target.pk,
            context=context,
            reason="capability_override_removed",
        )
        audit_event = record_event(
            context=context,
            action=ACCOUNT_CAPABILITY_OVERRIDE_REMOVED,
            outcome=AuditOutcome.SUCCESS,
            target_type="accounts.user",
            target_id=target.pk,
            metadata={"capability": capability_code},
        )
        _create_account_security_notification(
            target=target,
            audit_event=audit_event,
            event=NotificationEvent.SECURITY_ACCOUNT_ACCESS_CHANGED,
        )
        return OverrideMutationResult(override=override, changed=True)


def revoke_account_sessions(
    *,
    actor: User,
    actor_session,
    target_id,
    context: AuditContext,
) -> SecurityRevocationResult:
    with _admin_mutation(
        actor=actor,
        actor_session=actor_session,
        target_id=target_id,
        authority_change=False,
    ) as (_locked_actor, target):
        assert target is not None
        if target.pk == actor.pk:
            raise SelfTargetForbidden("use self-service session controls for your own sessions")
        count = revoke_all_auth_sessions(
            user_id=target.pk,
            context=context,
            reason="admin_revoked",
        )
        return SecurityRevocationResult(revoked_count=count)


def revoke_account_trusted_sessions(
    *,
    actor: User,
    actor_session,
    target_id,
    context: AuditContext,
) -> SecurityRevocationResult:
    with _admin_mutation(
        actor=actor,
        actor_session=actor_session,
        target_id=target_id,
        authority_change=False,
    ) as (_locked_actor, target):
        assert target is not None
        if target.pk == actor.pk:
            raise SelfTargetForbidden(
                "use self-service trusted-session controls for your own sessions"
            )
        count = revoke_all_trusted_sessions(
            user_id=target.pk,
            context=context,
            reason="admin_revoked",
        )
        return SecurityRevocationResult(revoked_count=count)


def reset_account_mfa(
    *,
    actor: User,
    actor_session,
    target_id,
    context: AuditContext,
) -> MFAResetMutationResult:
    with _admin_mutation(
        actor=actor,
        actor_session=actor_session,
        target_id=target_id,
        authority_change=False,
    ) as (_locked_actor, target):
        assert target is not None
        if target.pk == actor.pk:
            raise SelfTargetForbidden("use self-service MFA controls for your own MFA")
        mfa_result = reset_totp_state(user_id=target.pk)
        invalidation = invalidate_auth_state_after_authority_change(
            user_id=target.pk,
            context=context,
            reason="admin_mfa_reset",
        )
        if mfa_result.changed:
            audit_event = record_event(
                context=context,
                action=ACCOUNT_MFA_RESET,
                outcome=AuditOutcome.SUCCESS,
                target_type="accounts.user",
                target_id=target.pk,
                metadata={},
            )
            _create_account_security_notification(
                target=target,
                audit_event=audit_event,
                event=NotificationEvent.SECURITY_MFA_ADMIN_RESET,
            )
        return MFAResetMutationResult(
            reset=mfa_result.changed,
            mfa=mfa_result,
            invalidation=invalidation,
        )


__all__ = [
    "ACCOUNT_MANAGE_CAPABILITY",
    "INSTITUTIONAL_DESIGNATION_MANAGE_CAPABILITY",
    "AccountManagementError",
    "AccountNotFound",
    "AccountPage",
    "DEFAULT_PAGE_SIZE",
    "DesignationManagementNotAuthorized",
    "DesignationRoleConflict",
    "DuplicateEmail",
    "InvalidManagementInput",
    "LastAccountManagerError",
    "MAX_PAGE_NUMBER",
    "MAX_PAGE_SIZE",
    "MFAResetMutationResult",
    "ManagementConfigurationError",
    "ManagementNotAuthorized",
    "MutationResult",
    "OverrideMutationResult",
    "PaginationError",
    "SecurityRevocationResult",
    "SelfTargetForbidden",
    "assign_designation",
    "change_role",
    "create_account",
    "get_account",
    "list_accounts",
    "list_capability_overrides",
    "list_designations",
    "remove_capability_override",
    "remove_designation",
    "reset_account_mfa",
    "revoke_account_sessions",
    "revoke_account_trusted_sessions",
    "serialize_account",
    "set_account_active",
    "set_capability_override",
    "update_identity",
]
