"""Deliberate installation/adoption of the database-owned Organization catalog."""

from django.core.management.base import BaseCommand, CommandError

from compass.organization.bootstrap import (
    CatalogInitializationError,
    initialize_organization_catalog,
)


class Command(BaseCommand):
    help = "Explicitly seed an empty catalog, adopt existing data, or check its receipt."

    def add_arguments(self, parser):
        actions = parser.add_mutually_exclusive_group(required=True)
        for action in ("seed", "adopt", "check"):
            actions.add_argument(f"--{action}", action="store_const", const=action, dest="action")
        parser.add_argument("--reference", default="")
        parser.add_argument("--allow-empty-adoption", action="store_true")

    def handle(self, *args, **options):
        try:
            result = initialize_organization_catalog(
                action=options["action"],
                reference=options["reference"],
                allow_empty_adoption=options["allow_empty_adoption"],
            )
        except CatalogInitializationError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            f"Catalog {result.receipt.source}; changed={result.changed}; "
            f"baseline={result.receipt.baseline_version or 'adopted data'}"
        )
