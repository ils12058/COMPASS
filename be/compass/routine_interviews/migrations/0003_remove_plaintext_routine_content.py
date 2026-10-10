"""Phase B of ADR-066: prove every row is encrypted, then remove the plaintext columns.

Everything below runs in one transaction. Verification happens first, under a lock that blocks
writers, so a failure rolls back before any plaintext column is dropped. The 1–10 rating ranges
move from PostgreSQL check constraints to the API schema and service validation.
"""

from django.db import migrations, models

from compass.routine_interviews.migrations._routine_content_v1 import (
    CIPHERTEXT_COLUMNS,
    LEGACY_COLUMNS,
    decrypt,
    encrypt,
    failure,
    keyring,
    legacy_payloads,
)


def verify_encrypted_content(apps, schema_editor):
    RoutineInterview = apps.get_model("routine_interviews", "RoutineInterview")
    ring = keyring()
    table = schema_editor.quote_name(RoutineInterview._meta.db_table)
    with schema_editor.connection.cursor() as cursor:
        # Writers still running the previous release wait here instead of changing plaintext
        # after it is verified; the column drops below then take an exclusive lock.
        cursor.execute(f"LOCK TABLE {table} IN SHARE ROW EXCLUSIVE MODE")

    columns = ("pk", *LEGACY_COLUMNS, *CIPHERTEXT_COLUMNS.values())
    for row in RoutineInterview.objects.order_by("pk").only(*columns).iterator(chunk_size=200):
        updates = {}
        for section, payload in legacy_payloads(row).items():
            column = CIPHERTEXT_COLUMNS[section]
            if decrypt(ring, getattr(row, column), row.pk, section) == payload:
                continue
            # Missing or stale ciphertext, such as a write by the previous release after 0002, is
            # re-encrypted from the still-authoritative plaintext and verified before use.
            token = encrypt(ring, row.pk, section, payload)
            if decrypt(ring, token, row.pk, section) != payload:
                raise failure(row.pk, section, "encrypted content did not verify")
            updates[column] = token
        if updates:
            RoutineInterview.objects.filter(pk=row.pk).update(**updates)


def restore_plaintext(apps, schema_editor):
    """Controlled rollback only: write verified content back into the restored columns."""

    RoutineInterview = apps.get_model("routine_interviews", "RoutineInterview")
    ring = keyring()
    columns = ("pk", *CIPHERTEXT_COLUMNS.values())
    for row in RoutineInterview.objects.order_by("pk").only(*columns).iterator(chunk_size=200):
        values = {}
        for section, column in CIPHERTEXT_COLUMNS.items():
            payload = decrypt(ring, getattr(row, column), row.pk, section)
            if payload is None:
                raise failure(row.pk, section, "encrypted content could not be verified")
            values.update(payload)
        RoutineInterview.objects.filter(pk=row.pk).update(**values)


class Migration(migrations.Migration):
    dependencies = [
        ("routine_interviews", "0002_encrypt_routine_content"),
    ]

    operations = [
        migrations.RunPython(verify_encrypted_content, restore_plaintext),
        *[
            migrations.RemoveConstraint(
                model_name="routineinterview",
                name=f"routine_{prefix}_rating_range",
            )
            for prefix in ("academic", "physical", "social", "spiritual", "financial", "emotional")
        ],
        *[
            migrations.RemoveField(model_name="routineinterview", name=column)
            for column in LEGACY_COLUMNS
        ],
        migrations.AlterField(
            model_name="routineinterview",
            name="student_intake_ciphertext",
            field=models.TextField(editable=False),
        ),
        migrations.AlterField(
            model_name="routineinterview",
            name="counselor_evaluation_ciphertext",
            field=models.TextField(editable=False),
        ),
        migrations.AddConstraint(
            model_name="routineinterview",
            constraint=models.CheckConstraint(
                condition=~models.Q(student_intake_ciphertext=""),
                name="routine_intake_ciphertext_present",
            ),
        ),
        migrations.AddConstraint(
            model_name="routineinterview",
            constraint=models.CheckConstraint(
                condition=~models.Q(counselor_evaluation_ciphertext=""),
                name="routine_evaluation_ciphertext_present",
            ),
        ),
    ]
