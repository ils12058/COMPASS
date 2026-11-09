"""Preserve the PostgreSQL constraint identities established by the summary rename.

The old RunPython renamed schema objects even on an empty database. These SQL-only
renames keep the release schema identical without importing retired migration code.
"""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [('counseling', '0001_release_baseline')]

    operations = [
        migrations.RunSQL(
            sql='''
ALTER TABLE public.counseling_studentsessionsummary
    RENAME CONSTRAINT counseling_studentsessionsummary_pkey TO student_session_summary_pkey;
ALTER TABLE public.counseling_studentsessionsummary
    RENAME CONSTRAINT counseling_studentsessionsummary_encounter_id_key TO student_session_summary_encounter_uniq;
ALTER TABLE public.counseling_studentsessionsummary
    RENAME CONSTRAINT counseling_studentse_encounter_id_e41865cd_fk_counselin TO student_session_summary_encounter_fk;
''',
            reverse_sql='''
ALTER TABLE public.counseling_studentsessionsummary
    RENAME CONSTRAINT student_session_summary_encounter_fk TO counseling_studentse_encounter_id_e41865cd_fk_counselin;
ALTER TABLE public.counseling_studentsessionsummary
    RENAME CONSTRAINT student_session_summary_encounter_uniq TO counseling_studentsessionsummary_encounter_id_key;
ALTER TABLE public.counseling_studentsessionsummary
    RENAME CONSTRAINT student_session_summary_pkey TO counseling_studentsessionsummary_pkey;
''',
        ),
    ]
