"""Atomic Phase B/reverse: fence all writers before data verification or DDL."""

from datetime import date
from django.contrib.postgres.fields import ArrayField
from django.core.validators import MinValueValidator
from django.db import migrations, models
from compass.graduate_tracer.migrations._graduate_tracer_confidential_content_v1 import (
    FAMILIES,
    decrypt,
    encrypt,
    failure,
    keyring,
    plaintext,
    verify_anonymous,
)


def lock_tables(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        for name, _, _ in FAMILIES:
            table = schema_editor.quote_name(apps.get_model("graduate_tracer", name)._meta.db_table)
            cursor.execute(f"LOCK TABLE {table} IN EXCLUSIVE MODE")


def verify_content(apps, schema_editor):
    lock_tables(apps, schema_editor)
    ring = keyring()
    alias = schema_editor.connection.alias
    children = [apps.get_model("graduate_tracer", name) for name, _, _ in FAMILIES[1:]]
    roots = apps.get_model("graduate_tracer", "GraduateTracerResponse").objects.using(alias)
    for name, column, _ in FAMILIES:
        rows = apps.get_model("graduate_tracer", name).objects.using(alias)
        for row in rows.order_by("pk").iterator(chunk_size=200):
            if name == "GraduateTracerResponse" and row.student_id is None:
                verify_anonymous(row, rows, children)
                continue
            if (
                name != "GraduateTracerResponse"
                and not roots.filter(
                    pk=row.response_id, student__isnull=False, anonymized_at__isnull=True
                ).exists()
            ):
                raise failure(row, "malformed", name)
            current = plaintext(row, name)
            token = getattr(row, column)
            if token:
                previous = decrypt(ring, row, token, name)
                if previous == current:
                    continue
            token = encrypt(ring, row, current, name)
            if decrypt(ring, row, token, name) != current:
                raise failure(row, "malformed", name)
            rows.filter(pk=row.pk).update(**{column: token})


def restore_plaintext(apps, schema_editor):
    ring = keyring()
    alias = schema_editor.connection.alias
    for name, column, _ in FAMILIES:
        rows = apps.get_model("graduate_tracer", name).objects.using(alias)
        for row in rows.order_by("pk").iterator(chunk_size=200):
            if name == "GraduateTracerResponse" and row.student_id is None:
                # Anonymous contributions intentionally have no content to decrypt.
                restored = {
                    field_name: field.get_default()
                    for model_name, field_name, field in PLAIN_FIELDS
                    if model_name == name.lower()
                }
            else:
                restored = dict(decrypt(ring, row, getattr(row, column), name))
                for key in {"birth_date", "date_taken"}.intersection(restored):
                    restored[key] = (
                        date.fromisoformat(restored[key]) if restored[key] is not None else None
                    )
            rows.filter(pk=row.pk).update(**restored)
            if name == "GraduateTracerResponse" and row.student_id is None:
                children = [
                    apps.get_model("graduate_tracer", child) for child, _, _ in FAMILIES[1:]
                ]
                verify_anonymous(rows.get(pk=row.pk), rows, children)
                continue
            expected = decrypt(ring, row, getattr(row, column), name)
            if plaintext(rows.get(pk=row.pk), name) != expected:
                raise failure(row, "malformed", name)


PLAIN_FIELDS = [
    (
        "graduatetracerresponse",
        "permanent_address_snapshot",
        models.TextField(blank=True, default="", null=True),
    ),
    (
        "graduatetracerresponse",
        "email_snapshot",
        models.EmailField(max_length=320, blank=True, default="", null=True),
    ),
    (
        "graduatetracerresponse",
        "telephone_contact_numbers_snapshot",
        models.CharField(max_length=128, blank=True, default="", null=True),
    ),
    (
        "graduatetracerresponse",
        "mobile_number_snapshot",
        models.CharField(max_length=64, blank=True, default="", null=True),
    ),
    ("graduatetracerresponse", "birth_date", models.DateField(null=True, blank=True)),
    (
        "graduatetracerresponse",
        "province",
        models.CharField(max_length=160, blank=True, default="", null=True),
    ),
    (
        "graduatetracerresponse",
        "undergraduate_degree_reasons",
        ArrayField(
            models.CharField(
                max_length=48,
                choices=[
                    (
                        "HIGH_GRADES_RELATED_COURSE",
                        "High grades in the course or subject area(s) related to the course",
                    ),
                    ("GOOD_GRADES_HIGH_SCHOOL", "Good grades in high school"),
                    ("PARENTS_RELATIVES", "Influence of parents or relatives"),
                    ("PEER_INFLUENCE", "Peer Influence"),
                    ("ROLE_MODEL", "Inspired by a role model"),
                    ("PASSION_PROFESSION", "Strong passion for the profession"),
                    ("IMMEDIATE_EMPLOYMENT", "Prospect for immediate employment"),
                    ("STATUS_PRESTIGE", "Status or prestige of the profession"),
                    (
                        "COURSE_AVAILABILITY",
                        "Availability of course offering in chosen institution",
                    ),
                    ("CAREER_ADVANCEMENT", "Prospect of career advancement"),
                    ("AFFORDABLE", "Affordable for the family"),
                    ("ATTRACTIVE_COMPENSATION", "Prospect of attractive compensation"),
                    ("EMPLOYMENT_ABROAD", "Opportunity for employment abroad"),
                    ("NO_PARTICULAR_CHOICE", "No particular choice or no better idea"),
                ],
            ),
            default=list,
            blank=True,
            null=True,
        ),
    ),
    (
        "graduatetracerresponse",
        "graduate_study_reasons",
        ArrayField(
            models.CharField(
                max_length=48,
                choices=[
                    (
                        "HIGH_GRADES_RELATED_COURSE",
                        "High grades in the course or subject area(s) related to the course",
                    ),
                    ("GOOD_GRADES_HIGH_SCHOOL", "Good grades in high school"),
                    ("PARENTS_RELATIVES", "Influence of parents or relatives"),
                    ("PEER_INFLUENCE", "Peer Influence"),
                    ("ROLE_MODEL", "Inspired by a role model"),
                    ("PASSION_PROFESSION", "Strong passion for the profession"),
                    ("IMMEDIATE_EMPLOYMENT", "Prospect for immediate employment"),
                    ("STATUS_PRESTIGE", "Status or prestige of the profession"),
                    (
                        "COURSE_AVAILABILITY",
                        "Availability of course offering in chosen institution",
                    ),
                    ("CAREER_ADVANCEMENT", "Prospect of career advancement"),
                    ("AFFORDABLE", "Affordable for the family"),
                    ("ATTRACTIVE_COMPENSATION", "Prospect of attractive compensation"),
                    ("EMPLOYMENT_ABROAD", "Opportunity for employment abroad"),
                    ("NO_PARTICULAR_CHOICE", "No particular choice or no better idea"),
                ],
            ),
            default=list,
            blank=True,
            null=True,
        ),
    ),
    (
        "graduatetracerresponse",
        "degree_other_reason",
        models.TextField(blank=True, default="", null=True),
    ),
    (
        "graduatetracerresponse",
        "advanced_study_reasons",
        ArrayField(
            models.CharField(
                max_length=40,
                choices=[
                    ("PROMOTION", "For promotion"),
                    ("PROFESSIONAL_DEVELOPMENT", "For professional development"),
                    ("OTHER", "Others"),
                ],
            ),
            default=list,
            blank=True,
            null=True,
        ),
    ),
    (
        "graduatetracerresponse",
        "advanced_study_other_reason",
        models.TextField(blank=True, default="", null=True),
    ),
    (
        "graduatetracerresponse",
        "unemployment_other_reason",
        models.TextField(blank=True, default="", null=True),
    ),
    (
        "graduatetracerresponse",
        "self_employed_college_skills",
        models.TextField(blank=True, default="", null=True),
    ),
    (
        "graduatetracerresponse",
        "present_occupation",
        models.CharField(max_length=255, blank=True, default="", null=True),
    ),
    (
        "graduatetracerresponse",
        "reasons_for_staying_other",
        models.TextField(blank=True, default="", null=True),
    ),
    (
        "graduatetracerresponse",
        "reasons_for_accepting_first_job",
        ArrayField(
            models.CharField(
                max_length=40,
                choices=[
                    ("SALARIES_BENEFITS", "Salaries & benefits"),
                    ("CAREER_CHALLENGE", "Career challenge"),
                    ("RELATED_SPECIAL_SKILLS", "Related to special skills"),
                    ("PROXIMITY_RESIDENCE", "Proximity to residence"),
                    ("OTHER", "Other"),
                ],
            ),
            default=list,
            blank=True,
            null=True,
        ),
    ),
    (
        "graduatetracerresponse",
        "reasons_for_accepting_other",
        models.TextField(blank=True, default="", null=True),
    ),
    (
        "graduatetracerresponse",
        "reasons_for_changing_job",
        ArrayField(
            models.CharField(
                max_length=40,
                choices=[
                    ("SALARIES_BENEFITS", "Salaries & benefits"),
                    ("CAREER_CHALLENGE", "Career challenge"),
                    ("RELATED_SPECIAL_SKILLS", "Related to special skills"),
                    ("PROXIMITY_RESIDENCE", "Proximity to residence"),
                    ("OTHER", "Other"),
                ],
            ),
            default=list,
            blank=True,
            null=True,
        ),
    ),
    (
        "graduatetracerresponse",
        "reasons_for_changing_other",
        models.TextField(blank=True, default="", null=True),
    ),
    (
        "graduatetracerresponse",
        "first_job_duration_other",
        models.TextField(blank=True, default="", null=True),
    ),
    (
        "graduatetracerresponse",
        "first_job_source_other",
        models.TextField(blank=True, default="", null=True),
    ),
    (
        "graduatetracerresponse",
        "time_to_first_job_other",
        models.TextField(blank=True, default="", null=True),
    ),
    (
        "graduatetracerresponse",
        "useful_competencies_other",
        models.TextField(blank=True, default="", null=True),
    ),
    (
        "graduatetracerresponse",
        "curriculum_improvement_suggestions",
        models.TextField(blank=True, default="", null=True),
    ),
    (
        "graduatetracereducation",
        "degree_and_specialization",
        models.CharField(max_length=255, null=True),
    ),
    (
        "graduatetracereducation",
        "college_or_university",
        models.CharField(max_length=255, null=True),
    ),
    (
        "graduatetracereducation",
        "year_graduated",
        models.PositiveSmallIntegerField(validators=[MinValueValidator(1900)], null=True),
    ),
    (
        "graduatetracereducation",
        "honors_or_awards",
        models.CharField(max_length=255, blank=True, default="", null=True),
    ),
    (
        "graduatetracerprofessionalexam",
        "examination_name",
        models.CharField(max_length=255, null=True),
    ),
    ("graduatetracerprofessionalexam", "date_taken", models.DateField(null=True, blank=True)),
    (
        "graduatetracerprofessionalexam",
        "rating",
        models.CharField(max_length=128, blank=True, default="", null=True),
    ),
    ("graduatetracertraining", "title", models.CharField(max_length=255, null=True)),
    (
        "graduatetracertraining",
        "duration_and_credits",
        models.CharField(max_length=255, blank=True, default="", null=True),
    ),
    (
        "graduatetracertraining",
        "institution",
        models.CharField(max_length=255, blank=True, default="", null=True),
    ),
]


class Migration(migrations.Migration):
    dependencies = [("graduate_tracer", "0003_encrypt_confidential_content")]
    operations = (
        [migrations.RunPython(verify_content, migrations.RunPython.noop)]
        + [
            migrations.AlterField(model_name=model, name=name, field=field)
            for model, name, field in PLAIN_FIELDS
        ]
        + [migrations.RunPython(migrations.RunPython.noop, restore_plaintext)]
        + [migrations.RemoveField(model_name=model, name=name) for model, name, _ in PLAIN_FIELDS]
        + [
            migrations.AlterField(
                model_name=name.lower(), name=column, field=models.TextField(editable=False)
            )
            for name, column, _ in FAMILIES[1:]
        ]
        + [
            migrations.AddConstraint(
                model_name="graduatetracerresponse",
                constraint=models.CheckConstraint(
                    condition=(
                        models.Q(
                            student__isnull=False,
                            anonymized_at__isnull=True,
                            confidential_content_ciphertext__isnull=False,
                        )
                        & ~models.Q(confidential_content_ciphertext="")
                    )
                    | models.Q(
                        student__isnull=True,
                        anonymized_at__isnull=False,
                        status="SUBMITTED",
                        confidential_content_ciphertext__isnull=True,
                    ),
                    name="graduatetracerresponse_cipher_shape",
                ),
            )
        ]
        + [
            migrations.AddConstraint(
                model_name=name.lower(),
                constraint=models.CheckConstraint(
                    condition=~models.Q(confidential_content_ciphertext=""),
                    name=name.lower() + "_cipher_shape",
                ),
            )
            for name, _, _ in FAMILIES[1:]
        ]
        # Reverse runs this first, before constraints/nullable columns/DDL change.
        + [migrations.RunPython(migrations.RunPython.noop, lock_tables)]
    )
