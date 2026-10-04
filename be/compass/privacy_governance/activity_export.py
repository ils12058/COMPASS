"""A bounded CSV of the exact safe activity projection, audited before releasing bytes."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from io import StringIO
from itertools import islice
from uuid import uuid4

from django.db import transaction
from django.utils import timezone

from compass.audit.actions import PRIVACY_ACTIVITY_EXPORTED
from compass.audit.context import AuditContext
from compass.common.csv_export import spreadsheet_safe_text
from compass.common.institutional_time import to_institution_time

from .activity import PrivacyActivitySpec
from .releases import _record_release

MAX_EXPORT_ROWS = 10_000
CSV_CONTENT_TYPE = "text/csv; charset=utf-8"


class PrivacyActivityExportTooLarge(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PrivacyActivityExport:
    content: bytes
    filename: str


def export_privacy_activity(*, spec: PrivacyActivitySpec, context: AuditContext):
    # Freeze the selected projected dataset before appending the export event. The ordered
    # cursor uses one PostgreSQL statement snapshot; subsequent audit inserts cannot join it.
    with transaction.atomic():
        items = tuple(islice(spec.items(), MAX_EXPORT_ROWS + 1))
        if len(items) > MAX_EXPORT_ROWS:
            raise PrivacyActivityExportTooLarge(
                f"More than {MAX_EXPORT_ROWS:,} events match. Narrow the filters before exporting."
            )
        output = StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(
            (
                "Occurred At",
                "Category",
                "Event Type",
                "Title",
                "Description",
                "Actor",
                "Artifact",
                "Format",
                "Scope",
                "Reference",
            )
        )
        for item in items:
            writer.writerow(
                tuple(
                    spreadsheet_safe_text(value)
                    for value in (
                        to_institution_time(item.occurred_at).isoformat(),
                        item.category,
                        item.type,
                        item.title,
                        item.description,
                        item.actor_display_name,
                        item.artifact_type,
                        item.artifact_format,
                        item.scope,
                        item.resource_reference,
                    )
                )
            )
        content = output.getvalue().encode("utf-8")
        _record_release(
            context=context,
            action=PRIVACY_ACTIVITY_EXPORTED,
            target_type="privacy.activityexport",
            target_id=uuid4(),
            metadata={
                "exported_row_count": len(items),
                "category": spec.category,
                "event_type": spec.event_type,
                "date_from": spec.criteria.date_from.isoformat()
                if spec.criteria.date_from
                else None,
                "date_to": spec.criteria.date_to.isoformat() if spec.criteria.date_to else None,
                "search_applied": bool(spec.criteria.search),
                "actor_applied": bool(spec.criteria.actor),
            },
        )
    stamp = to_institution_time(timezone.now()).strftime("%Y%m%d-%H%M%S")
    return PrivacyActivityExport(content, f"COMPASS-Privacy-Activity-{stamp}.csv")
