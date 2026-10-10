"""Synthetic-only envelope/migration verification helpers."""

import importlib
import json
from io import StringIO

from cryptography.fernet import Fernet
from django.apps import apps
from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

K1 = Fernet.generate_key().decode()
K2 = Fernet.generate_key().decode()


def envelope(token):
    return json.loads(Fernet(K1).decrypt(token.encode()))


def mutated(token, fault):
    if fault == "missing":
        return None
    if fault == "empty":
        return ""
    if fault == "tamper":
        return token[:-4] + "xxxx"
    if fault == "truncate":
        return token[:30]
    if fault == "nonascii":
        return "PRIVATE-雪"
    if fault == "random":
        return "PRIVATE-broken"
    data = envelope(token)
    if fault == "schema":
        data["schema_version"] = 2
    elif fault == "boolean-version":
        data["schema_version"] = True
    elif fault == "binding":
        data[next(k for k in data if k not in {"schema_version", "payload"})] = "wrong"
    elif fault == "missing-field":
        data["payload"].pop(next(iter(data["payload"])))
    elif fault == "extra-field":
        data["payload"]["extra"] = "PRIVATE-extra"
    elif fault == "wrong-type":
        data["payload"][next(iter(data["payload"]))] = False
    elif fault == "null":
        data["payload"] = None
    elif fault == "nul":
        data["payload"][next(k for k in data["payload"] if k != "date_of_birth")] = "PRIVATE-\x00"
    return Fernet(K1).encrypt(json.dumps(data).encode()).decode()


FAULTS = [
    "missing",
    "empty",
    "tamper",
    "truncate",
    "nonascii",
    "random",
    "schema",
    "boolean-version",
    "binding",
    "missing-field",
    "extra-field",
    "wrong-type",
    "null",
    "nul",
]


def raw(model):
    with connection.cursor() as cursor:
        cursor.execute(f'SELECT * FROM "{model._meta.db_table}" ORDER BY id')
        names = [col.name for col in cursor.description]
        return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]


def columns(model):
    with connection.cursor() as cursor:
        return {
            col.name
            for col in connection.introspection.get_table_description(cursor, model._meta.db_table)
        }


def command(name, **options):
    out, err = StringIO(), StringIO()
    call_command(name, stdout=out, stderr=err, **options)
    return out.getvalue(), err.getvalue()


def state(target):
    return MigrationExecutor(connection).loader.project_state(target).apps


def migrate(target):
    MigrationExecutor(connection).migrate(target)


def metadata(model, column):
    return [{k: v for k, v in row.items() if k != column} for row in raw(model)]


def setup_legacy(app, before):
    assert connection.settings_dict["NAME"].startswith("test_")
    initial = MigrationExecutor(connection).loader.graph.leaf_nodes()
    migrate(before)
    return initial, state(before)


def cleanup_legacy(app, families, initial):
    with connection.cursor() as cursor:
        for family in reversed(families):
            table = apps.get_model(app, family)._meta.db_table
            cursor.execute(f'TRUNCATE "{table}" CASCADE')
    migrate(initial)


def fence_probe(module_name, app, families, metadata_column, monkeypatch, reverse):
    phase = importlib.import_module(module_name)
    original = phase.lock_tables
    calls = []

    def probe(registry, editor):
        original(registry, editor)
        other = connection.copy()
        try:
            import pytest
            from django.db import OperationalError

            for family in families:
                table = registry.get_model(app, family)._meta.db_table
                with other.cursor() as cursor:
                    cursor.execute("SET lock_timeout='100ms'")
                    with pytest.raises(OperationalError, match="lock timeout"):
                        cursor.execute(
                            f'UPDATE "{table}" SET "{metadata_column}"="{metadata_column}"'
                        )
                    with pytest.raises(OperationalError, match="lock timeout"):
                        cursor.execute(f'SELECT * FROM "{table}" FOR UPDATE')
        finally:
            other.close()
        calls.append(True)

    monkeypatch.setattr(phase, "lock_tables", probe)
    if reverse:
        monkeypatch.setattr(phase.Migration.operations[-1], "reverse_code", probe)
    return calls
