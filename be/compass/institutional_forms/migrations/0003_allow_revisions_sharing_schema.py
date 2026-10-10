from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("institutional_forms", "0002_routine_interview_family"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="formrevision",
            name="institutional_forms_family_schema_version_uniq",
        ),
    ]
