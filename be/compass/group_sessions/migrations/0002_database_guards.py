"""Frozen final PostgreSQL database guards; see ADR-117."""

from django.db import migrations


FORWARD_SQL = r"""
CREATE OR REPLACE FUNCTION public.compass_group_session_prevent_delete()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
        BEGIN
            RAISE EXCEPTION 'Group Sessions are operational records and cannot be deleted';
        END;
        $function$;
CREATE OR REPLACE FUNCTION public.compass_group_session_facilitator_preserve_delete()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
        BEGIN
            UPDATE group_sessions_groupsessionfacilitator
               SET removed_at = COALESCE(removed_at, clock_timestamp())
             WHERE id = OLD.id;
            RETURN NULL;
        END;
        $function$;
CREATE TRIGGER compass_group_session_prevent_delete BEFORE DELETE ON public.group_sessions_groupsession FOR EACH ROW EXECUTE FUNCTION compass_group_session_prevent_delete();
CREATE TRIGGER compass_group_session_facilitator_preserve_delete BEFORE DELETE ON public.group_sessions_groupsessionfacilitator FOR EACH ROW EXECUTE FUNCTION compass_group_session_facilitator_preserve_delete();
"""

REVERSE_SQL = r"""
DROP TRIGGER compass_group_session_prevent_delete ON public.group_sessions_groupsession;
DROP TRIGGER compass_group_session_facilitator_preserve_delete ON public.group_sessions_groupsessionfacilitator;
DROP FUNCTION public.compass_group_session_facilitator_preserve_delete();
DROP FUNCTION public.compass_group_session_prevent_delete();
"""


class Migration(migrations.Migration):
    dependencies = [
        ('group_sessions', '0001_release_baseline'),
    ]

    operations = [
        migrations.RunSQL(FORWARD_SQL, reverse_sql=REVERSE_SQL),
    ]
