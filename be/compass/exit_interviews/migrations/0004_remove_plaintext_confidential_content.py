"""Phase B and controlled reverse: fence all three tables; verified content only.

Services/operator writers must remain stopped until compatible code activation. Atomic PostgreSQL
DDL restores nullable plaintext columns before reverse verification, and historical fields last.
"""

from django.db import migrations, models

from compass.exit_interviews.migrations._exit_interview_confidential_content_v1 import (
    FAMILIES,
    LIMITS,
    decrypt,
    encrypt,
    failure,
    keyring,
    plaintext,
)


def _lock(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        for name, _column, _kind in FAMILIES:
            table = schema_editor.quote_name(apps.get_model("exit_interviews", name)._meta.db_table)
            cursor.execute(f"LOCK TABLE {table} IN SHARE ROW EXCLUSIVE MODE")


def verify_content(apps, schema_editor):
    ring = keyring()
    _lock(apps, schema_editor)
    for name, column, kind in FAMILIES:
        rows = apps.get_model("exit_interviews", name).objects.using(schema_editor.connection.alias)
        for row in rows.order_by("pk").iterator(chunk_size=200):
            current = plaintext(row, kind)
            token = getattr(row, column)
            if token:
                # Old code can change coded choices together with OTHER text after Phase A.
                # Authenticate original schema/fields independently of today's structured choices.
                previous = decrypt(ring, row, token, kind, check_consistency=False)
                if previous == current:
                    continue
            token = encrypt(ring, row, current, kind)
            if decrypt(ring, row, token, kind) != current:
                raise failure(row, "malformed", kind)
            rows.filter(pk=row.pk).update(**{column: token})


def restore_plaintext(apps, schema_editor):
    ring = keyring()
    _lock(apps, schema_editor)
    for name, column, kind in FAMILIES:
        rows = apps.get_model("exit_interviews", name).objects.using(schema_editor.connection.alias)
        for row in rows.order_by("pk").iterator(chunk_size=200):
            payload = decrypt(ring, row, getattr(row, column), kind)
            rows.filter(pk=row.pk).update(**payload)
            if plaintext(rows.get(pk=row.pk), kind) != payload:
                raise failure(row, "malformed", kind)


def _nullable_main_field(name):
    if name == "email_snapshot":
        return models.EmailField(max_length=320, blank=True, default="", null=True)
    if name == "contact_number_snapshot":
        return models.CharField(max_length=64, blank=True, default="", null=True)
    return models.TextField(blank=True, default="", null=True)


PLAIN_FIELDS = [("exitinterview", name, _nullable_main_field(name)) for name in LIMITS] + [
    (
        "exitinterviewopportunity",
        "note",
        models.CharField(max_length=1000, blank=True, default="", null=True),
    ),
    (
        "exitinterviewreopenevent",
        "reason",
        models.TextField(max_length=1000, null=True),
    ),
]
CONSTRAINTS = (
    "exit_confidential_ciphertext_present",
    "exit_opp_note_ciphertext_present",
    "exit_reopen_ciphertext_present",
)


class Migration(migrations.Migration):
    dependencies = [("exit_interviews", "0003_encrypt_confidential_content")]
    operations = (
        [migrations.RunPython(verify_content, migrations.RunPython.noop)]
        + [
            migrations.AlterField(model_name=model, name=name, field=field)
            for model, name, field in PLAIN_FIELDS
        ]
        + [migrations.RunPython(migrations.RunPython.noop, restore_plaintext)]
        + [
            migrations.RemoveField(model_name=model, name=name)
            for model, name, _field in PLAIN_FIELDS
        ]
        + [
            migrations.AlterField(
                model_name=name.lower(),
                name=column,
                field=models.TextField(editable=False),
            )
            for name, column, _kind in FAMILIES
        ]
        + [
            migrations.AddConstraint(
                model_name=name.lower(),
                constraint=models.CheckConstraint(
                    condition=~models.Q(**{column: ""}), name=constraint
                ),
            )
            for (name, column, _kind), constraint in zip(FAMILIES, CONSTRAINTS, strict=True)
        ]
    )
