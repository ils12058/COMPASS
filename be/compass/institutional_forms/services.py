"""Operational services for recording QMS-issued form revision metadata."""

from __future__ import annotations

from uuid import UUID

from django.db import IntegrityError, transaction

from compass.audit.actions import (
    INSTITUTIONAL_FORM_REVISION_ACTIVATED,
    INSTITUTIONAL_FORM_REVISION_DEACTIVATED,
    INSTITUTIONAL_FORM_REVISION_REGISTERED,
)
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.institutional_forms.models import (
    FormFamily,
    FormRevision,
    FormRevisionStatus,
)

SUPPORTED_SCHEMA_VERSIONS: dict[str, frozenset[int]] = {
    "individual_inventory": frozenset({1}),
    "routine_interview": frozenset({1}),
    "referral_slip": frozenset({1}),
    "call_slip": frozenset({1}),
}


class InstitutionalFormError(RuntimeError):
    pass


class InstitutionalFormNotFound(InstitutionalFormError):
    pass


class InvalidInstitutionalFormInput(InstitutionalFormError):
    pass


class InstitutionalFormConflict(InstitutionalFormError):
    pass


def _clean_required(value: str, label: str, max_length: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidInstitutionalFormInput(f"{label} is required")
    cleaned = value.strip()
    if len(cleaned) > max_length:
        raise InvalidInstitutionalFormInput(f"{label} is too long")
    return cleaned


def _clean_schema_version(value: int) -> int:
    if type(value) is not int or value < 1:
        raise InvalidInstitutionalFormInput("internal_schema_version must be a positive integer")
    return value


def list_form_families() -> tuple[FormFamily, ...]:
    return tuple(FormFamily.objects.all().order_by("key"))


def get_form_family_by_key(family_key: str) -> FormFamily:
    family = FormFamily.objects.filter(key=family_key).first()
    if family is None:
        raise InstitutionalFormNotFound("The requested Form Family was not found.")
    return family


def list_form_revisions(family_key: str) -> tuple[FormRevision, ...]:
    family = get_form_family_by_key(family_key)
    return tuple(
        FormRevision.objects.filter(family=family)
        .select_related("family")
        .order_by("internal_schema_version", "id")
    )


def get_active_form_revision(family_key: str) -> FormRevision | None:
    return (
        FormRevision.objects.select_related("family")
        .filter(family__key=family_key, status=FormRevisionStatus.ACTIVE)
        .first()
    )


def require_active_form_revision(family_key: str) -> FormRevision:
    revision = get_active_form_revision(family_key)
    if revision is None:
        raise InstitutionalFormConflict(f"No active Form Revision is configured for {family_key}.")
    return revision


def register_form_revision(
    *,
    family_key: str,
    official_code: str,
    official_revision: str,
    internal_schema_version: int,
    context: AuditContext,
) -> FormRevision:
    family = get_form_family_by_key(family_key)
    code = _clean_required(official_code, "official_code", 96)
    revision_label = _clean_required(official_revision, "official_revision", 32)
    schema_version = _clean_schema_version(internal_schema_version)
    with transaction.atomic():
        try:
            item = FormRevision.objects.create(
                family=family,
                official_code=code,
                official_revision=revision_label,
                internal_schema_version=schema_version,
                status=FormRevisionStatus.INACTIVE,
            )
        except IntegrityError as exc:
            raise InstitutionalFormConflict(
                "A Form Revision with this official identity already exists."
            ) from exc
        record_event(
            context=context,
            action=INSTITUTIONAL_FORM_REVISION_REGISTERED,
            outcome=AuditOutcome.SUCCESS,
            target_type="institutionalforms.formrevision",
            target_id=item.pk,
            metadata={
                "family_key": family.key,
                "official_code": item.official_code,
                "official_revision": item.official_revision,
                "internal_schema_version": item.internal_schema_version,
            },
        )
        return FormRevision.objects.select_related("family").get(pk=item.pk)


def _require_supported(revision: FormRevision) -> None:
    supported = SUPPORTED_SCHEMA_VERSIONS.get(revision.family.key, frozenset())
    if revision.internal_schema_version not in supported:
        raise InstitutionalFormConflict(
            "This COMPASS version does not support the Form Revision's internal schema version."
        )


def get_active_supported_form_revision(family_key: str) -> FormRevision | None:
    """Return the active compatible revision, while allowing families with no active revision."""

    revision = get_active_form_revision(family_key)
    if revision is None:
        return None
    _require_supported(revision)
    return revision


def activate_form_revision(*, revision_id: UUID, context: AuditContext) -> FormRevision:
    with transaction.atomic():
        revision = (
            FormRevision.objects.select_for_update()
            .select_related("family")
            .filter(pk=revision_id)
            .first()
        )
        if revision is None:
            raise InstitutionalFormNotFound("The requested Form Revision was not found.")
        _require_supported(revision)
        if revision.status == FormRevisionStatus.ACTIVE:
            return revision
        previous = (
            FormRevision.objects.select_for_update()
            .filter(family_id=revision.family_id, status=FormRevisionStatus.ACTIVE)
            .exclude(pk=revision.pk)
            .first()
        )
        if previous is not None:
            previous.status = FormRevisionStatus.INACTIVE
            previous.save(update_fields=["status", "updated_at"])
        revision.status = FormRevisionStatus.ACTIVE
        try:
            revision.save(update_fields=["status", "updated_at"])
        except IntegrityError as exc:
            raise InstitutionalFormConflict(
                "Another Form Revision became active concurrently; retry the operation."
            ) from exc
        record_event(
            context=context,
            action=INSTITUTIONAL_FORM_REVISION_ACTIVATED,
            outcome=AuditOutcome.SUCCESS,
            target_type="institutionalforms.formrevision",
            target_id=revision.pk,
            metadata={
                "family_key": revision.family.key,
                "official_code": revision.official_code,
                "official_revision": revision.official_revision,
                "internal_schema_version": revision.internal_schema_version,
            },
        )
        return revision


def deactivate_form_revision(*, revision_id: UUID, context: AuditContext) -> FormRevision:
    with transaction.atomic():
        revision = (
            FormRevision.objects.select_for_update()
            .select_related("family")
            .filter(pk=revision_id)
            .first()
        )
        if revision is None:
            raise InstitutionalFormNotFound("The requested Form Revision was not found.")
        if revision.status == FormRevisionStatus.INACTIVE:
            return revision
        revision.status = FormRevisionStatus.INACTIVE
        revision.save(update_fields=["status", "updated_at"])
        record_event(
            context=context,
            action=INSTITUTIONAL_FORM_REVISION_DEACTIVATED,
            outcome=AuditOutcome.SUCCESS,
            target_type="institutionalforms.formrevision",
            target_id=revision.pk,
            metadata={
                "family_key": revision.family.key,
                "official_code": revision.official_code,
                "official_revision": revision.official_revision,
                "internal_schema_version": revision.internal_schema_version,
            },
        )
        return revision
