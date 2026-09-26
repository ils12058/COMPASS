from django.db import migrations, models
from django.db.models import Exists, OuterRef

LEGACY_UNKNOWN = "LEGACY_UNKNOWN"
LIVE = "LIVE"


def classify_existing_call_slips(apps, schema_editor):
    """Record LIVE only where a durable issuance Notification proves live issuance.

    ``call_slip.issued`` Notifications were persisted in the same transaction as live issuance
    and are never deleted. Their absence is not evidence of historical intent (rows may predate
    Notifications), so every other existing row remains LEGACY_UNKNOWN.
    """

    CallSlip = apps.get_model("call_slips", "CallSlip")
    Notification = apps.get_model("notifications", "Notification")
    issued = Notification.objects.filter(
        event_code="call_slip.issued",
        source_type="call_slip",
        source_id=OuterRef("pk"),
    )
    CallSlip.objects.filter(Exists(issued)).update(issuance_mode=LIVE)


class Migration(migrations.Migration):
    dependencies = [
        ("call_slips", "0002_void_and_reissue"),
        ("notifications", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="callslip",
            name="issuance_mode",
            field=models.CharField(
                choices=[
                    ("LIVE", "Live issuance"),
                    ("HISTORICAL", "Historical entry"),
                    ("LEGACY_UNKNOWN", "Not recorded"),
                ],
                default=LEGACY_UNKNOWN,
                max_length=16,
            ),
            preserve_default=False,
        ),
        migrations.RunPython(classify_existing_call_slips, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="callslip",
            constraint=models.CheckConstraint(
                condition=models.Q(issuance_mode__in=["LIVE", "HISTORICAL", "LEGACY_UNKNOWN"]),
                name="callslip_issuance_mode_valid",
            ),
        ),
    ]
