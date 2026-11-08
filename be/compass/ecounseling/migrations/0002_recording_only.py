"""EC-RC-1/2: E-Counseling becomes recording-only. Destructive and irreversible by decision.

Every transcription capture, its stored artifact (and any transcript file already in private
storage), reconciliation and webhook receipts, and every transcription or transcript-storage consent
are deleted; there is no drain, cutover or retained legacy policy. A session-media consent always covered recording, so it becomes the recording
consent it already granted. Audit events are left untouched.
"""

from django.db import migrations, models
from django.db.models import Q

TRANSCRIPT_SCOPES = ("LIVE_TRANSCRIPTION", "TRANSCRIPT_STORAGE")


def _delete_stored_transcripts(artifacts):
    """Delete transcript files already copied into private storage, so no copy outlives its row.

    Best effort by decision: a file that cannot be deleted is reported by its opaque key (never by
    content or Student detail) so an operator can remove it, and the migration still completes.
    """
    keys = [key for key in artifacts.exclude(object_key=None).values_list("object_key", flat=True)]
    if not keys:
        return
    from compass.integrations.storage import ObjectStorage

    failed = []
    try:
        storage = ObjectStorage(alias="ecounseling_media")
    except Exception:  # noqa: BLE001 - reported below; the purge itself must still finish.
        failed = keys
    else:
        for key in keys:
            try:
                storage.delete(key)
            except Exception:  # noqa: BLE001 - reported below.
                failed.append(key)
    print(f"  Deleted {len(keys) - len(failed)} stored transcript file(s).")
    if failed:
        print(f"  WARNING: {len(failed)} stored transcript file(s) could not be deleted:")
        for key in failed:
            print(f"    {key}")


def purge_transcription(apps, schema_editor):
    Capture = apps.get_model("ecounseling", "ECounselingMediaCapture")
    Artifact = apps.get_model("ecounseling", "ECounselingMediaArtifact")
    Reconciliation = apps.get_model("ecounseling", "ECounselingCaptureReconciliation")
    Receipt = apps.get_model("ecounseling", "DailyWebhookReceipt")
    Consent = apps.get_model("ecounseling", "ECounselingConsent")
    transcription = Capture.objects.filter(kind="TRANSCRIPTION")
    _delete_stored_transcripts(Artifact.objects.filter(capture__in=transcription))
    Receipt.objects.filter(
        Q(capture__in=transcription) | Q(event_type__startswith="transcript.")
    ).delete()
    Reconciliation.objects.filter(capture__in=transcription).delete()
    Artifact.objects.filter(capture__in=transcription).delete()
    transcription.delete()
    Consent.objects.filter(scope__in=TRANSCRIPT_SCOPES).delete()
    Consent.objects.filter(scope="SESSION_MEDIA_CAPTURE").update(scope="AUDIO_VIDEO_RECORDING")


class Migration(migrations.Migration):
    dependencies = [
        ("ecounseling", "0001_canonical_baseline"),
    ]

    operations = [
        migrations.RunPython(purge_transcription, elidable=False),
        migrations.RemoveConstraint(
            model_name="ecounselingmediacapture",
            name="ec_media_storage_transcription_ck",
        ),
        migrations.RemoveConstraint(
            model_name="ecounselingroom",
            name="ec_room_media_policy_valid",
        ),
        migrations.AlterField(
            model_name="ecounselingconsent",
            name="scope",
            field=models.CharField(
                choices=[("AUDIO_VIDEO_RECORDING", "Audio/video recording")], max_length=32
            ),
        ),
        migrations.AlterField(
            model_name="ecounselingmediacapture",
            name="kind",
            field=models.CharField(choices=[("RECORDING", "Recording")], max_length=20),
        ),
        migrations.RemoveField(
            model_name="ecounselingmediacapture",
            name="transcript_storage_authorized",
        ),
        migrations.RemoveField(
            model_name="ecounselingmediacapture",
            name="transcript_storage_enabled",
        ),
        migrations.RemoveField(
            model_name="ecounselingroom",
            name="media_policy_version",
        ),
        migrations.AddConstraint(
            model_name="ecounselingconsent",
            constraint=models.CheckConstraint(
                condition=models.Q(scope="AUDIO_VIDEO_RECORDING"),
                name="ec_consent_recording_only_ck",
            ),
        ),
        migrations.AddConstraint(
            model_name="ecounselingmediacapture",
            constraint=models.CheckConstraint(
                condition=models.Q(kind="RECORDING"), name="ec_media_recording_only_ck"
            ),
        ),
    ]
