# ruff: noqa: F811
"""Opt-in disposable pg_dump/restore rehearsal, including a real post-backup gap.

No recovery/activation command is added to the application. The restored clone is
never attached to an app server and is dropped in finally. No triggers are disabled.
"""

import os
import subprocess
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from django.db import connection
from psycopg import sql

from compass.audit.models import AuditEvent
from compass.feedback.models import FeedbackOpportunity
from compass.good_moral.models import (
    GoodMoralReceiptAssignment,
    GoodMoralReceiptIdentity,
    GoodMoralReceiptImportBatch,
    GoodMoralReceiptLedger,
    GoodMoralReceiptMutation,
    GoodMoralReceiptVerification,
    GoodMoralRequest,
)
from compass.notifications.models import Notification
from tests.test_good_moral import auth_client
from tests.test_good_moral_authenticated_integration import (
    actors,  # noqa: F401
    approved,  # noqa: F401
    create,
    record,
)
from tests.test_good_moral_verification import issue, prepare, verify

pytestmark = pytest.mark.django_db(transaction=True)


def test_disposable_backup_restore_preserves_evidence_but_loses_later_claims(actors, tmp_path):
    if os.environ.get("COMPASS_GM_RECOVERY_REHEARSAL") != "1":
        pytest.skip("Explicit disposable PostgreSQL restore opt-in required")
    config = connection.settings_dict
    assert config["HOST"] in {"127.0.0.1", "localhost"}
    assert config["NAME"].startswith("test_")
    binaries = Path(os.environ["COMPASS_GM_PG_BIN"])
    clone_name = f"gm4_restore_{uuid4().hex}_synthetic"
    credentials = {
        "host": config["HOST"],
        "port": config["PORT"],
        "user": config["USER"],
        "password": config["PASSWORD"],
    }
    student, inspector, counselor = actors
    staff = auth_client(inspector)
    saved = record(staff, create(auth_client(student), "GRADUATE"), "GM4-BEFORE-BACKUP")
    item = GoodMoralRequest.objects.get(pk=saved["id"])
    verify(item, inspector)
    prepare(item, inspector)
    issue(item, counselor)
    retained = [
        GoodMoralRequest,
        GoodMoralReceiptIdentity,
        GoodMoralReceiptAssignment,
        GoodMoralReceiptMutation,
        GoodMoralReceiptImportBatch,
        GoodMoralReceiptLedger,
        GoodMoralReceiptVerification,
        AuditEvent,
        Notification,
        FeedbackOpportunity,
    ]
    # Canonical full-row values, including source form/template/issuer and fee
    # snapshots. Normalize driver JSON decoding and connection timezone only.
    expected = {}
    with connection.cursor() as cursor:
        cursor.execute("SET TIME ZONE 'UTC'")
        for model in retained:
            table = model._meta.db_table
            cursor.execute(f'SELECT to_jsonb(t)::text FROM "{table}" t ORDER BY 1')
            expected[table] = cursor.fetchall()
    environment = {
        "PATH": os.environ.get("PATH", ""),
        "PGPASSWORD": config["PASSWORD"],
    }
    backup = tmp_path / "synthetic.dump"
    arguments = ["-h", config["HOST"], "-p", str(config["PORT"]), "-U", config["USER"]]
    subprocess.run(
        [str(binaries / "pg_dump"), *arguments, "-Fc", "-f", str(backup), config["NAME"]],
        env=environment,
        check=True,
        capture_output=True,
        timeout=45,
    )
    later = record(staff, create(auth_client(student), "GRADUATE"), "GM4-AFTER-BACKUP")
    assert GoodMoralReceiptIdentity.objects.filter(normalized_key="GM4-AFTER-BACKUP").exists()
    with psycopg.connect(dbname="postgres", **credentials, autocommit=True) as admin:
        admin.execute(
            sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(clone_name))
        )
        try:
            subprocess.run(
                [
                    str(binaries / "pg_restore"),
                    *arguments,
                    "--no-owner",
                    "--no-privileges",
                    "--exit-on-error",
                    "-d",
                    clone_name,
                    str(backup),
                ],
                env=environment,
                check=True,
                capture_output=True,
                timeout=45,
            )
            with psycopg.connect(dbname=clone_name, **credentials) as restored:
                restored.execute("SET TIME ZONE 'UTC'")
                for table, rows in expected.items():
                    actual = restored.execute(
                        sql.SQL("SELECT to_jsonb(t)::text FROM {} t ORDER BY 1").format(
                            sql.Identifier(table)
                        )
                    ).fetchall()
                    assert actual == rows, table
                assert restored.execute(
                    "SELECT count(*) FROM good_moral_goodmoralreceiptidentity "
                    "WHERE normalized_key = %s",
                    ("GM4-AFTER-BACKUP",),
                ).fetchone() == (0,)
                assert restored.execute(
                    "SELECT count(*) FROM good_moral_goodmoralrequest WHERE id = %s",
                    (later["id"],),
                ).fetchone() == (0,)
                guards = restored.execute(
                    "SELECT count(*) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid "
                    "WHERE c.relname LIKE 'good_moral_%%' AND NOT t.tgisinternal "
                    "AND t.tgenabled <> 'D'",
                ).fetchone()[0]
                assert guards > 0
                # Restore retained ACTIVE too: a snapshot cannot know later physical
                # claims. Keep this clone disconnected; no unsafe write is reopened.
                assert restored.execute(
                    "SELECT mode FROM good_moral_goodmoralreceiptledger WHERE id=1"
                ).fetchone() == ("ACTIVE",)
        finally:
            admin.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(clone_name))
            )
