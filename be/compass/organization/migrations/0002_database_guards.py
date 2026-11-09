"""Frozen final PostgreSQL database guards; see ADR-117."""

from django.db import migrations, models


FORWARD_SQL = r"""
CREATE OR REPLACE FUNCTION public.organization_valid_year_levels_v1(levels smallint[])
 RETURNS boolean
 LANGUAGE sql
 IMMUTABLE PARALLEL SAFE
AS $function$
    SELECT COALESCE(
        array_ndims(levels) = 1 AND array_lower(levels, 1) = 1
        AND cardinality(levels) BETWEEN 1 AND 10
        AND levels = ARRAY(
            SELECT DISTINCT level FROM unnest(levels) AS level
            WHERE level BETWEEN 1 AND 10 ORDER BY level
        )::smallint[], false
    )
$function$;
"""

REVERSE_SQL = r"""

DROP FUNCTION public.organization_valid_year_levels_v1(levels smallint[]);
"""


class Migration(migrations.Migration):
    dependencies = [
        ('organization', '0001_release_baseline'),
    ]

    operations = [
        migrations.RunSQL(FORWARD_SQL, reverse_sql=REVERSE_SQL),
        migrations.AddConstraint(
            model_name='program',
            constraint=models.CheckConstraint(condition=models.Q(models.Q(('applicable_year_levels__isnull', True), ('year_level_policy_status', 'PENDING_POLICY')), models.Q(('academic_classification__isnull', False), ('applicable_year_levels__isnull', False), ('year_level_policy_status', 'CONFIGURED'), models.Func(models.F('applicable_year_levels'), function='organization_valid_year_levels_v1', output_field=models.BooleanField())), _connector='OR'), name='organization_program_policy_consistent'),
        ),
    ]
