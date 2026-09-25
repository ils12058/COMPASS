"""Keep persisted capability identity while clarifying reference-read authority."""

from django.db import migrations


RENAMES = (
    ("organization.view", "organization.structure.view"),
    ("services.view", "services.catalog.view"),
)


def _rename(apps, schema_editor, *, reverse=False):
    Capability = apps.get_model("accounts", "Capability")
    database = schema_editor.connection.alias
    for old_code, new_code in RENAMES:
        source_code, target_code = (new_code, old_code) if reverse else (old_code, new_code)
        rows = Capability.objects.using(database).filter(
            code__in=(source_code, target_code)
        )
        codes = set(rows.values_list("code", flat=True))
        if source_code in codes and target_code in codes:
            raise RuntimeError(
                f"Cannot rename capability {source_code} to {target_code}: both rows exist; "
                "reconcile grants and overrides before migrating."
            )
        if source_code in codes:
            rows.filter(code=source_code).update(code=target_code)


def forwards(apps, schema_editor):
    _rename(apps, schema_editor)


def backwards(apps, schema_editor):
    _rename(apps, schema_editor, reverse=True)


class Migration(migrations.Migration):
    dependencies = [("accounts", "0005_user_institutional_id")]

    operations = [migrations.RunPython(forwards, backwards)]
