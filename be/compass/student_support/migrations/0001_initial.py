import django.db.models.deletion
import uuid
from django.db import migrations, models


def copy_legacy_parent_life_status(apps, schema_editor):
    StudentInventory = apps.get_model("inventory", "StudentInventory")
    InventoryFamilyMember = apps.get_model("inventory", "InventoryFamilyMember")
    StudentSupportProfile = apps.get_model("student_support", "StudentSupportProfile")

    for inventory in StudentInventory.objects.all().iterator():
        father = (
            InventoryFamilyMember.objects.filter(
                inventory_id=inventory.pk,
                kind="FATHER",
            )
            .values_list("life_status", flat=True)
            .first()
        )
        mother = (
            InventoryFamilyMember.objects.filter(
                inventory_id=inventory.pk,
                kind="MOTHER",
            )
            .values_list("life_status", flat=True)
            .first()
        )
        StudentSupportProfile.objects.update_or_create(
            inventory_id=inventory.pk,
            defaults={
                "father_life_status": father,
                "mother_life_status": mother,
            },
        )


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("inventory", "0003_inventory_profiling_normalization"),
    ]

    operations = [
        migrations.CreateModel(
            name="StudentSupportProfile",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "four_ps_status",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("BENEFICIARY", "4Ps household beneficiary"),
                            ("NOT_BENEFICIARY", "Not a 4Ps household beneficiary"),
                            ("NOT_SPECIFIED", "Not specified"),
                        ],
                        max_length=24,
                        null=True,
                    ),
                ),
                (
                    "indigenous_peoples_status",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("MEMBER", "Indigenous Peoples member"),
                            ("NOT_MEMBER", "Not an Indigenous Peoples member"),
                            ("NOT_SPECIFIED", "Not specified"),
                        ],
                        max_length=24,
                        null=True,
                    ),
                ),
                (
                    "mother_life_status",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("LIVING", "Living"),
                            ("DECEASED", "Deceased"),
                            ("NOT_SPECIFIED", "Not specified"),
                        ],
                        max_length=24,
                        null=True,
                    ),
                ),
                (
                    "father_life_status",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("LIVING", "Living"),
                            ("DECEASED", "Deceased"),
                            ("NOT_SPECIFIED", "Not specified"),
                        ],
                        max_length=24,
                        null=True,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "inventory",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="support_profile",
                        to="inventory.studentinventory",
                    ),
                ),
            ],
            options={"default_permissions": ()},
        ),
        migrations.RunPython(copy_legacy_parent_life_status, migrations.RunPython.noop),
    ]
