"""Phase A: add ciphertext and backfill, preserving authoritative plaintext and metadata."""

from django.db import migrations, models

from compass.referrals.migrations._referral_confidential_content_v1 import (
    encrypt,
    keyring,
    plaintext,
)


def backfill(apps, schema_editor):
    ring = keyring()
    alias = schema_editor.connection.alias
    for model, column, action in (
        ("Referral", "confidential_content_ciphertext", False),
        ("ReferralAction", "remarks_ciphertext", True),
    ):
        rows = apps.get_model("referrals", model).objects.using(alias)
        for row in rows.order_by("pk").iterator(chunk_size=200):
            token = encrypt(ring, row, plaintext(row, action=action), action=action)
            rows.filter(pk=row.pk).update(**{column: token})


class Migration(migrations.Migration):
    dependencies = [("referrals", "0002_void_provenance")]
    operations = [
        migrations.AddField(
            model_name="referral",
            name="confidential_content_ciphertext",
            field=models.TextField(null=True, editable=False),
        ),
        migrations.AddField(
            model_name="referralaction",
            name="remarks_ciphertext",
            field=models.TextField(null=True, editable=False),
        ),
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
