import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("good_moral", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="goodmoralrequest",
            name="good_moral_issuance_shape",
        ),
        migrations.AlterField(
            model_name="goodmoralrequest",
            name="status",
            field=models.CharField(
                choices=[
                    ("REQUESTED", "Requested"),
                    ("ISSUED", "Issued"),
                    ("CANCELLED", "Cancelled"),
                ],
                default="REQUESTED",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="goodmoralrequest",
            name="cancellation_reason",
            field=models.TextField(blank=True, default="", max_length=1000),
        ),
        migrations.AddField(
            model_name="goodmoralrequest",
            name="cancelled_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="goodmoralrequest",
            name="cancelled_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="cancelled_good_moral_requests",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddConstraint(
            model_name="goodmoralrequest",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(
                        status__in=("REQUESTED", "CANCELLED"),
                        form_revision__isnull=True,
                        issued_at__isnull=True,
                        issued_by__isnull=True,
                        issued_by_name_snapshot="",
                        document_template_key__isnull=True,
                        document_template_version__isnull=True,
                    )
                    | (
                        models.Q(
                            status="ISSUED",
                            form_revision__isnull=False,
                            issued_at__isnull=False,
                            issued_by__isnull=False,
                            document_template_key__isnull=False,
                            document_template_version__isnull=False,
                        )
                        & ~models.Q(issued_by_name_snapshot="")
                    )
                ),
                name="good_moral_issuance_shape",
            ),
        ),
        migrations.AddConstraint(
            model_name="goodmoralrequest",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(
                        status__in=("REQUESTED", "ISSUED"),
                        cancelled_at__isnull=True,
                        cancellation_reason="",
                    )
                    | (
                        models.Q(status="CANCELLED", cancelled_at__isnull=False)
                        & ~models.Q(cancellation_reason="")
                    )
                ),
                name="good_moral_cancellation_shape",
            ),
        ),
    ]
