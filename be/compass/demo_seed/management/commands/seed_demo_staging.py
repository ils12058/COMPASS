"""Seed the deterministic, synthetic COMPASS demo dataset into a staging environment."""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from compass.demo_seed.config import DemoConfigurationError
from compass.demo_seed.guard import DemoSeedingRefused, ensure_demo_seeding_allowed_by_settings
from compass.demo_seed.seed import SeedReport, seed_demo_staging
from compass.demo_seed.support import DemoSeedError
from compass.demo_seed.timeline import DemoTimelineError


class Command(BaseCommand):
    help = (
        "Seed or reconcile the synthetic staging demo dataset. Allowed only in local-staging "
        "and live-staging with DEMO_SEEDING_ENABLED=true; safe to rerun."
    )

    def handle(self, *args, **options):
        try:
            # The guard runs before any configuration is read or any database work happens.
            ensure_demo_seeding_allowed_by_settings()
            report = seed_demo_staging()
        except (DemoSeedingRefused, DemoConfigurationError, DemoTimelineError) as exc:
            raise CommandError(str(exc)) from None
        except DemoSeedError as exc:
            raise CommandError(
                f"{exc} Units that completed earlier stay committed; fix the cause and rerun."
            ) from None
        self._write_report(report)

    def _write_report(self, report: SeedReport) -> None:
        write = self.stdout.write
        write(self.style.SUCCESS("COMPASS staging demo dataset ready."))
        write("")
        write(f"Environment: {report.app_env}")
        write(f"Dataset version: {report.dataset_version}")
        write(f"Timeline anchor: {report.anchor.isoformat()} ({report.timezone_name})")
        write(f"Seed run ID: {report.run_id} (shared by this run's audit events)")
        write("")
        write("Accounts:")
        for line in report.accounts:
            details = [line.role, *line.designations]
            if line.lifecycle:
                details.append(line.lifecycle)
            write(f"  {line.label:<50} {line.email:<42} {'/'.join(details)}; {line.auth}")
        write("")
        write("Records:")
        for label, value in report.records:
            write(f"  {label + ':':<24} {value}")
        write("")
        created = sum(report.created.values())
        existing = sum(report.existing.values())
        write(f"This run: {created} item(s) created, {existing} already present and reused.")
        for note in report.notes:
            write(f"Note: {note}")
        write("")
        write("Password: configured externally; not displayed.")
