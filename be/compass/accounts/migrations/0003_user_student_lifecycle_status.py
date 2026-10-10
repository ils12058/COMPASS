from django.db import migrations, models


def backfill_student_lifecycle_status(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(
        role__code="STUDENT",
        student_lifecycle_status__isnull=True,
    ).update(student_lifecycle_status="CURRENT")


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_user_reusable_profile_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="student_lifecycle_status",
            field=models.CharField(
                blank=True,
                choices=[
                    ("CURRENT", "Current"),
                    ("GRADUATED", "Graduated"),
                    ("FORMER", "Former"),
                ],
                max_length=16,
                null=True,
            ),
        ),
        migrations.RunPython(
            backfill_student_lifecycle_status,
            migrations.RunPython.noop,
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(student_lifecycle_status__isnull=True)
                    | models.Q(
                        student_lifecycle_status__in=["CURRENT", "GRADUATED", "FORMER"]
                    )
                ),
                name="accounts_user_student_lifecycle_valid",
            ),
        ),
    ]
