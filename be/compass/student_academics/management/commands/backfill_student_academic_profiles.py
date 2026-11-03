"""Create missing shadow profiles without overwriting existing rows."""

from django.core.management.base import BaseCommand, CommandError

from compass.student_academics.services import backfill_student_academic_profiles


class Command(BaseCommand):
    help = (
        "Backfill StudentAcademicProfile from StudentAffiliation. Student-role rows only; "
        "existing profiles are never overwritten."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Count only; write nothing.")
        parser.add_argument("--batch-size", type=int, default=200, help="Between 1 and 1000.")

    def handle(self, *args, dry_run, batch_size, **options):
        if not 1 <= batch_size <= 1000:
            raise CommandError("--batch-size must be between 1 and 1000.")
        report = backfill_student_academic_profiles(dry_run=dry_run, batch_size=batch_size)
        self.stdout.write(
            " ".join(
                (
                    f"affiliations_total={report.affiliations_total}",
                    f"eligible={report.eligible}",
                    f"missing_profiles={report.missing_profiles}",
                    f"existing_profiles={report.existing_profiles}",
                    f"inactive_student_accounts={report.inactive_student_accounts}",
                    f"non_student_role_rows={report.non_student_role_rows}",
                    f"inactive_college_rows={report.inactive_college_rows}",
                    f"created={report.created}",
                    f"dry_run={'true' if dry_run else 'false'}",
                )
            )
        )
        if report.non_student_role_rows:
            self.stderr.write(
                "WARNING: non-Student-role affiliations were excluded; review D-SAR-03 "
                "before enabling the sync gate."
            )
        if report.inactive_college_rows:
            self.stderr.write(
                "WARNING: affiliations to inactive College/Campus rows were copied as recorded."
            )
