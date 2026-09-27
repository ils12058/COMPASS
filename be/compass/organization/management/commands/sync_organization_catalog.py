"""Synchronize the code-owned UCN organization catalog."""

from django.core.management.base import BaseCommand

from compass.organization.bootstrap import sync_organization_catalog


class Command(BaseCommand):
    help = "Synchronize canonical Campus, College, and Program rows."

    def handle(self, *args, **options):
        result = sync_organization_catalog()
        if result.changed:
            self.stdout.write(
                self.style.SUCCESS(
                    "Synchronized Organization catalog: "
                    + ", ".join(
                        f"{key}={value}" for key, value in result.metadata().items() if value
                    )
                )
            )
        else:
            self.stdout.write("Organization catalog is already synchronized.")
