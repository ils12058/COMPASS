"""Atomic writer-fenced reconciliation, removal and exact controlled reverse."""

from datetime import date
from django.db import migrations, models
from compass.accounts.migrations._account_profile_confidential_content_v1 import (
    FAMILIES,
    COLUMN,
    keyring,
    encrypt,
    decrypt,
    plaintext,
    failure,
)


def lock_tables(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        for family in FAMILIES:
            table = schema_editor.quote_name(apps.get_model("accounts", family)._meta.db_table)
            cursor.execute(f"LOCK TABLE {table} IN EXCLUSIVE MODE")


def verify_content(apps, schema_editor):
    lock_tables(apps, schema_editor)
    ring = keyring()
    for family in FAMILIES:
        rows = apps.get_model("accounts", family).objects.using(schema_editor.connection.alias)
        for row in rows.order_by("pk").iterator(chunk_size=200):
            current = plaintext(row, family)
            token = getattr(row, COLUMN)
            # Present corrupt/unsupported/rebound payloads must abort, never repair.
            if token is not None and token != "":
                if decrypt(ring, row, token, family) == current:
                    continue
            token = encrypt(ring, row, current, family)
            if decrypt(ring, row, token, family) != current:
                raise failure(row, "malformed", family)
            rows.filter(pk=row.pk).update(**{COLUMN: token})


def restore_plaintext(apps, schema_editor):
    ring = keyring()
    for family in FAMILIES:
        rows = apps.get_model("accounts", family).objects.using(schema_editor.connection.alias)
        for row in rows.order_by("pk").iterator(chunk_size=200):
            expected = decrypt(ring, row, getattr(row, COLUMN), family)
            restored = dict(expected)
            if "date_of_birth" in restored and restored["date_of_birth"] is not None:
                restored["date_of_birth"] = date.fromisoformat(restored["date_of_birth"])
            rows.filter(pk=row.pk).update(**restored)
            if plaintext(rows.get(pk=row.pk), family) != expected:
                raise failure(row, "malformed", family)


PLAIN_FIELDS = [
    ("user", "date_of_birth", models.DateField(blank=True, null=True)),
    ("user", "civil_status", models.CharField(max_length=80, blank=True, default="", null=True)),
    ("user", "contact_number", models.CharField(max_length=64, blank=True, default="", null=True)),
    ("user", "current_address", models.TextField(blank=True, default="", null=True)),
    ("user", "permanent_address", models.TextField(blank=True, default="", null=True)),
]


class Migration(migrations.Migration):
    dependencies = [("accounts", "0007_encrypt_confidential_content")]
    operations = (
        [migrations.RunPython(verify_content, migrations.RunPython.noop)]
        + [
            migrations.AlterField(model_name=model, name=name, field=field)
            for model, name, field in PLAIN_FIELDS
        ]
        + [migrations.RunPython(migrations.RunPython.noop, restore_plaintext)]
        + [migrations.RemoveField(model_name=model, name=name) for model, name, _ in PLAIN_FIELDS]
        + [
            migrations.AlterField(
                model_name=family.lower(), name=COLUMN, field=models.TextField(editable=False)
            )
            for family in FAMILIES
        ]
        + [
            migrations.AddConstraint(
                model_name=family.lower(),
                constraint=models.CheckConstraint(
                    condition=~models.Q(**{COLUMN: ""}),
                    name="accounts_user_profile_cipher_nonempty",
                ),
            )
            for family in FAMILIES
        ]
        # Reverse executes this first, fencing writers before restored-column DDL.
        + [migrations.RunPython(migrations.RunPython.noop, lock_tables)]
    )
