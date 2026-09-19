"""Operator-facing COMPASS configuration and runtime diagnostics."""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from compass.platform_ops.diagnostics import (
    DiagnosticCheck,
    DiagnosticStatus,
    WORKER_SMOKE_DEFAULT_TIMEOUT_SECONDS,
    WORKER_SMOKE_MAX_TIMEOUT_SECONDS,
    collect_environment_diagnostics,
    collect_platform_health,
    run_worker_smoke,
)


def _status_prefix(status: DiagnosticStatus) -> str:
    if status == DiagnosticStatus.HEALTHY:
        return "OK"
    if status in {DiagnosticStatus.DEGRADED, DiagnosticStatus.UNAVAILABLE}:
        return "FAIL"
    if status == DiagnosticStatus.DISABLED:
        return "INFO"
    return "WARN"


class Command(BaseCommand):
    help = "Run safe COMPASS configuration and platform dependency diagnostics."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--configuration-only",
            action="store_true",
            help="Inspect safe resolved configuration and skip runtime network probes.",
        )
        parser.add_argument(
            "--worker-smoke",
            action="store_true",
            help="Actively verify Celery worker execution using compass.infrastructure.noop.",
        )
        parser.add_argument(
            "--worker-timeout",
            type=float,
            default=WORKER_SMOKE_DEFAULT_TIMEOUT_SECONDS,
            help=(
                "Worker smoke timeout in seconds "
                f"(maximum {WORKER_SMOKE_MAX_TIMEOUT_SECONDS:g})."
            ),
        )

    def _write_check(self, check: DiagnosticCheck) -> None:
        prefix = _status_prefix(check.status)
        self.stdout.write(f"[{prefix}] {check.label} — {check.summary}")

    def _write_configuration(self) -> None:
        try:
            environment = collect_environment_diagnostics()
        except Exception as exc:
            raise CommandError(
                "COMPASS configuration diagnostics could not be evaluated."
            ) from exc

        self.stdout.write("[OK] Application configuration — resolved Django settings are loaded.")
        for category in environment.categories:
            safe_values = ", ".join(
                f"{value.code}={str(value.value).lower() if isinstance(value.value, bool) else value.value}"
                for value in category.values
            )
            self.stdout.write(f"[INFO] {category.label} — {safe_values}")
        self.stdout.write(f"[INFO] Startup limitation — {environment.startup_limitation}")

    def handle(self, *args, **options) -> None:
        configuration_only = bool(options["configuration_only"])
        worker_smoke = bool(options["worker_smoke"])
        timeout = float(options["worker_timeout"])

        if configuration_only and worker_smoke:
            raise CommandError("--worker-smoke cannot be combined with --configuration-only")
        if not 0 < timeout <= WORKER_SMOKE_MAX_TIMEOUT_SECONDS:
            raise CommandError(
                "worker timeout must be greater than zero and at most "
                f"{WORKER_SMOKE_MAX_TIMEOUT_SECONDS:g} seconds"
            )

        self.stdout.write("COMPASS diagnostics")
        self.stdout.write("")
        self._write_configuration()

        if configuration_only:
            return

        try:
            health = collect_platform_health()
        except Exception as exc:
            raise CommandError("COMPASS runtime diagnostics could not be evaluated.") from exc

        for check in health.checks:
            self._write_check(check)

        worker_check = None
        if worker_smoke:
            worker_check = run_worker_smoke(timeout_seconds=timeout)
            self._write_check(worker_check)

        if health.status != DiagnosticStatus.HEALTHY:
            raise CommandError("One or more required COMPASS runtime diagnostics failed.")
        if worker_check is not None and worker_check.status != DiagnosticStatus.HEALTHY:
            raise CommandError("The Celery worker smoke diagnostic failed.")
