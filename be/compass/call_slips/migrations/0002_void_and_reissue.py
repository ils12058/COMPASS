import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("call_slips", "0001_initial"),
        ("referrals", "0002_void_provenance"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="callslip",
            name="referral",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="call_slips",
                to="referrals.referral",
            ),
        ),
        migrations.AddField(
            model_name="callslip",
            name="void_reason",
            field=models.TextField(blank=True, default="", max_length=1000),
        ),
        migrations.AddField(
            model_name="callslip",
            name="voided_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="callslip",
            name="voided_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="voided_call_slips",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddConstraint(
            model_name="callslip",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(voided_at__isnull=True, void_reason="")
                    | (models.Q(voided_at__isnull=False) & ~models.Q(void_reason=""))
                ),
                name="callslip_void_shape",
            ),
        ),
        migrations.AddConstraint(
            model_name="callslip",
            constraint=models.UniqueConstraint(
                fields=("referral",),
                condition=models.Q(referral__isnull=False, voided_at__isnull=True),
                name="callslip_active_referral_uniq",
            ),
        ),
    ]
