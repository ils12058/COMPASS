from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("organization", "0003_program"),
        ("inventory", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="studentinventory",
            name="program",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="student_inventories",
                to="organization.program",
            ),
        ),
        migrations.AddField(
            model_name="studentinventory",
            name="year_level",
            field=models.PositiveSmallIntegerField(
                blank=True,
                null=True,
                validators=[MinValueValidator(1), MaxValueValidator(10)],
            ),
        ),
        migrations.AddConstraint(
            model_name="studentinventory",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(year_level__isnull=True)
                    | (
                        models.Q(year_level__gte=1)
                        & models.Q(year_level__lte=10)
                    )
                ),
                name="inventory_year_level_range",
            ),
        ),
    ]
