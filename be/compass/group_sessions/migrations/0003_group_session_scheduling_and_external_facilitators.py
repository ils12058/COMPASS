# Additive group scheduling rules and mixed internal/external facilitator identity.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def populate_facilitator_name_snapshots(apps, schema_editor):
    Facilitator = apps.get_model("group_sessions", "GroupSessionFacilitator")
    for item in Facilitator.objects.filter(display_name_snapshot="").select_related("internal_user"):
        user = item.internal_user
        if user is None:
            continue
        display_name = " ".join(
            value.strip()
            for value in (
                user.first_name,
                getattr(user, "middle_name", ""),
                user.last_name,
                getattr(user, "suffix", ""),
            )
            if value and value.strip()
        )
        item.display_name_snapshot = display_name[:255]
        item.save(update_fields=["display_name_snapshot"])


def prevent_facilitator_history_deletion(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        """
        CREATE FUNCTION compass_group_session_facilitator_preserve_delete() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            UPDATE group_sessions_groupsessionfacilitator
               SET removed_at = COALESCE(removed_at, clock_timestamp())
             WHERE id = OLD.id;
            RETURN NULL;
        END;
        $$;
        """
    )
    schema_editor.execute(
        """
        CREATE TRIGGER compass_group_session_facilitator_preserve_delete
        BEFORE DELETE ON group_sessions_groupsessionfacilitator
        FOR EACH ROW EXECUTE FUNCTION compass_group_session_facilitator_preserve_delete();
        """
    )


def reverse_facilitator_extensions(apps, schema_editor):
    """Allow rollback only when it cannot discard new facilitator or schedule history."""
    Facilitator = apps.get_model("group_sessions", "GroupSessionFacilitator")
    GroupSession = apps.get_model("group_sessions", "GroupSession")
    has_external_or_ended_facilitators = Facilitator.objects.filter(
        models.Q(kind="EXTERNAL") | models.Q(removed_at__isnull=False)
    ).exists()
    has_reschedule_history = GroupSession.objects.filter(schedule_revision__gt=1).exists()
    if has_external_or_ended_facilitators or has_reschedule_history:
        raise RuntimeError(
            "Cannot reverse facilitator or schedule history after external guests, replacements, "
            "or rescheduling have been recorded."
        )

    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(
            "DROP TRIGGER IF EXISTS compass_group_session_facilitator_preserve_delete "
            "ON group_sessions_groupsessionfacilitator;"
        )
        schema_editor.execute(
            "DROP FUNCTION IF EXISTS compass_group_session_facilitator_preserve_delete();"
        )


class Migration(migrations.Migration):
    dependencies = [
        ("group_sessions", "0002_alter_groupsessionfacilitator_group_session"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="groupsessionfacilitator",
            name="grp_facil_session_counselor_uniq",
        ),
        migrations.RenameField(
            model_name="groupsessionfacilitator",
            old_name="counselor",
            new_name="internal_user",
        ),
        migrations.AlterField(
            model_name="groupsessionfacilitator",
            name="internal_user",
            field=models.ForeignKey(
                db_column="counselor_id",
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="facilitated_group_sessions",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterModelOptions(
            name="groupsessionfacilitator",
            options={
                "ordering": ("-is_lead", "created_at", "id"),
                "default_permissions": (),
            },
        ),
        migrations.AddField(
            model_name="groupsession",
            name="schedule_revision",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="groupsessionfacilitator",
            name="kind",
            field=models.CharField(
                choices=[("INTERNAL", "Internal COMPASS person"), ("EXTERNAL", "External guest")],
                db_default="INTERNAL",
                default="INTERNAL",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="groupsessionfacilitator",
            name="external_display_name",
            field=models.CharField(blank=True, db_default="", default="", max_length=255),
        ),
        migrations.AddField(
            model_name="groupsessionfacilitator",
            name="display_name_snapshot",
            field=models.CharField(blank=True, db_default="", default="", max_length=255),
        ),
        migrations.AddField(
            model_name="groupsessionfacilitator",
            name="removed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(populate_facilitator_name_snapshots, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="groupsessionfacilitator",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(
                        models.Q(
                            ("external_display_name", ""),
                            ("internal_user__isnull", False),
                            ("kind", "INTERNAL"),
                        ),
                        models.Q(
                            ("internal_user__isnull", True),
                            ("kind", "EXTERNAL"),
                            models.Q(("external_display_name", ""), _negated=True),
                        ),
                        _connector="OR",
                    )
                ),
                name="grp_fac_identity_matches_kind",
            ),
        ),
        migrations.AddConstraint(
            model_name="groupsessionfacilitator",
            constraint=models.UniqueConstraint(
                condition=models.Q(("kind", "INTERNAL"), ("removed_at__isnull", True)),
                fields=("group_session", "internal_user"),
                name="grp_fac_active_internal_uniq",
            ),
        ),
        migrations.AddConstraint(
            model_name="groupsessionfacilitator",
            constraint=models.UniqueConstraint(
                condition=models.Q(("is_lead", True), ("removed_at__isnull", True)),
                fields=("group_session",),
                name="grp_fac_active_lead_uniq",
            ),
        ),
        migrations.RunPython(prevent_facilitator_history_deletion, reverse_facilitator_extensions),
    ]
