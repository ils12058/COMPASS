"""Opt-in ORG-4 disposable browser fixture/oracle; never an application endpoint.

Run with an empty compass_org4_* DB on loopback, tests.settings and an external
0600 state file. The browser authenticates through the ordinary login/TOTP APIs.
Only this test helper expires MFA or creates a competing, properly audited edit.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import secrets
import sys
import time
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    action, filename, *args = sys.argv[1:]
    path = Path(filename).resolve()
    assert os.environ.get("COMPASS_ORG4_DISPOSABLE") == "1", "Explicit disposable opt-in required"
    assert os.environ.get("POSTGRES_HOST") == "127.0.0.1"
    assert os.environ.get("POSTGRES_PORT") not in {None, "5432"}
    assert os.environ.get("POSTGRES_DB", "").startswith("compass_org4_")
    assert os.environ.get("DJANGO_SETTINGS_MODULE") == "tests.settings"
    assert not path.is_relative_to(Path(__file__).resolve().parents[2])
    if action == "prepare":
        assert not path.exists(), "Never replace an existing rehearsal state"
        from cryptography.fernet import Fernet

        keys = {
            name: Fernet.generate_key().decode()
            for name in (
                "AUTH_TOTP_ENCRYPTION_KEY",
                "INVENTORY_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS",
                "GUIDANCE_MESSAGE_ENCRYPTION_KEYS",
                "GUIDANCE_FOLLOWUP_ENCRYPTION_KEYS",
            )
        }
        state = {"keys": keys, "actors": {}, "password": secrets.token_urlsafe(24)}
    else:
        state = json.loads(path.read_text())
    os.environ.update(state["keys"])
    import django

    django.setup()
    from django.core.management import call_command
    from django.utils import timezone

    from compass.accounts.models import Role, User
    from compass.accounts.services import set_user_capability_override
    from compass.audit.models import AuditEvent
    from compass.authentication.crypto import decrypt_totp_secret, encrypt_totp_secret
    from compass.authentication.models import AuthSession, TOTPFactor
    from compass.organization import catalog_services as cs
    from compass.organization.models import Campus, College, Program, StudentAffiliation

    if action == "prepare":
        from django.db import transaction

        with contextlib.redirect_stdout(io.StringIO()):
            call_command("migrate", verbosity=0, interactive=False)
            assert not User.objects.exists() and not Campus.objects.exists()
            transaction.set_autocommit(False)
            call_command("sync_identity_policy", verbosity=0)
            call_command("sync_institutional_forms", verbosity=0)
            call_command(
                "initialize_organization_catalog",
                "--adopt",
                "--allow-empty-adoption",
                reference="Synthetic ORG-4 only; no institutional authority",
                verbosity=0,
            )
        import pyotp

        for key, role, catalog in (
            ("catalog", "GUIDANCE_SERVICES_STAFF", True),
            ("relationships", "IT_ADMIN", False),
            ("both", "IT_ADMIN", True),
            ("reader", "GUIDANCE_SERVICES_STAFF", False),
            ("student", "STUDENT", False),
        ):
            user = User.objects.create_user(
                email=f"org4-{key}@synthetic.invalid",
                password=state["password"],
                role=Role.objects.get(code=role),
                first_name="Synthetic",
                last_name=key,
            )
            if catalog:
                set_user_capability_override(
                    user=user,
                    capability="organization.catalog.manage",
                    effect="GRANT",
                    reason="Disposable engineering rehearsal only",
                )
            TOTPFactor.objects.create(
                user=user,
                encrypted_secret=encrypt_totp_secret(pyotp.random_base32()),
                confirmed_at=timezone.now(),
            )
            state["actors"][key] = {"id": str(user.pk), "email": user.email}
        # A real encrypted submitted Inventory is a historical oracle for UI Catalog edits.
        from compass.audit.context import AuditContext
        from compass.inventory.services import (
            ensure_current_inventory,
            replace_current_inventory,
            submit_current_inventory,
        )
        from tests.inventory_test_helpers import minimum_normalized_inventory_values
        from tests.test_inventory import configure_year

        c = Campus.objects.create(code="HISTORY", name="Historical Campus")
        k = College.objects.create(campus=c, code="HISTORY", name="Historical College")
        p = Program.objects.create(
            college=k,
            code="HISTORY",
            name="Historical Program",
            academic_classification="BACHELORS",
            year_level_policy_status="CONFIGURED",
            applicable_year_levels=[1, 2, 3, 4],
        )
        s = User.objects.get(pk=state["actors"]["student"]["id"])
        configure_year(User.objects.get(pk=state["actors"]["both"]["id"]))
        StudentAffiliation.objects.create(student=s, college=k)
        ensure_current_inventory(student=s, context=AuditContext.user(s))
        replace_current_inventory(
            student=s, values=minimum_normalized_inventory_values(program_id=p.pk, year_level=1)
        )
        item = submit_current_inventory(student=s, context=AuditContext.user(s))
        state["historical_program"] = str(p.pk)
        state["inventory"] = {
            field.attname: str(getattr(item, field.attname)) for field in item._meta.fields
        }
        with path.open("x") as output:
            os.chmod(path, 0o600)
            json.dump(state, output)
        transaction.commit()
        transaction.set_autocommit(True)
        print("Prepared synthetic actors, encrypted Inventory and initialization receipt")
    elif action == "serve":
        call_command("runserver", "127.0.0.1:8164", use_reloader=False)
    elif action == "totp":
        import pyotp

        factor = TOTPFactor.objects.get(user_id=state["actors"][args[0]]["id"])
        # Wait for a fresh real time step; do not reset replay protection or spoof time.
        while int(time.time()) // 30 <= (factor.last_verified_time_step or -1):
            time.sleep(0.2)
        print(pyotp.TOTP(decrypt_totp_secret(factor.encrypted_secret)).now())
    elif action == "expire-mfa":
        AuthSession.objects.filter(user_id=state["actors"]["catalog"]["id"]).update(
            mfa_verified_at=timezone.now() - timedelta(hours=2)
        )
    elif action == "competing-rename":
        from tests.catalog_test_helpers import authority, manager

        with contextlib.redirect_stdout(io.StringIO()):
            user, issued = manager()
        p = Program.objects.get(code=args[0], college__code="E2E_COLLEGE")
        cs.rename_program(
            **authority(user, issued),
            target_id=p.pk,
            expected_resource_version=p.resource_version,
            name=args[1],
        )
    elif action == "snapshot":
        from compass.inventory.models import StudentInventory

        item = StudentInventory.objects.get(student_id=state["actors"]["student"]["id"])
        assert state["inventory"] == {
            field.attname: str(getattr(item, field.attname)) for field in item._meta.fields
        }, "Submitted Inventory changed"
        result = {
            "historical_inventory_unchanged": True,
            "catalog": {},
            "events": list(
                AuditEvent.objects.filter(metadata__catalog_change=1).values(
                    "target_id", "actor_user_id", "action", "metadata"
                )
            ),
        }
        for model in (Campus, College, Program):
            result["catalog"][model._meta.model_name] = list(model.objects.values())
        print(json.dumps(result, default=str))
    elif action == "backup-manifest":
        from django.db import connection

        result = {}
        with connection.cursor() as cursor:
            for table in sorted(connection.introspection.table_names()):
                # Public application tables only, quoted from database introspection.
                cursor.execute(
                    f"SELECT to_jsonb(t)::text FROM {connection.ops.quote_name(table)} t "
                    "ORDER BY to_jsonb(t)::text"
                )
                rows = [row[0] for row in cursor.fetchall()]
                result[table] = {
                    "rows": len(rows),
                    "sha256": hashlib.sha256("\n".join(rows).encode()).hexdigest(),
                }
        print(json.dumps(result, sort_keys=True))
    else:
        raise ValueError("Unknown rehearsal action")


if __name__ == "__main__":
    main()
