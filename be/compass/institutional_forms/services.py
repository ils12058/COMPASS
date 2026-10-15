"""Read and compatibility services for synchronized institutional form metadata."""

from __future__ import annotations

from django.db.models import Case, IntegerField, Value, When

from compass.institutional_forms.canonical import (
    CANONICAL_FORM_FAMILY_KEYS,
    get_canonical_form_family,
    get_canonical_form_revision,
)
from compass.institutional_forms.models import FormFamily, FormRevision, FormRevisionStatus


class InstitutionalFormError(RuntimeError):
    pass


class InstitutionalFormNotFound(InstitutionalFormError):
    pass


class InstitutionalFormConflict(InstitutionalFormError):
    pass


class UnsupportedInstitutionalFormRevision(InstitutionalFormConflict):
    pass


def list_form_families() -> tuple[FormFamily, ...]:
    return tuple(
        FormFamily.objects.filter(key__in=CANONICAL_FORM_FAMILY_KEYS)
        .prefetch_related("revisions")
        .order_by("key")
    )


def get_form_family_by_key(family_key: str) -> FormFamily:
    if get_canonical_form_family(family_key) is None:
        raise InstitutionalFormNotFound("The requested Form Family is not supported by COMPASS.")
    family = FormFamily.objects.filter(key=family_key).first()
    if family is None:
        raise InstitutionalFormNotFound("The requested canonical Form Family is not synchronized.")
    return family


def list_form_revisions(family_key: str) -> tuple[FormRevision, ...]:
    family = get_form_family_by_key(family_key)
    return tuple(
        FormRevision.objects.filter(family=family)
        .select_related("family")
        .order_by(
            Case(
                When(status=FormRevisionStatus.ACTIVE, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            ),
            "-created_at",
            "id",
        )
    )


def get_active_form_revision(family_key: str) -> FormRevision | None:
    if get_canonical_form_family(family_key) is None:
        return None
    return (
        FormRevision.objects.select_related("family")
        .filter(family__key=family_key, status=FormRevisionStatus.ACTIVE)
        .first()
    )


def is_supported_form_revision(revision: FormRevision) -> bool:
    family_key = revision.family.key
    return (
        get_canonical_form_revision(
            family_key=family_key,
            official_code=revision.official_code,
            official_revision=revision.official_revision,
            internal_schema_version=revision.internal_schema_version,
        )
        is not None
    )


def is_current_form_revision(revision: FormRevision) -> bool:
    """Whether the exact saved identity is canonical for new records in this build."""
    definition = get_canonical_form_revision(
        family_key=revision.family.key,
        official_code=revision.official_code,
        official_revision=revision.official_revision,
        internal_schema_version=revision.internal_schema_version,
    )
    return definition is not None and definition.active


def _require_supported(revision: FormRevision) -> None:
    if not is_supported_form_revision(revision):
        raise UnsupportedInstitutionalFormRevision(
            "This COMPASS version does not support this exact Form Revision identity."
        )


def get_active_supported_form_revision(family_key: str) -> FormRevision | None:
    """Return the active exact canonical revision, allowing families with no active revision."""

    revision = get_active_form_revision(family_key)
    if revision is None:
        return None
    _require_supported(revision)
    if not is_current_form_revision(revision):
        raise UnsupportedInstitutionalFormRevision(
            "The active Form Revision is retired by this COMPASS version. "
            "Run sync_institutional_forms before creating new records."
        )
    return revision


def require_active_supported_form_revision(family_key: str) -> FormRevision:
    """Return the required active revision only when its exact identity is supported."""

    revision = get_active_supported_form_revision(family_key)
    if revision is None:
        raise InstitutionalFormConflict(
            f"No active supported Form Revision is configured for {family_key}."
        )
    return revision
