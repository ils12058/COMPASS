"""Backfill solo_parent_status=YES for legacy SOLO_PARENT civil-status rows (ADR-121).

Submitted Inventories are historical records: this migration never edits
``StudentInventory.civil_status_category`` or encrypted ``civil_status`` text,
and leaves non-SOLO_PARENT rows unanswered (``NULL``).
"""

from django.db import migrations


def backfill_solo_parent_status(apps, schema_editor):
    StudentInventory = apps.get_model("inventory", "StudentInventory")
    StudentSupportProfile = apps.get_model("student_support", "StudentSupportProfile")

    legacy_inventory_ids = list(
        StudentInventory.objects.filter(civil_status_category="SOLO_PARENT").values_list(
            "pk", flat=True
        )
    )
    if not legacy_inventory_ids:
        return

    StudentSupportProfile.objects.filter(
        inventory_id__in=legacy_inventory_ids,
        solo_parent_status__isnull=True,
    ).update(solo_parent_status="YES")

    existing_ids = set(
        StudentSupportProfile.objects.filter(inventory_id__in=legacy_inventory_ids).values_list(
            "inventory_id", flat=True
        )
    )
    missing = [
        StudentSupportProfile(inventory_id=inventory_id, solo_parent_status="YES")
        for inventory_id in legacy_inventory_ids
        if inventory_id not in existing_ids
    ]
    if missing:
        StudentSupportProfile.objects.bulk_create(missing)


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0002_civil_status_categories"),
        ("student_support", "0002_solo_parent_status"),
    ]

    operations = [
        migrations.RunPython(backfill_solo_parent_status, migrations.RunPython.noop),
    ]
