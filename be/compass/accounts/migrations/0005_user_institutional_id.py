from django.db import migrations, models
from django.db.models.functions import Lower


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0004_user_email_verified_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="institutional_id",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.UniqueConstraint(
                Lower("institutional_id"),
                condition=models.Q(("institutional_id__isnull", False)),
                name="accounts_user_institutional_id_ci_uniq",
            ),
        ),
    ]
