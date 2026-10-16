"""Operator entry point for COMPASS Staging Dataset v1.

Modes:

* ``seed`` (default): create what is missing, reuse what exists, refuse conflicts.
* ``verify``: read-only verification of schema, accounts, scenarios, privacy and side effects.
* ``report --output-dir DIR``: read-only; verify, then generate the UAT documentation.
* ``issue-credentials --output FILE``: explicit, protected credential issuance for participant
  accounts (see ``compass.staging_seed.credentials``).

Every mode is refused outside local-staging and live-staging or without STAGING_SEED_ENABLED.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from compass.staging_seed import DATASET_NAME
from compass.staging_seed.config import StagingSeedConfigurationError
from compass.staging_seed.credentials import CredentialIssuanceError, issue_credentials
from compass.staging_seed.guard import StagingSeedingRefused, ensure_seeding_allowed_by_settings
from compass.staging_seed.reports import ReportError, write_reports
from compass.staging_seed.seed import SeedReport, seed_staging_dataset
from compass.staging_seed.support import StagingSeedError
from compass.staging_seed.timeline import StagingTimelineError
from compass.staging_seed.verify import verify_dataset


def _date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise CommandError("Dates use the YYYY-MM-DD format.") from None


class Command(BaseCommand):
    help = (
        f"{DATASET_NAME}: seed, verify, document, or issue participant credentials. Allowed only "
        "in local-staging and live-staging with STAGING_SEED_ENABLED=true."
    )

    def add_arguments(self, parser):
        modes = parser.add_subparsers(dest="mode")
        seed = modes.add_parser("seed", help="Create missing dataset records; never overwrite.")
        seed.add_argument(
            "--preparation-date",
            type=_date,
            help="Institutional date the timeline is anchored to (default: today, Asia/Manila).",
        )
        verify = modes.add_parser("verify", help="Read-only verification of the seeded dataset.")
        verify.add_argument(
            "--allow-uat-changes",
            action="store_true",
            help="Report scenario states changed by evaluators as warnings instead of failures.",
        )
        report = modes.add_parser("report", help="Read-only: verify, then write UAT documents.")
        report.add_argument("--output-dir", required=True, type=Path)
        report.add_argument("--allow-uat-changes", action="store_true")
        credentials = modes.add_parser(
            "issue-credentials", help="Issue distinct credentials to participant accounts."
        )
        credentials.add_argument(
            "--output",
            required=True,
            type=Path,
            help="New protected handoff file outside the repository (created with mode 0600).",
        )
        credentials.add_argument(
            "--account",
            action="append",
            default=[],
            help="Limit issuance to this account key (repeatable). Required for restricted ones.",
        )
        credentials.add_argument(
            "--reissue",
            action="store_true",
            help="Replace the credential of each named --account (revokes its sessions).",
        )
        credentials.add_argument("--confirm-reissue", action="store_true")

    def handle(self, *args, **options):
        mode = options.get("mode") or "seed"
        try:
            # The guard runs before any configuration is read or any database work happens.
            ensure_seeding_allowed_by_settings()
            if mode == "seed":
                self._write_seed(seed_staging_dataset(anchor=options.get("preparation_date")))
            elif mode == "verify":
                result = verify_dataset(allow_uat_changes=options["allow_uat_changes"])
                self._write_verification(result)
            elif mode == "report":
                result = verify_dataset(allow_uat_changes=options["allow_uat_changes"])
                self._write_verification(result)
                written = write_reports(result, options["output_dir"])
                for path in written:
                    self.stdout.write(f"Wrote {path}")
            else:
                outcome = issue_credentials(
                    output=options["output"],
                    account_keys=tuple(options["account"]),
                    reissue=options["reissue"],
                    confirm_reissue=options["confirm_reissue"],
                )
                where = (
                    f"Handoff file: {outcome.path} (mode 0600)."
                    if outcome.issued
                    else "No handoff file was written."
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Issued {outcome.issued} credential(s); skipped {outcome.skipped} that "
                        f"already have one. {where} Passwords are never displayed."
                    )
                )
        except (
            StagingSeedingRefused,
            StagingSeedConfigurationError,
            StagingTimelineError,
            CredentialIssuanceError,
            ReportError,
        ) as exc:
            raise CommandError(str(exc)) from None
        except StagingSeedError as exc:
            raise CommandError(
                f"{exc} Units that completed earlier stay committed; fix the cause and rerun."
            ) from None

    def _write_seed(self, report: SeedReport) -> None:
        write = self.stdout.write
        write(self.style.SUCCESS(f"{report.dataset_name} ready."))
        write(f"Environment: {report.app_env}")
        write(f"Dataset version: {report.dataset_version}")
        write(f"Preparation date: {report.anchor.isoformat()} ({report.timezone_name})")
        write(f"Seed run ID: {report.run_id} (shared by this run's audit events)")
        write(f"Manifest: {report.account_count} accounts, {report.student_count} Students")
        created = sum(report.created.values())
        existing = sum(report.existing.values())
        write(f"This run: {created} item(s) created, {existing} already present and reused.")
        for domain in sorted({*report.created, *report.existing}):
            write(
                f"  {domain + ':':<44} created {report.created.get(domain, 0):>4}, "
                f"reused {report.existing.get(domain, 0):>4}"
            )
        for note in report.notes:
            write(f"Note: {note}")
        write("No credential was set. Run 'verify', then 'issue-credentials' for participants.")

    def _write_verification(self, result) -> None:
        style = self.style.SUCCESS if result.passed else self.style.ERROR
        self.stdout.write(style(f"Verification {'PASSED' if result.passed else 'FAILED'}."))
        for section in result.sections:
            self.stdout.write(
                f"  {section.name:<28} {section.passed_count:>4} passed, "
                f"{len(section.failures):>3} failed, {len(section.warnings):>3} warnings"
            )
            for failure in section.failures:
                self.stdout.write(self.style.ERROR(f"    FAIL {failure}"))
            for warning in section.warnings:
                self.stdout.write(self.style.WARNING(f"    WARN {warning}"))
        if not result.passed:
            raise CommandError("Staging Dataset v1 verification failed; see the failures above.")
