from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("good_moral", "0002_request_cancellation"),
    ]

    operations = [
        migrations.AddField(
            model_name="goodmoralrequest",
            name="creation_key_digest",
            field=models.CharField(blank=True, max_length=64, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="goodmoralrequest",
            name="creation_request_fingerprint",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
    ]
