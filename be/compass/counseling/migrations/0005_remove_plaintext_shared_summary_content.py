"""Phase B: verify under a writer-blocking lock before destroying plaintext schema.

This is a one-time deployment compatibility boundary: stop old application services before
applying it. The lock prevents unsafe writes during verification; it cannot make old code
compatible with the removed column after commit. Coordinate rollback with service downtime too.
"""

from django.db import migrations, models

from compass.counseling.migrations._shared_summary_content_v1 import (
    decrypt,
    encrypt,
    failure,
    keyring,
    validate_content,
)


def _lock(Summary, schema_editor):
    table = schema_editor.quote_name(Summary._meta.db_table)
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(f"LOCK TABLE {table} IN SHARE ROW EXCLUSIVE MODE")


def verify_encrypted_content(apps, schema_editor):
    Summary = apps.get_model("counseling", "CounselingSharedSummary")
    ring = keyring()
    _lock(Summary, schema_editor)
    rows = Summary.objects.using(schema_editor.connection.alias)
    for row in (
        rows.order_by("pk")
        .only("pk", "encounter_id", "content", "content_ciphertext")
        .iterator(chunk_size=200)
    ):
        current = validate_content(row.content, row.pk, row.encounter_id)
        token = row.content_ciphertext
        # Missing ciphertext is expected for rows inserted by an old release after Phase A.
        # A present but unverifiable token aborts; never conceal corruption by replacing it.
        if token and decrypt(ring, token, row.pk, row.encounter_id) == current:
            continue
        token = encrypt(ring, row.pk, row.encounter_id, current)
        if decrypt(ring, token, row.pk, row.encounter_id) != current:
            raise failure(row.pk, row.encounter_id, "malformed")
        rows.filter(pk=row.pk).update(content_ciphertext=token)


def restore_plaintext(apps, schema_editor):
    Summary = apps.get_model("counseling", "CounselingSharedSummary")
    ring = keyring()
    _lock(Summary, schema_editor)
    rows = Summary.objects.using(schema_editor.connection.alias)
    for row in (
        rows.order_by("pk")
        .only("pk", "encounter_id", "content_ciphertext")
        .iterator(chunk_size=200)
    ):
        content = decrypt(ring, row.content_ciphertext, row.pk, row.encounter_id)
        rows.filter(pk=row.pk).update(content=content)


class Migration(migrations.Migration):
    dependencies = [("counseling", "0004_encrypt_shared_summary_content")]
    operations = [
        migrations.RunPython(verify_encrypted_content, restore_plaintext),
        migrations.RemoveField(model_name="counselingsharedsummary", name="content"),
        migrations.AlterField(
            model_name="counselingsharedsummary",
            name="content_ciphertext",
            field=models.TextField(editable=False),
        ),
        migrations.AddConstraint(
            model_name="counselingsharedsummary",
            constraint=models.CheckConstraint(
                condition=~models.Q(content_ciphertext=""),
                name="counseling_summary_ciphertext_present",
            ),
        ),
    ]
