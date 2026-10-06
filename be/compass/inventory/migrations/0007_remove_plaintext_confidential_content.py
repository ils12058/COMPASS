"""Phase B and controlled reverse: fence all seven tables; verified content only.

Services/operator writers must remain stopped until compatible code activation. Atomic PostgreSQL
DDL restores nullable plaintext columns before reverse verification, and historical fields last.
"""

from datetime import date

from django.contrib.postgres.fields import ArrayField
from django.db import migrations, models

from compass.inventory.migrations._inventory_confidential_content_v1 import (
    FAMILIES,
    decrypt,
    encrypt,
    failure,
    keyring,
    plaintext,
)


def _lock(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        for name, _column, _kind in FAMILIES:
            table = schema_editor.quote_name(apps.get_model("inventory", name)._meta.db_table)
            cursor.execute(f"LOCK TABLE {table} IN SHARE ROW EXCLUSIVE MODE")


def verify_content(apps, schema_editor):
    ring = keyring()
    _lock(apps, schema_editor)
    for name, column, _relation in FAMILIES:
        rows = apps.get_model("inventory", name).objects.using(schema_editor.connection.alias)
        for row in rows.order_by("pk").iterator(chunk_size=200):
            current = plaintext(row, name)
            token = getattr(row, column)
            if token:
                # Old code can change coded choices together with OTHER text after Phase A.
                # Authenticate original schema/fields independently of today's structured choices.
                previous = decrypt(ring, row, token, name, check_consistency=False)
                if previous == current:
                    continue
            token = encrypt(ring, row, current, name)
            if decrypt(ring, row, token, name) != current:
                raise failure(row, "malformed", name)
            rows.filter(pk=row.pk).update(**{column: token})


def restore_plaintext(apps, schema_editor):
    ring = keyring()
    _lock(apps, schema_editor)
    for name, column, _relation in FAMILIES:
        rows = apps.get_model("inventory", name).objects.using(schema_editor.connection.alias)
        for row in rows.order_by("pk").iterator(chunk_size=200):
            payload = decrypt(ring, row, getattr(row, column), name)
            restored = dict(payload)
            if "date_of_birth" in restored and restored["date_of_birth"] is not None:
                restored["date_of_birth"] = date.fromisoformat(restored["date_of_birth"])
            rows.filter(pk=row.pk).update(**restored)
            if plaintext(rows.get(pk=row.pk), name) != payload:
                raise failure(row, "malformed", name)


PLAIN_FIELDS = [
    (
        "studentinventory",
        "nickname",
        models.CharField(max_length=100, blank=True, default="", null=True),
    ),
    (
        "studentinventory",
        "place_of_birth",
        models.CharField(max_length=160, blank=True, default="", null=True),
    ),
    (
        "studentinventory",
        "nationality",
        models.CharField(max_length=100, blank=True, default="", null=True),
    ),
    (
        "studentinventory",
        "birth_order_among_siblings",
        models.CharField(max_length=64, blank=True, default="", null=True),
    ),
    (
        "studentinventory",
        "civil_status",
        models.CharField(max_length=80, blank=True, default="", null=True),
    ),
    ("studentinventory", "current_address", models.TextField(blank=True, default="", null=True)),
    ("studentinventory", "permanent_address", models.TextField(blank=True, default="", null=True)),
    (
        "studentinventory",
        "contact_number",
        models.CharField(max_length=64, blank=True, default="", null=True),
    ),
    ("studentinventory", "email_address", models.EmailField(blank=True, default="", null=True)),
    (
        "studentinventory",
        "languages_spoken_at_home",
        models.TextField(blank=True, default="", null=True),
    ),
    (
        "studentinventory",
        "languages_most_fluent",
        models.TextField(blank=True, default="", null=True),
    ),
    (
        "studentinventory",
        "religion_from_birth",
        models.CharField(max_length=120, blank=True, default="", null=True),
    ),
    (
        "studentinventory",
        "current_religion",
        models.CharField(max_length=120, blank=True, default="", null=True),
    ),
    (
        "studentinventory",
        "guardian_name",
        models.CharField(max_length=160, blank=True, default="", null=True),
    ),
    (
        "studentinventory",
        "guardian_relationship",
        models.CharField(max_length=120, blank=True, default="", null=True),
    ),
    ("studentinventory", "guardian_address", models.TextField(blank=True, default="", null=True)),
    (
        "studentinventory",
        "guardian_contact_number",
        models.CharField(max_length=64, blank=True, default="", null=True),
    ),
    (
        "studentinventory",
        "emergency_contact_name",
        models.CharField(max_length=160, blank=True, default="", null=True),
    ),
    (
        "studentinventory",
        "emergency_contact_number",
        models.CharField(max_length=64, blank=True, default="", null=True),
    ),
    ("studentinventory", "friends_in_school", models.TextField(blank=True, default="", null=True)),
    (
        "studentinventory",
        "friends_outside_school",
        models.TextField(blank=True, default="", null=True),
    ),
    ("studentinventory", "special_interest", models.TextField(blank=True, default="", null=True)),
    (
        "studentinventory",
        "special_skills_talents",
        models.TextField(blank=True, default="", null=True),
    ),
    ("studentinventory", "hobbies_recreation", models.TextField(blank=True, default="", null=True)),
    ("studentinventory", "ambition_goal", models.TextField(blank=True, default="", null=True)),
    ("studentinventory", "characteristics", models.TextField(blank=True, default="", null=True)),
    (
        "studentinventory",
        "boarding_landlord_name",
        models.CharField(max_length=160, blank=True, default="", null=True),
    ),
    ("studentinventory", "boarding_address", models.TextField(blank=True, default="", null=True)),
    (
        "studentinventory",
        "accidents_experienced",
        models.TextField(blank=True, default="", null=True),
    ),
    ("studentinventory", "accidents_effect", models.TextField(blank=True, default="", null=True)),
    (
        "studentinventory",
        "operations_experienced",
        models.TextField(blank=True, default="", null=True),
    ),
    ("studentinventory", "operations_effect", models.TextField(blank=True, default="", null=True)),
    (
        "studentinventory",
        "immunizations",
        ArrayField(
            models.CharField(
                max_length=24,
                choices=[
                    ("CHICKEN_POX", "Chicken pox"),
                    ("BOOSTER", "Booster"),
                    ("MEASLES_MMR", "Measles / MMR"),
                    ("HEPATITIS_B", "Hepatitis B"),
                    ("MUMPS", "Mumps"),
                    ("INFLUENZA", "Influenza"),
                    ("SMALL_POX", "Small pox"),
                    ("OTHER", "Other"),
                ],
            ),
            default=list,
            blank=True,
            null=True,
        ),
    ),
    (
        "studentinventory",
        "immunization_other",
        models.CharField(max_length=160, blank=True, default="", null=True),
    ),
    (
        "studentinventory",
        "height",
        models.CharField(max_length=64, blank=True, default="", null=True),
    ),
    (
        "studentinventory",
        "weight",
        models.CharField(max_length=64, blank=True, default="", null=True),
    ),
    (
        "studentinventory",
        "physical_disadvantage",
        models.TextField(blank=True, default="", null=True),
    ),
    ("studentinventory", "illness_this_year", models.TextField(blank=True, default="", null=True)),
    ("studentinventory", "previous_illness", models.TextField(blank=True, default="", null=True)),
    (
        "studentinventory",
        "schedule_satisfaction_reason",
        models.TextField(blank=True, default="", null=True),
    ),
    (
        "studentinventory",
        "course_choice_other",
        models.TextField(blank=True, default="", null=True),
    ),
    (
        "studentinventory",
        "lowest_subjects_grades",
        models.TextField(blank=True, default="", null=True),
    ),
    (
        "studentinventory",
        "highest_subjects_grades",
        models.TextField(blank=True, default="", null=True),
    ),
    (
        "studentinventory",
        "inclination_performing_arts",
        models.TextField(blank=True, default="", null=True),
    ),
    ("studentinventory", "inclination_sports", models.TextField(blank=True, default="", null=True)),
    (
        "studentinventory",
        "inclination_leadership",
        models.TextField(blank=True, default="", null=True),
    ),
    (
        "studentinventory",
        "other_skills_hobbies",
        models.TextField(blank=True, default="", null=True),
    ),
    (
        "studentinventory",
        "desired_extracurricular_activities",
        models.TextField(blank=True, default="", null=True),
    ),
    (
        "studentinventory",
        "reading_preferences",
        models.TextField(blank=True, default="", null=True),
    ),
    (
        "studentinventory",
        "intended_work_other",
        models.CharField(max_length=160, blank=True, default="", null=True),
    ),
    ("studentinventory", "prior_counseling_experience", models.BooleanField(null=True, blank=True)),
    (
        "studentinventory",
        "prior_counselor_name",
        models.CharField(max_length=160, blank=True, default="", null=True),
    ),
    (
        "studentinventory",
        "prior_counseling_when",
        models.CharField(max_length=120, blank=True, default="", null=True),
    ),
    (
        "studentinventory",
        "prior_counseling_where",
        models.CharField(max_length=200, blank=True, default="", null=True),
    ),
    ("studentinventory", "current_concerns", models.TextField(blank=True, default="", null=True)),
    ("studentinventory", "current_fears", models.TextField(blank=True, default="", null=True)),
    (
        "inventoryfamilymember",
        "name",
        models.CharField(max_length=160, blank=True, default="", null=True),
    ),
    ("inventoryfamilymember", "date_of_birth", models.DateField(null=True, blank=True)),
    (
        "inventoryfamilymember",
        "place_of_birth",
        models.CharField(max_length=160, blank=True, default="", null=True),
    ),
    (
        "inventoryfamilymember",
        "current_address",
        models.TextField(blank=True, default="", null=True),
    ),
    (
        "inventoryfamilymember",
        "permanent_address",
        models.TextField(blank=True, default="", null=True),
    ),
    (
        "inventoryfamilymember",
        "contact_number",
        models.CharField(max_length=64, blank=True, default="", null=True),
    ),
    (
        "inventoryfamilymember",
        "email_address",
        models.EmailField(blank=True, default="", null=True),
    ),
    (
        "inventoryfamilymember",
        "educational_attainment",
        models.CharField(max_length=160, blank=True, default="", null=True),
    ),
    (
        "inventoryfamilymember",
        "occupation",
        models.CharField(max_length=160, blank=True, default="", null=True),
    ),
    (
        "inventoryfamilymember",
        "business_address",
        models.TextField(blank=True, default="", null=True),
    ),
    (
        "inventoryfamilymember",
        "business_telephone",
        models.CharField(max_length=64, blank=True, default="", null=True),
    ),
    (
        "inventoryfamilymember",
        "languages_spoken",
        models.TextField(blank=True, default="", null=True),
    ),
    (
        "inventoryfamilymember",
        "religion_raised_with",
        models.CharField(max_length=120, blank=True, default="", null=True),
    ),
    (
        "inventoryfamilymember",
        "current_religion",
        models.CharField(max_length=120, blank=True, default="", null=True),
    ),
    (
        "inventorysibling",
        "name",
        models.CharField(max_length=160, blank=True, default="", null=True),
    ),
    (
        "inventorysibling",
        "sex",
        models.CharField(
            max_length=16,
            choices=[("MALE", "Male"), ("FEMALE", "Female")],
            blank=True,
            default="",
            null=True,
        ),
    ),
    ("inventorysibling", "age", models.PositiveSmallIntegerField(null=True, blank=True)),
    (
        "inventorysibling",
        "educational_attainment",
        models.CharField(max_length=160, blank=True, default="", null=True),
    ),
    (
        "inventorysibling",
        "occupation",
        models.CharField(max_length=160, blank=True, default="", null=True),
    ),
    (
        "inventoryeducationentry",
        "school_attended_address",
        models.TextField(blank=True, default="", null=True),
    ),
    (
        "inventoryeducationentry",
        "inclusive_years",
        models.CharField(max_length=100, blank=True, default="", null=True),
    ),
    (
        "inventoryeducationentry",
        "awards_received",
        models.TextField(blank=True, default="", null=True),
    ),
    (
        "inventoryorganizationmembership",
        "organization_name",
        models.CharField(max_length=180, blank=True, default="", null=True),
    ),
    (
        "inventoryorganizationmembership",
        "position_title",
        models.CharField(max_length=160, blank=True, default="", null=True),
    ),
    (
        "inventorytransportationentry",
        "frequency",
        models.CharField(max_length=100, blank=True, default="", null=True),
    ),
    ("inventoryreopenevent", "reason", models.TextField(max_length=1000, null=True)),
]
CONSTRAINTS = tuple(name.lower() + "_cipher_present" for name, _column, _relation in FAMILIES)


class Migration(migrations.Migration):
    dependencies = [("inventory", "0006_encrypt_confidential_content")]
    operations = (
        [migrations.RunPython(verify_content, migrations.RunPython.noop)]
        + [
            migrations.AlterField(model_name=model, name=name, field=field)
            for model, name, field in PLAIN_FIELDS
        ]
        + [migrations.RunPython(migrations.RunPython.noop, restore_plaintext)]
        + [
            migrations.RemoveField(model_name=model, name=name)
            for model, name, _field in PLAIN_FIELDS
        ]
        + [
            migrations.AlterField(
                model_name=name.lower(),
                name=column,
                field=models.TextField(editable=False),
            )
            for name, column, _kind in FAMILIES
        ]
        + [
            migrations.AddConstraint(
                model_name=name.lower(),
                constraint=models.CheckConstraint(
                    condition=~models.Q(**{column: ""}), name=constraint
                ),
            )
            for (name, column, _kind), constraint in zip(FAMILIES, CONSTRAINTS, strict=True)
        ]
    )
