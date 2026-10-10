from django.db import migrations, models


PWD_FORWARD = {
    "HAS_PHYSICAL_DISADVANTAGE": "PWD",
    "NONE": "NON_PWD",
    "NOT_SPECIFIED": "NOT_SPECIFIED",
}
PWD_REVERSE = {
    "PWD": "HAS_PHYSICAL_DISADVANTAGE",
    "NON_PWD": "NONE",
    "NOT_SPECIFIED": "NOT_SPECIFIED",
}


def map_pwd_forward(apps, schema_editor):
    StudentInventory = apps.get_model("inventory", "StudentInventory")
    for old_value, new_value in PWD_FORWARD.items():
        StudentInventory.objects.filter(pwd_status=old_value).update(pwd_status=new_value)


def map_pwd_reverse(apps, schema_editor):
    StudentInventory = apps.get_model("inventory", "StudentInventory")
    for new_value, old_value in PWD_REVERSE.items():
        StudentInventory.objects.filter(pwd_status=new_value).update(pwd_status=old_value)


def restore_parent_life_status_on_reverse(apps, schema_editor):
    InventoryFamilyMember = apps.get_model("inventory", "InventoryFamilyMember")
    StudentSupportProfile = apps.get_model("student_support", "StudentSupportProfile")
    for profile in StudentSupportProfile.objects.all().iterator():
        if profile.father_life_status is not None:
            InventoryFamilyMember.objects.filter(
                inventory_id=profile.inventory_id,
                kind="FATHER",
            ).update(life_status=profile.father_life_status)
        if profile.mother_life_status is not None:
            InventoryFamilyMember.objects.filter(
                inventory_id=profile.inventory_id,
                kind="MOTHER",
            ).update(life_status=profile.mother_life_status)


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0003_inventory_profiling_normalization"),
        ("student_support", "0001_initial"),
    ]

    operations = [
        migrations.RenameField(
            model_name="studentinventory",
            old_name="physical_disadvantage_status",
            new_name="pwd_status",
        ),
        migrations.RunPython(map_pwd_forward, map_pwd_reverse),
        migrations.AlterField(
            model_name="studentinventory",
            name="pwd_status",
            field=models.CharField(
                blank=True,
                choices=[
                    ("PWD", "PWD"),
                    ("NON_PWD", "Non-PWD"),
                    ("NOT_SPECIFIED", "Not specified"),
                ],
                max_length=32,
                null=True,
            ),
        ),
        migrations.RunPython(
            migrations.RunPython.noop,
            restore_parent_life_status_on_reverse,
        ),
        migrations.RemoveField(
            model_name="inventoryfamilymember",
            name="life_status",
        ),
    ]
