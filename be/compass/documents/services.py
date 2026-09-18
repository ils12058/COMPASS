"""Branding-profile configuration services for institutional document rendering."""

from __future__ import annotations

from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import transaction

from compass.audit.actions import DOCUMENT_BRANDING_UPDATED
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event

from .models import DocumentBrandingProfile

PROFILE_KEY = "default"
REQUIRED_FIELDS = frozenset(
    {
        "country_line",
        "institution_name",
        "institution_short_name",
        "office_name",
    }
)
OPTIONAL_FIELDS = frozenset(
    {
        "former_institution_name",
        "institution_address",
        "institution_website_url",
        "institution_contact_email",
        "institution_social_url",
        "office_parent_unit_name",
        "office_email",
        "office_phone",
        "office_location",
    }
)
EDITABLE_FIELDS = REQUIRED_FIELDS | OPTIONAL_FIELDS


class DocumentBrandingError(RuntimeError):
    pass


class DocumentBrandingConfigurationError(DocumentBrandingError):
    pass


class InvalidDocumentBrandingInput(DocumentBrandingError):
    pass


@dataclass(frozen=True, slots=True)
class BrandingUpdateResult:
    profile: DocumentBrandingProfile
    changed: bool
    changed_fields: tuple[str, ...]


def get_branding_profile() -> DocumentBrandingProfile:
    profile = DocumentBrandingProfile.objects.filter(key=PROFILE_KEY).first()
    if profile is None:
        raise DocumentBrandingConfigurationError(
            "The default document branding profile is not configured."
        )
    return profile


def _normalize_field(
    profile: DocumentBrandingProfile,
    field_name: str,
    value: object,
) -> object:
    field = profile._meta.get_field(field_name)
    if field_name in REQUIRED_FIELDS:
        if not isinstance(value, str) or not value.strip():
            raise InvalidDocumentBrandingInput(f"{field_name} must contain meaningful text.")
        normalized: object = value.strip()
    else:
        if value is None:
            normalized = None
        elif not isinstance(value, str):
            raise InvalidDocumentBrandingInput(f"{field_name} must be text or null.")
        else:
            normalized = value.strip() or None

    try:
        field.clean(normalized, profile)
    except ValidationError as exc:
        raise InvalidDocumentBrandingInput(f"{field_name} is invalid.") from exc
    return normalized


def update_branding_profile(
    *,
    changes: dict[str, object],
    context: AuditContext,
) -> BrandingUpdateResult:
    unknown = set(changes) - EDITABLE_FIELDS
    if unknown:
        raise InvalidDocumentBrandingInput(
            f"Unsupported branding fields: {', '.join(sorted(unknown))}."
        )

    with transaction.atomic():
        profile = (
            DocumentBrandingProfile.objects.select_for_update().filter(key=PROFILE_KEY).first()
        )
        if profile is None:
            raise DocumentBrandingConfigurationError(
                "The default document branding profile is not configured."
            )

        normalized = {
            field_name: _normalize_field(profile, field_name, value)
            for field_name, value in changes.items()
        }
        changed_fields = tuple(
            sorted(
                field_name
                for field_name, value in normalized.items()
                if getattr(profile, field_name) != value
            )
        )
        if not changed_fields:
            return BrandingUpdateResult(profile=profile, changed=False, changed_fields=())

        for field_name in changed_fields:
            setattr(profile, field_name, normalized[field_name])
        profile.save(update_fields=[*changed_fields, "updated_at"])
        record_event(
            context=context,
            action=DOCUMENT_BRANDING_UPDATED,
            outcome=AuditOutcome.SUCCESS,
            target_type="documents.documentbrandingprofile",
            target_id=profile.pk,
            metadata={
                "profile_key": profile.key,
                "changed_fields": list(changed_fields),
            },
        )
        return BrandingUpdateResult(
            profile=profile,
            changed=True,
            changed_fields=changed_fields,
        )
