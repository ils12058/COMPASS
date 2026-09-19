import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0002_inventory_academic_context"),
    ]

    operations = [
        migrations.AddField(
            model_name="studentinventory",
            name="civil_status_category",
            field=models.CharField(
                blank=True,
                choices=[
                    ("SINGLE", "Single"),
                    ("MARRIED", "Married"),
                    ("SOLO_PARENT", "Solo Parent"),
                    ("OTHER", "Other"),
                    ("NOT_SPECIFIED", "Not specified"),
                ],
                max_length=32,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="studentinventory",
            name="current_religion_category",
            field=models.CharField(
                blank=True,
                choices=[
                    ("ROMAN_CATHOLIC", "Roman Catholic"),
                    ("BORN_AGAIN", "Born Again"),
                    ("IGLESIA_NI_CRISTO", "Iglesia Ni Cristo"),
                    ("MORMON", "Mormon"),
                    ("JEHOVAHS_WITNESS", "Jehovah's Witness"),
                    ("SEVENTH_DAY_ADVENTIST", "Seventh Day Adventist"),
                    ("CHURCH_OF_CHRIST", "Church Of Christ"),
                    ("EVANGELICAL_CHRISTIAN", "Evangelical Christian"),
                    ("MGCI", "MGCI"),
                    ("BAPTIST", "Baptist"),
                    ("PMCC", "PMCC"),
                    ("NONE", "None"),
                    ("OTHER", "Other"),
                    ("NOT_SPECIFIED", "Not specified"),
                ],
                max_length=40,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="studentinventory",
            name="parent_status_category",
            field=models.CharField(
                blank=True,
                choices=[
                    ("MARRIED", "Married"),
                    ("ANNULLED", "Annulled"),
                    ("LEGALLY_SEPARATED", "Legally Separated"),
                    ("TEMPORARILY_SEPARATED", "Temporarily Separated"),
                    ("PERMANENTLY_SEPARATED", "Permanently Separated"),
                    ("LIVING_TOGETHER", "Living Together"),
                    ("WIDOWED", "Widowed"),
                    ("MOTHER_WITH_OTHER_PARTNER", "Mother with other partner"),
                    ("FATHER_WITH_OTHER_PARTNER", "Father with other partner"),
                    ("MOTHER_OFW", "Mother OFW"),
                    ("FATHER_OFW", "Father OFW"),
                    ("OTHER", "Other"),
                    ("NOT_SPECIFIED", "Not specified"),
                ],
                max_length=40,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="studentinventory",
            name="physical_disadvantage_status",
            field=models.CharField(
                blank=True,
                choices=[
                    ("NONE", "None"),
                    ("HAS_PHYSICAL_DISADVANTAGE", "Has physical disadvantage"),
                    ("NOT_SPECIFIED", "Not specified"),
                ],
                max_length=32,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="inventoryfamilymember",
            name="life_status",
            field=models.CharField(
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
        migrations.AddField(
            model_name="inventoryfamilymember",
            name="occupation_category",
            field=models.CharField(
                blank=True,
                choices=[
                    ("GOVERNMENT_EMPLOYEE", "Government Employee"),
                    ("PRIVATE_EMPLOYEE", "Private Employee"),
                    ("LABORER", "Laborer"),
                    ("FARMER", "Farmer"),
                    ("SELF_EMPLOYED", "Self Employed"),
                    ("OFW", "OFW"),
                    ("NONE", "None"),
                    ("OTHER", "Other"),
                    ("NOT_SPECIFIED", "Not specified"),
                ],
                max_length=32,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="inventoryfamilymember",
            name="annual_income_status",
            field=models.CharField(
                blank=True,
                choices=[
                    ("REPORTED", "Reported"),
                    ("NONE", "None"),
                    ("NOT_SPECIFIED", "Not specified"),
                ],
                max_length=24,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="inventorytransportationentry",
            name="frequency_category",
            field=models.CharField(
                blank=True,
                choices=[
                    ("DAILY", "Daily"),
                    ("SEVERAL_TIMES_A_WEEK", "Several times a week"),
                    ("WEEKLY", "Weekly"),
                    ("OCCASIONAL", "Occasional"),
                    ("OTHER", "Other"),
                    ("NOT_SPECIFIED", "Not specified"),
                ],
                max_length=32,
                null=True,
            ),
        ),
        migrations.CreateModel(
            name="InventoryGeographicLocation",
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
                    "kind",
                    models.CharField(
                        choices=[("CURRENT", "Current"), ("PERMANENT", "Permanent")],
                        max_length=16,
                    ),
                ),
                ("not_specified", models.BooleanField(default=False)),
                ("region_psgc_code", models.CharField(blank=True, default="", max_length=32)),
                ("region_name_snapshot", models.CharField(blank=True, default="", max_length=160)),
                ("province_psgc_code", models.CharField(blank=True, default="", max_length=32)),
                (
                    "province_name_snapshot",
                    models.CharField(blank=True, default="", max_length=160),
                ),
                (
                    "city_municipality_psgc_code",
                    models.CharField(blank=True, default="", max_length=32),
                ),
                (
                    "city_municipality_name_snapshot",
                    models.CharField(blank=True, default="", max_length=160),
                ),
                ("barangay_psgc_code", models.CharField(blank=True, default="", max_length=32)),
                (
                    "barangay_name_snapshot",
                    models.CharField(blank=True, default="", max_length=160),
                ),
                (
                    "inventory",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="geographic_locations",
                        to="inventory.studentinventory",
                    ),
                ),
            ],
            options={
                "ordering": ("kind", "id"),
                "default_permissions": (),
            },
        ),
        migrations.AddConstraint(
            model_name="inventorygeographiclocation",
            constraint=models.UniqueConstraint(
                fields=("inventory", "kind"),
                name="inventory_geographic_location_kind_uniq",
            ),
        ),
        migrations.AddConstraint(
            model_name="inventoryfamilymember",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(("annual_income_previous_year__isnull", True))
                    | models.Q(("annual_income_previous_year__gte", 0))
                ),
                name="inventory_family_income_nonnegative",
            ),
        ),
        migrations.AddConstraint(
            model_name="inventorytransportationentry",
            constraint=models.CheckConstraint(
                condition=models.Q(("fare__isnull", True)) | models.Q(("fare__gte", 0)),
                name="inventory_transport_fare_nonnegative",
            ),
        ),
    ]
