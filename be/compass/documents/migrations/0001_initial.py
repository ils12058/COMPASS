import uuid

from django.db import migrations, models


def bootstrap_default_profile(apps, schema_editor):
    DocumentBrandingProfile = apps.get_model("documents", "DocumentBrandingProfile")
    DocumentBrandingProfile.objects.get_or_create(
        key="default",
        defaults={
            "country_line": "Republic of the Philippines",
            "institution_name": "University of Camarines Norte",
            "institution_short_name": "UCN",
            "former_institution_name": "Camarines Norte State College",
            "office_name": "Guidance and Counseling Office",
        },
    )


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="DocumentBrandingProfile",
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
                ("key", models.CharField(default="default", max_length=32, unique=True)),
                ("country_line", models.CharField(max_length=128)),
                ("institution_name", models.CharField(max_length=255)),
                ("institution_short_name", models.CharField(max_length=64)),
                (
                    "former_institution_name",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                ("institution_address", models.CharField(blank=True, max_length=500, null=True)),
                (
                    "institution_website_url",
                    models.URLField(blank=True, max_length=500, null=True),
                ),
                (
                    "institution_contact_email",
                    models.EmailField(blank=True, max_length=320, null=True),
                ),
                (
                    "institution_social_url",
                    models.URLField(blank=True, max_length=500, null=True),
                ),
                (
                    "office_parent_unit_name",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                ("office_name", models.CharField(max_length=255)),
                ("office_email", models.EmailField(blank=True, max_length=320, null=True)),
                ("office_phone", models.CharField(blank=True, max_length=64, null=True)),
                ("office_location", models.CharField(blank=True, max_length=255, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"default_permissions": ()},
        ),
        migrations.AddConstraint(
            model_name="documentbrandingprofile",
            constraint=models.CheckConstraint(
                condition=models.Q(("key", "default")),
                name="document_branding_supported_key",
            ),
        ),
        migrations.RunPython(bootstrap_default_profile, migrations.RunPython.noop),
    ]
