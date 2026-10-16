"""Synthetic-only envelope verification helpers."""

import json
from io import StringIO

from cryptography.fernet import Fernet
from django.core.management import call_command
from django.db import connection

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


def metadata(model, column):
    return [{k: v for k, v in row.items() if k != column} for row in raw(model)]
