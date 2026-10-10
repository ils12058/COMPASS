"""Provision and reconcile required canonical Service Catalog configuration."""

from django.core.management.base import BaseCommand, CommandError

from compass.service_catalog.bootstrap import (
    CanonicalIdentityPolicyMissing,
    sync_canonical_services,
)
from compass.service_catalog.services import ServiceCatalogError


class Command(BaseCommand):
    help = "Synchronize the system-required canonical Counseling Service."

    def handle(self, *args, **options):
        try:
            result = sync_canonical_services()
        except (CanonicalIdentityPolicyMissing, ServiceCatalogError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            f"Canonical Counseling Service {result.outcome} (id={result.service_id})."
        )
