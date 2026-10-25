"""Deprecated seed-only alias; never reconcile official database values."""

from django.core.management.base import BaseCommand, CommandError

from compass.organization.bootstrap import CatalogInitializationError, sync_organization_catalog


class Command(BaseCommand):
    help = "Deprecated seed-only alias. Existing catalogs must be explicitly adopted."

    def handle(self, *args, **options):
        try:
            result = sync_organization_catalog()
        except CatalogInitializationError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            f"Seed-only compatibility alias: {result.receipt.source}; changed={result.changed}. "
            "Use initialize_organization_catalog --seed/--adopt/--check."
        )
