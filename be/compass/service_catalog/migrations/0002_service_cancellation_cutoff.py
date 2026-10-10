from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("service_catalog", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="service",
            name="cancellation_cutoff_minutes",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="service",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(("cancellation_cutoff_minutes__isnull", True))
                    | models.Q(("cancellation_cutoff_minutes__gte", 0))
                ),
                name="service_catalog_cancellation_cutoff_nonnegative",
            ),
        ),
    ]
