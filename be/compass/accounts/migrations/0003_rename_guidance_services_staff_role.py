"""Rename the persisted Guidance Services Staff role to Guidance Office Assistant in place."""

from django.db import migrations

OLD_CODE = "GUIDANCE_SERVICES_STAFF"
OLD_NAME = "Guidance Services Staff"
NEW_CODE = "GUIDANCE_OFFICE_ASSISTANT"
NEW_NAME = "Guidance Office Assistant"


def _rename(role_model, *, alias, old_code, new_code, new_name):
    rows = role_model.objects.using(alias)
    # Fence identity writers; decide only after both row identities are known.
    existing = set(
        rows.select_for_update()
        .filter(code__in=(old_code, new_code))
        .values_list("code", flat=True)
    )
    if old_code not in existing:
        return
    if new_code in existing:
        raise RuntimeError(
            "Guidance Office Assistant role collision: both "
            f"{old_code} and {new_code} rows exist; migration stopped."
        )
    # The primary key survives, so users, grants, overrides and links stay attached.
    rows.filter(code=old_code).update(code=new_code, name=new_name)


def rename_role(apps, schema_editor):
    _rename(
        apps.get_model("accounts", "Role"),
        alias=schema_editor.connection.alias,
        old_code=OLD_CODE,
        new_code=NEW_CODE,
        new_name=NEW_NAME,
    )


def reverse_role(apps, schema_editor):
    _rename(
        apps.get_model("accounts", "Role"),
        alias=schema_editor.connection.alias,
        old_code=NEW_CODE,
        new_code=OLD_CODE,
        new_name=OLD_NAME,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_student_session_summary_capabilities"),
    ]
    operations = [
        migrations.RunPython(rename_role, reverse_code=reverse_role),
    ]
