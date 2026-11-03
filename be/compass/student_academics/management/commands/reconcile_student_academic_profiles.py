"""Aggregate reconciliation of the shadow profile against the affiliation truth."""

from django.core.management.base import BaseCommand, CommandError

from compass.student_academics.services import reconcile_student_academic_profiles


class Command(BaseCommand):
    help = (
        "Report aggregate StudentAcademicProfile mismatches. Blocking mismatches are "
        "affiliations without a profile, College drift, non-null Program or effective date, "
        "VERIFIED status, and profiles without an affiliation."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--fail-on-mismatch",
            action="store_true",
            help="Exit nonzero when any blocking mismatch exists.",
        )

    def handle(self, *args, fail_on_mismatch, **options):
        report = reconcile_student_academic_profiles()
        self.stdout.write(
            " ".join(
                (
                    f"affiliations_without_profile={report.affiliations_without_profile}",
                    f"profile_college_drift={report.profile_college_drift}",
                    f"profile_program_present={report.profile_program_present}",
                    f"profile_effective_at_present={report.profile_effective_at_present}",
                    f"profile_verified={report.profile_verified}",
                    f"profiles_without_affiliation={report.profiles_without_affiliation}",
                    f"blocking_total={report.blocking_total}",
                    f"non_student_profiles={report.non_student_profiles}",
                    f"inactive_student_profiles={report.inactive_student_profiles}",
                )
            )
        )
        if report.non_student_profiles:
            self.stderr.write(
                "WARNING: non-Student profiles exist; these are reported separately from "
                "blocking mismatches."
            )
        if report.inactive_student_profiles:
            self.stderr.write(
                "WARNING: inactive Student profiles exist; these are reported separately "
                "from blocking mismatches."
            )
        if report.blocking_total:
            if fail_on_mismatch:
                raise CommandError(f"{report.blocking_total} blocking profile mismatch(es) remain.")
            self.stderr.write("WARNING: blocking mismatches remain; do not enable the sync gate.")
        else:
            self.stdout.write(self.style.SUCCESS("No blocking profile mismatches."))
