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
        self.stdout.write(
            "Retired capability state: "
            f"role grants deleted={result.retired_role_grants_deleted}; "
            f"designation grants deleted={result.retired_designation_grants_deleted}; "
            f"overrides deleted={result.retired_overrides_deleted}; "
            f"capabilities deleted={result.retired_capabilities_deleted}. "
            "Other unknown database rows were retained."
        )
