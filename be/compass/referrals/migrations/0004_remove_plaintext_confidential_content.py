"""Phase B: lock both tables, reconcile verified content, then remove plaintext.

Old services must remain stopped through migration and candidate activation. Reverse is atomic:
nullable plaintext columns first, verified restoration second, historical constraints last.
"""

from django.db import migrations, models

from compass.referrals.migrations._referral_confidential_content_v1 import (
    decrypt,
    encrypt,
    failure,
    keyring,
    plaintext,
)


def _models(apps):
    return apps.get_model("referrals", "Referral"), apps.get_model("referrals", "ReferralAction")


def _lock(apps, schema_editor):
    # Referral before ReferralAction, matching runtime parent-before-action locking.
    with schema_editor.connection.cursor() as cursor:
        for model in _models(apps):
            table = schema_editor.quote_name(model._meta.db_table)
            cursor.execute(f"LOCK TABLE {table} IN SHARE ROW EXCLUSIVE MODE")


def verify_content(apps, schema_editor):
    ring = keyring()
    _lock(apps, schema_editor)
    for model, column, action in zip(
        _models(apps),
        ("confidential_content_ciphertext", "remarks_ciphertext"),
        (False, True),
        strict=True,
    ):
        rows = model.objects.using(schema_editor.connection.alias)
        for row in rows.order_by("pk").iterator(chunk_size=200):
            current = plaintext(row, action=action)
            token = getattr(row, column)
            # A stale Referral's void state can change after Phase A. Validate the token's
            # original payload shape/content independently, then latest lifecycle on plaintext.
            if token:
                # An old writer may have voided a previously active Referral since Phase A.
                # Verify authenticated context and every field; latest lifecycle is verified
                # on authoritative plaintext above and on the replacement token below.
                previous = decrypt(ring, row, token, action=action, check_lifecycle=False)
                if previous == current:
                    continue
            token = encrypt(ring, row, current, action=action)
            if decrypt(ring, row, token, action=action) != current:
                raise failure(row, "malformed", action=action)
            rows.filter(pk=row.pk).update(**{column: token})


def restore_plaintext(apps, schema_editor):
    ring = keyring()
    _lock(apps, schema_editor)
    for model, column, action in zip(
        _models(apps),
        ("confidential_content_ciphertext", "remarks_ciphertext"),
        (False, True),
        strict=True,
    ):
        rows = model.objects.using(schema_editor.connection.alias)
        for row in rows.order_by("pk").iterator(chunk_size=200):
            payload = decrypt(ring, row, getattr(row, column), action=action)
            rows.filter(pk=row.pk).update(**payload)
            restored = rows.get(pk=row.pk)
            if plaintext(restored, action=action) != payload:
                raise failure(row, "malformed", action=action)


class Migration(migrations.Migration):
    dependencies = [("referrals", "0003_encrypt_confidential_content")]
    operations = [
        migrations.RunPython(verify_content, migrations.RunPython.noop),
        migrations.RemoveConstraint(model_name="referral", name="referral_void_shape"),
        # Reverse RemoveField must add nullable columns to populated ciphertext-only rows.
        migrations.AlterField(
            model_name="referral", name="reason", field=models.TextField(null=True)
        ),
        migrations.AlterField(
            model_name="referral",
            name="referrer_name",
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name="referral",
            name="status_note",
            field=models.TextField(blank=True, default="", null=True),
        ),
        migrations.AlterField(
            model_name="referral",
            name="void_reason",
            field=models.TextField(blank=True, default="", max_length=1000, null=True),
        ),
        migrations.AlterField(
            model_name="referralaction",
            name="remarks",
            field=models.TextField(blank=True, default="", null=True),
        ),
        migrations.RunPython(migrations.RunPython.noop, restore_plaintext),
        migrations.RemoveField(model_name="referral", name="reason"),
        migrations.RemoveField(model_name="referral", name="referrer_name"),
        migrations.RemoveField(model_name="referral", name="status_note"),
        migrations.RemoveField(model_name="referral", name="void_reason"),
        migrations.RemoveField(model_name="referralaction", name="remarks"),
        migrations.AlterField(
            model_name="referral",
            name="confidential_content_ciphertext",
            field=models.TextField(editable=False),
        ),
        migrations.AlterField(
            model_name="referralaction",
            name="remarks_ciphertext",
            field=models.TextField(editable=False),
        ),
        migrations.AddConstraint(
            model_name="referral",
            constraint=models.CheckConstraint(
                condition=~models.Q(confidential_content_ciphertext=""),
                name="referral_confidential_ciphertext_present",
            ),
        ),
        migrations.AddConstraint(
            model_name="referralaction",
            constraint=models.CheckConstraint(
                condition=~models.Q(remarks_ciphertext=""),
                name="referral_action_ciphertext_present",
            ),
        ),
    ]
