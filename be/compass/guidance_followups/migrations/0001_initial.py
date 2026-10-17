"""Create independent Guidance Follow-Ups. No legacy rows or credentials are modified."""
import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="GuidanceFollowUp",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("source_kind", models.CharField(max_length=32, null=True, blank=True, choices=[
                    ("COUNSELING_ENCOUNTER", "Counseling encounter"),
                    ("REFERRAL", "Referral"), ("ROUTINE_INTERVIEW", "Routine interview"),
                ])),
                ("source_id", models.UUIDField(null=True, blank=True)),
                ("visibility", models.CharField(max_length=32, choices=[
                    ("OPERATIONAL", "Operational coordination"),
                    ("COUNSELOR_CONFIDENTIAL", "Counselor-confidential"),
                ])),
                ("category", models.CharField(max_length=32, choices=[
                    ("ADMINISTRATIVE", "Administrative coordination"),
                    ("STUDENT_CONTACT", "Student contact"),
                    ("COUNSELING", "Counseling follow-up"),
                    ("REFERRAL_ACTION", "Referral coordination"),
                ])),
                ("due_at", models.DateTimeField()),
                ("status", models.CharField(max_length=16, default="PENDING", choices=[
                    ("PENDING", "Pending"), ("COMPLETED", "Completed"), ("CANCELLED", "Cancelled"),
                ])),
                ("description_ciphertext", models.TextField(null=True, blank=True, editable=False)),
                ("outcome_ciphertext", models.TextField(null=True, blank=True, editable=False)),
                ("completed_at", models.DateTimeField(null=True, blank=True)),
                ("cancelled_at", models.DateTimeField(null=True, blank=True)),
                ("version", models.PositiveIntegerField(default=1)),
                ("creation_key_digest", models.CharField(max_length=64, unique=True)),
                ("creation_request_fingerprint", models.CharField(max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("student", models.ForeignKey(
                    to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT,
                    related_name="student_guidance_followups",
                )),
                ("assigned_to", models.ForeignKey(
                    to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT,
                    related_name="assigned_guidance_followups",
                )),
                ("created_by", models.ForeignKey(
                    to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT,
                    related_name="created_guidance_followups",
                )),
                ("completed_by", models.ForeignKey(
                    to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT,
                    null=True, blank=True, related_name="completed_guidance_followups",
                )),
                ("cancelled_by", models.ForeignKey(
                    to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT,
                    null=True, blank=True, related_name="cancelled_guidance_followups",
                )),
            ],
            options={"default_permissions": (), "ordering": ("due_at", "id")},
        ),
        migrations.AddConstraint(
            model_name="guidancefollowup",
            constraint=models.CheckConstraint(
                condition=(
                    Q(source_kind__isnull=True, source_id__isnull=True)
                    | Q(source_kind__isnull=False, source_id__isnull=False)
                ), name="fup_source_pair_consistent",
            ),
        ),
        migrations.AddConstraint(
            model_name="guidancefollowup",
            constraint=models.CheckConstraint(condition=Q(version__gte=1), name="fup_version_positive"),
        ),
        migrations.AddConstraint(
            model_name="guidancefollowup",
            constraint=models.CheckConstraint(
                condition=(
                    Q(status="PENDING", completed_at__isnull=True, completed_by__isnull=True,
                      cancelled_at__isnull=True, cancelled_by__isnull=True,
                      outcome_ciphertext__isnull=True)
                    | Q(status="COMPLETED", completed_at__isnull=False,
                        completed_by__isnull=False, cancelled_at__isnull=True,
                        cancelled_by__isnull=True, outcome_ciphertext__isnull=False)
                    | Q(status="CANCELLED", cancelled_at__isnull=False,
                        cancelled_by__isnull=False, completed_at__isnull=True,
                        completed_by__isnull=True, outcome_ciphertext__isnull=True)
                ), name="fup_terminal_state_consistent",
            ),
        ),
        migrations.AddIndex(
            model_name="guidancefollowup",
            index=models.Index(fields=("assigned_to", "status", "due_at", "id"), name="fup_assignment_idx"),
        ),
        migrations.AddIndex(
            model_name="guidancefollowup",
            index=models.Index(fields=("student", "created_at", "id"), name="fup_student_created_idx"),
        ),
        migrations.AddIndex(
            model_name="guidancefollowup",
            index=models.Index(fields=("source_kind", "source_id"), name="fup_source_ref_idx"),
        ),
        migrations.CreateModel(
            name="GuidanceFollowUpEvent",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("kind", models.CharField(max_length=24, choices=[
                    ("CREATED", "Created"), ("UPDATED", "Updated"),
                    ("REASSIGNED", "Reassigned"), ("ACTIVITY_RECORDED", "Activity recorded"),
                    ("COMPLETED", "Completed"), ("CANCELLED", "Cancelled"),
                ])),
                ("revision", models.PositiveIntegerField()),
                ("old_due_at", models.DateTimeField(null=True, blank=True)),
                ("new_due_at", models.DateTimeField(null=True, blank=True)),
                ("remarks_ciphertext", models.TextField(null=True, blank=True, editable=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("followup", models.ForeignKey(
                    to="guidance_followups.guidancefollowup", on_delete=django.db.models.deletion.PROTECT,
                    related_name="events",
                )),
                ("actor", models.ForeignKey(
                    to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT,
                    related_name="guidance_followup_events",
                )),
                ("old_assignee", models.ForeignKey(
                    to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT,
                    null=True, blank=True, related_name="+",
                )),
                ("new_assignee", models.ForeignKey(
                    to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT,
                    null=True, blank=True, related_name="+",
                )),
            ],
            options={"default_permissions": (), "ordering": ("revision", "created_at", "id")},
        ),
        migrations.AddConstraint(
            model_name="guidancefollowupevent",
            constraint=models.UniqueConstraint(
                fields=("followup", "revision"), name="fup_event_revision_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="guidancefollowupevent",
            constraint=models.CheckConstraint(condition=Q(revision__gte=1), name="fup_event_version_positive"),
        ),
    ]
