"""Rename persisted capability identities without replacing grants or explicit denials."""

from django.db import migrations

PAIRS = tuple(
    (f"shared_summaries.{suffix}", f"student_session_summaries.{suffix}")
    for suffix in ("view_self", "view_assigned", "manage_assigned")
)


def rename_capabilities(apps, schema_editor):
    alias = schema_editor.connection.alias
    Capability = apps.get_model("accounts", "Capability")
    User = apps.get_model("accounts", "User")
    RoleCapability = apps.get_model("accounts", "RoleCapability")
    DesignationCapability = apps.get_model("accounts", "DesignationCapability")
    UserDesignation = apps.get_model("accounts", "UserDesignation")
    Override = apps.get_model("accounts", "UserCapabilityOverride")
    # Fence policy writers; check every pair before changing any identity.
    if schema_editor.connection.vendor == "postgresql":
        with schema_editor.connection.cursor() as cursor:
            for model in (Capability, RoleCapability, DesignationCapability, Override):
                cursor.execute(
                    f"LOCK TABLE {schema_editor.quote_name(model._meta.db_table)} "
                    "IN SHARE ROW EXCLUSIVE MODE"
                )
    rows = Capability.objects.using(alias)
    for old, new in PAIRS:
        if rows.filter(code=old).exists() and rows.filter(code=new).exists():
            raise RuntimeError("Student Session Summary capability collision; migration stopped.")
    affected = set()
    for old, new in PAIRS:
        item = rows.filter(code=old).first()
        if item is None:
            continue
        roles = RoleCapability.objects.using(alias).filter(capability_id=item.pk)
        designations = DesignationCapability.objects.using(alias).filter(capability_id=item.pk)
        affected.update(
            User.objects.using(alias)
            .filter(role_id__in=roles.values("role_id"))
            .values_list("pk", flat=True)
        )
        affected.update(
            UserDesignation.objects.using(alias)
            .filter(designation_id__in=designations.values("designation_id"))
            .values_list("user_id", flat=True)
        )
        affected.update(
            Override.objects.using(alias)
            .filter(capability_id=item.pk)
            .values_list("user_id", flat=True)
        )
        # FK identities, override effects, reasons, expiry and creation timestamps survive intact.
        rows.filter(pk=item.pk).update(
            code=new,
            name={
                "view_self": "View own Student Session Summaries",
                "view_assigned": "View assigned Student Session Summaries",
                "manage_assigned": "Manage assigned Student Session Summaries",
            }[new.rsplit(".", 1)[1]],
            description=item.description.replace("Shared Summaries", "Student Session Summaries"),
        )
    if affected:
        if alias != "default":
            raise RuntimeError("Authority invalidation requires the default database.")
        from compass.audit.context import AuditContext
        from compass.authentication.security import invalidate_auth_state_after_authority_change

        for user_id in sorted(affected, key=str):
            invalidate_auth_state_after_authority_change(
                user_id=user_id,
                context=AuditContext.system(),
                reason="student_session_summary_capability_cutover",
            )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_canonical_baseline"),
        ("authentication", "0001_canonical_baseline"),
        ("audit", "0001_canonical_baseline"),
    ]
    # Reversing policy identities without coordinating code, keys and data is unsafe.
    operations = [migrations.RunPython(rename_capabilities)]
