"""Loopback-only FAC-3 browser fixture. Creates/drops its own disposable PostgreSQL DB.

Not an application command, provider, activation switch or deployment entry point.
Run from be/: .venv/bin/python -m tests.faculty_portal_server /tmp/fac3-session.json
The 0600 manifest contains synthetic session cookies only; remove it after use.
"""

import json
import os
import signal
import sys
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql


def run():
    manifest = Path(sys.argv[1])
    database = "test_compass_fac3_" + uuid4().hex[:12]
    os.environ["DJANGO_SETTINGS_MODULE"] = "tests.settings"
    os.environ["POSTGRES_DB"] = database
    os.environ["CSRF_TRUSTED_ORIGINS"] = "http://localhost:3107,http://127.0.0.1:3107"
    os.environ["ALLOWED_HOSTS"] = "localhost,127.0.0.1,testserver"
    import django

    django.setup()
    from django.conf import settings
    from django.core.management import call_command
    from django.db import connections
    from pytest import MonkeyPatch

    from compass.authentication.sessions import create_auth_session
    from compass.institutional_forms.bootstrap import sync_institutional_forms
    from tests.faculty_referral_helpers import make_world

    config = settings.DATABASES["default"]
    assert config["NAME"] == database and config["HOST"] in {"127.0.0.1", "localhost"}
    admin = dict(
        dbname="postgres",
        user=config["USER"],
        password=config["PASSWORD"],
        host=config["HOST"],
        port=config["PORT"],
        autocommit=True,
    )
    with psycopg.connect(**admin) as owner:
        owner.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    patch = MonkeyPatch()
    manifest_written = False
    try:
        call_command("migrate", interactive=False, verbosity=0)
        sync_institutional_forms()
        world = make_world(patch)
        student_session = create_auth_session(world.student)
        data = {
            "faculty_cookie": world.issued.token,
            "other_faculty_cookie": world.other_issued.token,
            "student_cookie": student_session.token,
        }
        descriptor = os.open(manifest, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as handle:
            json.dump(data, handle)
        manifest_written = True

        def stop(*_args):
            raise KeyboardInterrupt

        signal.signal(signal.SIGTERM, stop)
        print("FAC-3 isolated synthetic approved-policy server ready on loopback:8033", flush=True)
        call_command("runserver", "127.0.0.1:8033", use_reloader=False, verbosity=0)
    finally:
        patch.undo()
        connections.close_all()
        if manifest_written:
            manifest.unlink(missing_ok=True)
        with psycopg.connect(**admin) as owner:
            owner.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database)))


if __name__ == "__main__":
    run()
