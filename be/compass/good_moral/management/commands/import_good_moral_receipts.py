"""Synthetic-only rehearsal. Production transition needs separate authorization and tooling."""

import json
from uuid import UUID

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, connection

from compass.good_moral.legacy_receipts import (
    activate_synthetic_import,
    begin_import,
    import_chunk,
    inventory,
)
from compass.good_moral.models import GoodMoralReceiptAssignment


class Command(BaseCommand):
    help = "Classify or import receipt observations in a confirmed disposable local database."
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument("--confirm-disposable-database", required=True)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--import", action="store_true", dest="apply")
        parser.add_argument("--activate", action="store_true")
        parser.add_argument("--batch", type=UUID)
        parser.add_argument("--evidence-reference", default="")
        parser.add_argument("--chunk-size", type=int, default=100)
        parser.add_argument("--max-batches", type=int, default=1000)
        parser.add_argument("--maximum-records", type=int, default=100000)

    def handle(self, *args, **options):
        db = settings.DATABASES["default"]
        name = db["NAME"]
        if (
            settings.APP_ENV != "local-staging"
            or db["HOST"] not in {"127.0.0.1", "localhost", "::1"}
            or options["confirm_disposable_database"] != name
            or not (name.startswith("test_") or name.endswith("_synthetic"))
        ):
            raise CommandError(
                "Receipt rehearsal requires an explicitly confirmed disposable local database."
            )
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database()")
            if cursor.fetchone()[0] != name:
                raise CommandError(
                    "The actual database does not match the confirmed disposable database."
                )
        if not (
            1 <= options["chunk_size"] <= 1000
            and 1 <= options["max_batches"] <= 10000
            and 1 <= options["maximum_records"] <= 1000000
        ):
            raise CommandError("Receipt rehearsal bounds are invalid.")
        if options["dry_run"] and (options["apply"] or options["activate"]):
            raise CommandError("Dry-run cannot be combined with import or activation.")
        try:
            if not options["apply"]:
                if options["activate"]:
                    raise ValueError(
                        "Synthetic activation requires --import and an existing batch."
                    )
                observed = inventory(maximum_records=options["maximum_records"])
            else:
                if options["batch"] is None:
                    raise ValueError("Import requires an explicit batch UUID.")
                observed = begin_import(
                    batch_id=options["batch"],
                    evidence_reference=options["evidence_reference"],
                    maximum_records=options["maximum_records"],
                )
                for _ in range(options["max_batches"]):
                    if (
                        import_chunk(
                            batch_id=options["batch"], observed=observed, size=options["chunk_size"]
                        )
                        == 0
                    ):
                        break
                if options["activate"]:
                    activate_synthetic_import(batch_id=options["batch"])
        except ValueError as exc:
            raise CommandError(str(exc)) from None
        except DatabaseError:
            # No raw SQL exception DETAIL: keys and row facts can contain payment/Student data.
            raise CommandError(
                "Receipt import or activation was refused by a database guard "
                "or transaction error. "
                "The batch remains resumable; review protected diagnostics."
            ) from None
        result = {"source_counts": observed.counts}
        if options["apply"]:
            result["imported_observations"] = GoodMoralReceiptAssignment.objects.filter(
                import_batch_id=options["batch"]
            ).count()
        self.stdout.write(json.dumps(result, sort_keys=True))
