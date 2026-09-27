"""Phase A of ADR-066: encrypt existing Routine Interview content next to its plaintext.

The plaintext columns stay authoritative until 0003 verifies every row and removes them. Any
invalid legacy row or a missing keyring aborts this migration before anything is committed.
"""

from django.db import migrations, models

from compass.routine_interviews.migrations._routine_content_v1 import (
    CIPHERTEXT_COLUMNS,
    LEGACY_COLUMNS,
    encrypt,
    keyring,
    legacy_payloads,
)


def encrypt_legacy_content(apps, schema_editor):
    RoutineInterview = apps.get_model("routine_interviews", "RoutineInterview")
    ring = keyring()
    rows = RoutineInterview.objects.order_by("pk").only("pk", *LEGACY_COLUMNS)
    for row in rows.iterator(chunk_size=200):
        # QuerySet.update() leaves updated_at and the workflow timestamps untouched.
        RoutineInterview.objects.filter(pk=row.pk).update(
            **{
                CIPHERTEXT_COLUMNS[section]: encrypt(ring, row.pk, section, payload)
                for section, payload in legacy_payloads(row).items()
            }
        )


class Migration(migrations.Migration):
    dependencies = [
        ("routine_interviews", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="routineinterview",
            name="student_intake_ciphertext",
            field=models.TextField(editable=False, null=True),
        ),
        migrations.AddField(
            model_name="routineinterview",
            name="counselor_evaluation_ciphertext",
            field=models.TextField(editable=False, null=True),
        ),
        migrations.RunPython(encrypt_legacy_content, migrations.RunPython.noop),
    ]
