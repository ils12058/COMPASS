"""Safe historical revision choices from an already-authorized domain collection."""

from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from django.db.models import QuerySet
from ninja import Schema
from pydantic import ConfigDict

from .models import FormRevision


class FormRevisionFilterOption(Schema):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    official_code: str | None
    official_revision: str | None


class CollectionFilterOptions(Schema):
    model_config = ConfigDict(extra="forbid")
    form_revisions: list[FormRevisionFilterOption]


def represented_form_revisions(
    records: QuerySet, *, family_keys: tuple[str, ...]
) -> tuple[FormRevision, ...]:
    # Status/compatibility governs new records, never historical retrieval. Clear the
    # record ordering so only the stored FK participates in the subquery.
    return tuple(
        FormRevision.objects.filter(
            pk__in=records.order_by().values("form_revision_id"),
            family__key__in=family_keys,
        ).order_by("family__key", "official_code", "official_revision", "id")
    )


def project_filter_options(revisions: Iterable[FormRevision]) -> dict[str, object]:
    return {
        "form_revisions": [
            {
                "id": revision.pk,
                "official_code": revision.official_code,
                "official_revision": revision.official_revision,
            }
            for revision in revisions
        ]
    }
