"""Current reusable personal/contact profile owned by the COMPASS User aggregate."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from compass.audit.actions import PROFILE_UPDATED
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event

from .models import User

PROFILE_EDITABLE_FIELDS = frozenset(
    {
        "date_of_birth",
        "civil_status",
        "contact_number",
        "current_address",
        "permanent_address",
    }
)
CIVIL_STATUS_MAX_LENGTH = 80
CONTACT_NUMBER_MAX_LENGTH = 64
ADDRESS_MAX_LENGTH = 2000


class ProfileError(RuntimeError):
    """Base error for the small self-profile service boundary."""


class InvalidProfileInput(ProfileError):
    """Raised when supplied current-profile values are invalid."""


class ProfileUnavailable(ProfileError):
    """Raised when the authenticated account can no longer be updated."""


@dataclass(frozen=True, slots=True)
class PersonProfileContext:
    """Accounts-owned current facts suitable for domain-specific initial prefill."""

    user_id: UUID
    full_name: str
    email: str
    date_of_birth: date | None
    civil_status: str
    contact_number: str
    current_address: str
    permanent_address: str


@dataclass(frozen=True, slots=True)
class ProfileUpdateResult:
    user: User
    changed_fields: tuple[str, ...]

    @property
    def changed(self) -> bool:
        return bool(self.changed_fields)


def get_person_profile_context(user: User) -> PersonProfileContext:
    """Return current Accounts-owned profile facts without cross-domain lookups."""

    if not getattr(user, "pk", None):
        raise ValueError("a saved user is required")
    return PersonProfileContext(
        user_id=user.pk,
        full_name=user.get_full_name(),
        email=user.email,
        date_of_birth=user.date_of_birth,
        civil_status=user.civil_status,
        contact_number=user.contact_number,
        current_address=user.current_address,
        permanent_address=user.permanent_address,
    )


def _normalize_text(field_name: str, value: object, *, maximum: int) -> str:
    if not isinstance(value, str):
        raise InvalidProfileInput(f"{field_name} must be text.")
    normalized = value.strip()
    if len(normalized) > maximum:
        raise InvalidProfileInput(f"{field_name} is too long.")
    return normalized


def _normalize_date_of_birth(value: object) -> date | None:
    if value is None:
        return None
    if not isinstance(value, date):
        raise InvalidProfileInput("date_of_birth must be a date or null.")
    if value > timezone.localdate():
        raise InvalidProfileInput("date_of_birth must not be in the future.")
    return value


def _normalize_changes(changes: dict[str, object]) -> dict[str, object]:
    unknown = set(changes) - PROFILE_EDITABLE_FIELDS
    if unknown:
        raise InvalidProfileInput(f"Unsupported profile fields: {', '.join(sorted(unknown))}.")

    normalized: dict[str, object] = {}
    for field_name, value in changes.items():
        if field_name == "date_of_birth":
            normalized[field_name] = _normalize_date_of_birth(value)
        elif field_name == "civil_status":
            normalized[field_name] = _normalize_text(
                field_name,
                value,
                maximum=CIVIL_STATUS_MAX_LENGTH,
            )
        elif field_name == "contact_number":
            normalized[field_name] = _normalize_text(
                field_name,
                value,
                maximum=CONTACT_NUMBER_MAX_LENGTH,
            )
        elif field_name in {"current_address", "permanent_address"}:
            normalized[field_name] = _normalize_text(
                field_name,
                value,
                maximum=ADDRESS_MAX_LENGTH,
            )
    return normalized


def update_my_profile(
    *,
    user: User,
    changes: dict[str, object],
    context: AuditContext,
) -> ProfileUpdateResult:
    """Update only the authenticated owner's ordinary current-profile fields."""

    if not getattr(user, "pk", None):
        raise ProfileUnavailable("The authenticated account is unavailable.")

    normalized = _normalize_changes(changes)
    with transaction.atomic():
        locked = User.objects.select_for_update().filter(pk=user.pk).first()
        if locked is None or not locked.is_active:
            raise ProfileUnavailable("The authenticated account is unavailable.")

        changed_fields = tuple(
            sorted(
                field_name
                for field_name, value in normalized.items()
                if getattr(locked, field_name) != value
            )
        )
        if not changed_fields:
            return ProfileUpdateResult(user=locked, changed_fields=())

        for field_name in changed_fields:
            setattr(locked, field_name, normalized[field_name])
        locked.save(update_fields=[*changed_fields, "updated_at"])

        record_event(
            context=context,
            action=PROFILE_UPDATED,
            outcome=AuditOutcome.SUCCESS,
            target_type="accounts.user",
            target_id=locked.pk,
            metadata={"changed_fields": list(changed_fields)},
        )
        return ProfileUpdateResult(user=locked, changed_fields=changed_fields)
