from django.db import migrations


def add_routine_interview_family(apps, schema_editor):
    FormFamily = apps.get_model("institutional_forms", "FormFamily")
    FormFamily.objects.get_or_create(
        key="routine_interview",
        defaults={"title": "Routine Interview Form"},
    )


class Migration(migrations.Migration):
    dependencies = [("institutional_forms", "0001_initial")]

    operations = [
        migrations.RunPython(add_routine_interview_family, migrations.RunPython.noop),
    ]
