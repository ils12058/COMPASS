"""Remove the retired descriptive policy registry only when it is empty."""

from django.db import migrations


def refuse_populated_retention_policy(apps, schema_editor):
    model = apps.get_model("privacy_governance", "RetentionPolicy")
    count = model.objects.using(schema_editor.connection.alias).count()
    if count:
        raise RuntimeError(
            "Privacy Governance RetentionPolicy removal stopped because existing rows remain "
            f"(RetentionPolicy={count}). An explicit institutional data-disposition decision is "
            "required before retrying this migration."
        )


class Migration(migrations.Migration):
    dependencies = [("privacy_governance", "0003_simplify_privacy_governance_scope")]

    operations = [
        migrations.RunPython(
            refuse_populated_retention_policy,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.DeleteModel(name="RetentionPolicy"),
    ]
