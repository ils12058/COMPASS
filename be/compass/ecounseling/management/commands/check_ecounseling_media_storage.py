"""Deployment preflight without printing endpoints, bucket names or credentials."""

from django.core.management.base import BaseCommand, CommandError

from compass.integrations.storage import ObjectStorage


class Command(BaseCommand):
    help = "Verify private, unversioned E-Counseling media storage without modifying objects."

    def handle(self, *args, **options):
        try:
            ObjectStorage(alias="ecounseling_media").validate_sensitive_policy()
        except Exception:
            raise CommandError("Sensitive media storage policy could not be verified.") from None
        self.stdout.write(self.style.SUCCESS("E-Counseling media storage policy verified."))
        self.stdout.write("Deployment must also verify CDN/public endpoint access is disabled.")
