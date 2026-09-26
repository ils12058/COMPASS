"""Explicit synchronization of code-owned institutional form definitions."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from uuid import UUID

from django.db import IntegrityError, transaction

from compass.audit.actions import INSTITUTIONAL_FORMS_SYNCED
from compass.audit.context import AuditContext
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.institutional_forms.canonical import CANONICAL_FORM_FAMILIES
from compass.institutional_forms.models import FormFamily, FormRevision, FormRevisionStatus


class CanonicalFormSyncError(RuntimeError):
    """Persisted form metadata cannot be safely reconciled with the canonical registry."""


@dataclass(frozen=True, slots=True)
class CanonicalFormSyncResult:
    families_created: int = 0
    families_updated: int = 0
    revisions_created: int = 0
    revisions_updated: int = 0
    revisions_activated: int = 0
    revisions_deactivated: int = 0

    @property
    def changed(self) -> bool:
        return any(asdict(self).values())

    def metadata(self) -> dict[str, int]:
        return asdict(self)


def _get_or_create_family(*, key: str, title: str) -> tuple[FormFamily, bool]:
    family = FormFamily.objects.select_for_update().filter(key=key).first()
    if family is not None:
        return family, False
    try:
        with transaction.atomic():
            return FormFamily.objects.create(key=key, title=title), True
    except IntegrityError:
        return FormFamily.objects.select_for_update().get(key=key), False


def _get_or_create_revision(
    *,
    family: FormFamily,
    official_code: str,
    official_revision: str,
    internal_schema_version: int,
) -> tuple[FormRevision, bool]:
    revision = (
        FormRevision.objects.select_for_update()
        .filter(
            family=family,
            official_code=official_code,
            official_revision=official_revision,
        )
        .first()
    )
    if revision is not None:
        return revision, False
    try:
        with transaction.atomic():
            return (
                FormRevision.objects.create(
                    family=family,
                    official_code=official_code,
                    official_revision=official_revision,
                    internal_schema_version=internal_schema_version,
                    status=FormRevisionStatus.INACTIVE,
                ),
                True,
            )
    except IntegrityError:
        return (
            FormRevision.objects.select_for_update().get(
                family=family,
                official_code=official_code,
                official_revision=official_revision,
            ),
            False,
        )


def _sync_institutional_forms() -> CanonicalFormSyncResult:
    counts = {
        "families_created": 0,
        "families_updated": 0,
        "revisions_created": 0,
        "revisions_updated": 0,
        "revisions_activated": 0,
        "revisions_deactivated": 0,
    }

    for definition in CANONICAL_FORM_FAMILIES:
        family, created = _get_or_create_family(key=definition.key, title=definition.title)
        if created:
            counts["families_created"] += 1
        elif family.title != definition.title:
            family.title = definition.title
            family.save(update_fields=["title", "updated_at"])
            counts["families_updated"] += 1

        active_revision_id: UUID | None = None
        for revision_definition in definition.revisions:
            revision, revision_created = _get_or_create_revision(
                family=family,
                official_code=revision_definition.official_code,
                official_revision=revision_definition.official_revision,
                internal_schema_version=revision_definition.internal_schema_version,
            )
            if revision_created:
                counts["revisions_created"] += 1
            elif revision.internal_schema_version != revision_definition.internal_schema_version:
                revision.internal_schema_version = revision_definition.internal_schema_version
                revision.save(update_fields=["internal_schema_version", "updated_at"])
                counts["revisions_updated"] += 1
            if revision_definition.active:
                active_revision_id = revision.pk

        active_rows = tuple(
            FormRevision.objects.select_for_update().filter(
                family=family,
                status=FormRevisionStatus.ACTIVE,
            )
        )
        for active_row in active_rows:
            if active_row.pk == active_revision_id:
                continue
            active_row.status = FormRevisionStatus.INACTIVE
            active_row.save(update_fields=["status", "updated_at"])
            counts["revisions_deactivated"] += 1

        if active_revision_id is not None:
            canonical_active = FormRevision.objects.select_for_update().get(pk=active_revision_id)
            if canonical_active.status != FormRevisionStatus.ACTIVE:
                canonical_active.status = FormRevisionStatus.ACTIVE
                canonical_active.save(update_fields=["status", "updated_at"])
                counts["revisions_activated"] += 1

    result = CanonicalFormSyncResult(**counts)
    if result.changed:
        record_event(
            context=AuditContext.system(),
            action=INSTITUTIONAL_FORMS_SYNCED,
            outcome=AuditOutcome.SUCCESS,
            metadata=result.metadata(),
        )
    return result


def sync_institutional_forms() -> CanonicalFormSyncResult:
    """Reconcile canonical definitions while preserving historical rows and stable IDs."""

    try:
        with transaction.atomic():
            return _sync_institutional_forms()
    except (IntegrityError, FormFamily.DoesNotExist, FormRevision.DoesNotExist) as exc:
        raise CanonicalFormSyncError(
            "Canonical institutional forms could not be synchronized safely. "
            "Inspect existing Form Family and Form Revision identities before retrying."
        ) from exc
