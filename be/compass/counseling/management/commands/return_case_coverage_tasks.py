"""Explicit idempotent return recording. Nothing schedules this command."""

from django.core.management.base import BaseCommand

from compass.counseling.case_coverage_tasks import reconcile_returns


class Command(BaseCommand):
    help = (
        "Record ended case coverage task returns and confidential recovery flags. "
        "No work is completed or cancelled."
    )

    def handle(self, *args, **options):
        result = reconcile_returns()
        self.stdout.write(
            f"Returned: {result['returned']}; recovery resolved: {result['recovered']}."
        )
