"""Synchronize code-owned institutional form definitions into PostgreSQL."""

from django.core.management.base import BaseCommand, CommandError

from compass.institutional_forms.bootstrap import CanonicalFormSyncError, sync_institutional_forms


class Command(BaseCommand):
    help = "Synchronize canonical institutional Form Families and supported revisions."

    def handle(self, *args, **options):
        try:
            result = sync_institutional_forms()
        except CanonicalFormSyncError as exc:
            raise CommandError(str(exc)) from exc

        state = "updated" if result.changed else "unchanged"
        self.stdout.write(f"Canonical institutional forms {state}.")
        self.stdout.write(
            "Families: "
            f"created={result.families_created} updated={result.families_updated}; "
            "revisions: "
            f"created={result.revisions_created} updated={result.revisions_updated} "
            f"activated={result.revisions_activated} deactivated={result.revisions_deactivated}."
        )
