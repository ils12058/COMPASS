"""Read-only canonical database/migration and worker gates; operator tooling, never startup."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

# The staging coordinator deliberately keeps RunPython, constraints, and non-null defaults
# outside the routine policy unless the complete migration source has been reviewed. Pinning the
# source digest makes the exception exact: editing one of these migrations requires a new review.
REVIEWED_MIGRATIONS = {
    "appointments/0002_appointment_reminders": (
        "d3df93c555e2ebb91b6efcb188325620946c49aa2007dbaf55fadc8b81e5b101"
    ),
    "guidance_followups/0001_initial": (
        "1f2e8b449c32b2650129e5cf4e83806dd4ee424c29b7391d4c8d8a218f906806"
    ),
    "guidance_followups/0002_guidancefollowupmutation": (
        "68aae55d167f46c4fccc3937256291a9c3fb48c09fef5cbec8f140821163337e"
    ),
    "group_sessions/0001_initial": (
        "8c948628511004f2249873a1fd9e3d72f393f0d7957c76d2cc730284d7584ca2"
    ),
    "service_catalog/0002_booking_pathways": (
        "627cb721f11d06e1fe0fd8dce2c91aec50b70d25924dff0e55e2607618536951"
    ),
    "service_catalog/0003_fixed_date_slots": (
        "ff54707a1d30f4f424e982f8913c6f896f7f021fe575154ce96075677a587381"
    ),
}


class Refused(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise Refused(message)


def validate_operations(plan):
    from django.db.migrations import operations as ops

    root = Path(__file__).resolve().parents[2]
    for migration, backwards in plan:
        require(
            not backwards and migration.atomic,
            "Backwards/non-atomic migration requires coordinated review",
        )
        migration_key = f"{migration.app_label}/{migration.name}"
        reviewed_digest = REVIEWED_MIGRATIONS.get(migration_key)
        migration_file = (
            root / "compass" / migration.app_label / "migrations" / f"{migration.name}.py"
        )
        try:
            actual_digest = hashlib.sha256(migration_file.read_bytes()).hexdigest()
        except OSError:
            actual_digest = ""
        digest_matches = reviewed_digest is not None and actual_digest == reviewed_digest
        if reviewed_digest is not None:
            require(
                digest_matches,
                f"{migration.app_label}.{migration.name}: reviewed migration source changed",
            )
        for operation in migration.operations:
            safe = type(operation) in {ops.CreateModel, ops.AddIndex}
            if type(operation) is ops.AddField:
                from django.db.models import NOT_PROVIDED

                safe = (
                    operation.field.null
                    and not operation.field.primary_key
                    and not operation.field.has_default()
                    and operation.field.db_default is NOT_PROVIDED
                )
            if not safe:
                safe = digest_matches
            require(
                safe,
                f"{migration.app_label}.{migration.name}: {type(operation).__name__} "
                "requires a separately reviewed coordinated procedure",
            )


def inspect_database():
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    import django
    from django.conf import settings
    from django.db import connection, transaction
    from django.db.migrations.executor import MigrationExecutor

    django.setup()
    require(settings.APP_ENV == "live-staging", "Destination must be live-staging")
    require(
        not getattr(settings, "STAGING_SEED_ENABLED", False), "Persistent seeding opt-in forbidden"
    )
    root = Path(__file__).resolve().parents[2]
    baseline = json.loads((Path(__file__).with_name("baseline-sha256.json")).read_text())
    require(len(baseline) == 26, "Canonical baseline manifest changed")
    labels = set()
    for filename, digest in baseline.items():
        require(
            hashlib.sha256((root / filename).read_bytes()).hexdigest() == digest,
            "Canonical baseline was modified",
        )
        labels.add(filename.split("/")[1])
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
        tables = set(connection.introspection.table_names())
        require(
            "django_migrations" in tables and "accounts_user" in tables,
            "Uninitialized database; never bootstrap in normal deployment",
        )
        require(
            not any(
                "dispositioncase" in t or "dispositionhold" in t or "operationalretentionrule" in t
                for t in tables
            ),
            "Retired ledger present",
        )
        executor = MigrationExecutor(connection)
        loader = executor.loader
        require(not loader.detect_conflicts(), "Conflicting migration graph")
        loader.check_consistent_history(connection)
        applied = set(loader.applied_migrations)
        require(
            all((label, "0001_canonical_baseline") in applied for label in labels),
            "Missing applied canonical baseline",
        )
        require(
            all(key in loader.disk_migrations for key in applied),
            "Unknown applied migration; rollback/pre-canonical image refused",
        )
        plan = executor.migration_plan(loader.graph.leaf_nodes())
        validate_operations(plan)
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM accounts_user")
            require(cursor.fetchone()[0] > 0, "Initialized account population missing")
        transaction.set_rollback(True)
    from config.celery import app

    app.loader.import_default_modules()
    require(
        not any(t.startswith("compass.privacy_governance.") for t in app.tasks),
        "Retired task registration",
    )
    tasks = {v["task"] for v in app.conf.beat_schedule.values()}
    required = {
        "compass.ecounseling.recover_media_artifacts",
        "compass.notifications.push.dispatch_due",
        "compass.notifications.email.dispatch_due",
        "compass.authentication.email_change.recover_unsent_alerts",
    }
    require(
        required <= tasks and not any(t.startswith("compass.privacy_governance.") for t in tasks),
        "Unsafe Beat schedule",
    )
    print(
        json.dumps(
            {
                "canonical_database": True,
                "pending_forward_migrations": [f"{m.app_label}.{m.name}" for m, _ in plan],
                "beat_tasks": sorted(tasks),
            }
        )
    )


def worker_idle():
    import django

    django.setup()
    from config.celery import app

    for kind in ("active", "reserved", "scheduled"):
        responses = getattr(app.control.inspect(timeout=3), kind)()
        require(
            responses is not None and len(responses) == 1, "Expected exactly one responsive worker"
        )
        require(
            all(not work for work in responses.values()),
            f"Worker {kind} work remains; preserve runtime and review",
        )
    # Check all broker lists (including priorities/custom queues), ETA/unacked work; no purge.
    import redis

    broker = redis.Redis.from_url(app.conf.broker_url)
    for key in broker.scan_iter():
        kind = broker.type(key)
        require(kind != b"list" or broker.llen(key) == 0, "Queued broker work requires review")
        require(
            key != b"unacked" or broker.hlen(key) == 0, "Unacknowledged broker work requires review"
        )
    print("Worker and broker idle; no task arguments inspected")


if __name__ == "__main__":
    import sys

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    try:
        if sys.argv[1:] == ["worker-idle"]:
            worker_idle()
        elif not sys.argv[1:]:
            inspect_database()
        else:
            raise RuntimeError("Unsupported preflight mode")
    except Refused as exc:
        print(f"Deployment preflight refused: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        # Never dump DB/adapter exception text, connection URLs, records or query parameters.
        print(
            f"Deployment preflight refused ({type(exc).__name__}); see the operator runbook",
            file=sys.stderr,
        )
        sys.exit(1)
