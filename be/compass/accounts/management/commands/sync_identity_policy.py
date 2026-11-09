"""Synchronize the version-controlled identity policy into PostgreSQL."""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from compass.accounts.bootstrap import IdentityPolicySyncError, sync_identity_policy


class Command(BaseCommand):
    help = "Synchronize canonical COMPASS identity roles, designations, capabilities, and grants."

    def handle(self, *args, **options):
        try:
            result = sync_identity_policy()
        except IdentityPolicySyncError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write("Identity policy synchronization complete.")
        self.stdout.write(
            "Definitions: "
            f"roles created={result.roles_created} updated={result.roles_updated}; "
            f"designations created={result.designations_created} "
            f"updated={result.designations_updated}; "
            f"capabilities created={result.capabilities_created} "
            f"updated={result.capabilities_updated}."
        )
        self.stdout.write(
            "Baseline grants: "
            f"role grants created={result.role_grants_created}; "
            f"designation grants created={result.designation_grants_created}. "
            "Unknown database rows were retained."
        )
