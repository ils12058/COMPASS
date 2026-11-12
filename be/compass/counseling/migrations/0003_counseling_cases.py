"""CW-1 counseling cases: new tables only, so the routine additive deployment path applies.

Every index and constraint is declared inside the CreateModel that owns the new table. Nothing
here alters, backfills or reads an existing table.
"""

import django.db.models.deletion
import django.utils.timezone
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('appointments', '0002_release_baseline_links'),
        ('counseling', '0002_database_guards'),
        ('routine_interviews', '0001_release_baseline'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CounselingCase',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('reference_code', models.CharField(max_length=32, unique=True)),
                ('status', models.CharField(choices=[('ACTIVE', 'Active'), ('CLOSED', 'Closed')], default='ACTIVE', max_length=16)),
                ('origin', models.CharField(choices=[('INTAKE', 'Counseling intake'), ('APPOINTMENT', 'Appointment'), ('ENCOUNTER', 'Recorded session'), ('ROUTINE_INTERVIEW', 'Routine Interview')], max_length=24)),
                ('opened_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('version', models.PositiveIntegerField(default=1)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('opened_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='opened_counseling_cases', to=settings.AUTH_USER_MODEL)),
                ('origin_appointment', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='originated_counseling_cases', to='appointments.appointment')),
                ('origin_encounter', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='originated_counseling_cases', to='counseling.counselingencounter')),
                ('origin_routine_interview', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='originated_counseling_cases', to='routine_interviews.routineinterview')),
                ('primary_counselor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='primary_counseling_cases', to=settings.AUTH_USER_MODEL)),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='student_counseling_cases', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('-opened_at', 'id'),
                'default_permissions': (),
                'indexes': [
                    models.Index(fields=['primary_counselor', 'status', 'opened_at'], name='counseling_case_owner_idx'),
                    models.Index(fields=['student', 'status'], name='counseling_case_student_idx'),
                ],
                'constraints': [
                    models.CheckConstraint(condition=models.Q(('version__gt', 0)), name='counseling_case_version_positive'),
                    models.CheckConstraint(condition=models.Q(('student', models.F('primary_counselor')), _negated=True), name='counseling_case_counselor_not_student'),
                    models.CheckConstraint(condition=models.Q(models.Q(('origin', 'INTAKE'), ('origin_appointment__isnull', True), ('origin_encounter__isnull', True), ('origin_routine_interview__isnull', True)), models.Q(('origin', 'APPOINTMENT'), ('origin_appointment__isnull', False), ('origin_encounter__isnull', True), ('origin_routine_interview__isnull', True)), models.Q(('origin', 'ENCOUNTER'), ('origin_appointment__isnull', True), ('origin_encounter__isnull', False), ('origin_routine_interview__isnull', True)), models.Q(('origin', 'ROUTINE_INTERVIEW'), ('origin_appointment__isnull', True), ('origin_encounter__isnull', True), ('origin_routine_interview__isnull', False)), _connector='OR'), name='counseling_case_origin_matches_source'),
                ],
            },
        ),
        migrations.CreateModel(
            name='CounselingCaseEvent',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('sequence', models.PositiveIntegerField()),
                ('kind', models.CharField(choices=[('OPENED', 'Case opened'), ('SESSION_LINKED', 'Session linked'), ('SESSION_UNLINKED', 'Session link corrected')], max_length=24)),
                ('detail_code', models.CharField(blank=True, default='', max_length=32)),
                ('occurred_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('actor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='counseling_case_events', to=settings.AUTH_USER_MODEL)),
                ('case', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='events', to='counseling.counselingcase')),
                ('encounter', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='case_events', to='counseling.counselingencounter')),
                ('primary_counselor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='responsible_counseling_case_events', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('case', '-sequence'),
                'default_permissions': (),
                'constraints': [
                    models.UniqueConstraint(fields=('case', 'sequence'), name='counseling_case_event_sequence_unique'),
                    models.CheckConstraint(condition=models.Q(('sequence__gt', 0)), name='counseling_case_event_sequence_positive'),
                    models.CheckConstraint(condition=models.Q(('kind', 'OPENED'), ('encounter__isnull', False), _connector='OR'), name='counseling_case_event_session_named'),
                ],
            },
        ),
        migrations.CreateModel(
            name='CounselingCaseReferenceCounter',
            fields=[
                ('year', models.PositiveIntegerField(primary_key=True, serialize=False)),
                ('next_value', models.PositiveIntegerField(default=1)),
            ],
            options={
                'default_permissions': (),
                'constraints': [models.CheckConstraint(condition=models.Q(('next_value__gte', 1)), name='counseling_case_reference_counter_positive')],
            },
        ),
        migrations.CreateModel(
            name='CounselingCaseSession',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('linked_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('removed_at', models.DateTimeField(blank=True, null=True)),
                ('removal_reason', models.CharField(blank=True, choices=[('BELONGS_TO_ANOTHER_CASE', 'Belongs to another case'), ('NOT_PART_OF_THIS_CASE', 'Not part of this case'), ('LINKED_BY_MISTAKE', 'Linked by mistake')], default='', max_length=32)),
                ('case', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='session_links', to='counseling.counselingcase')),
                ('encounter', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='case_links', to='counseling.counselingencounter')),
                ('linked_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='linked_counseling_case_sessions', to=settings.AUTH_USER_MODEL)),
                ('removed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='removed_counseling_case_sessions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('-linked_at', 'id'),
                'default_permissions': (),
                'indexes': [
                    models.Index(fields=['case', 'removed_at'], name='counseling_case_session_idx'),
                ],
                'constraints': [
                    models.UniqueConstraint(condition=models.Q(('removed_at__isnull', True)), fields=('encounter',), name='counseling_case_session_one_current_case'),
                    models.CheckConstraint(condition=models.Q(models.Q(('removal_reason', ''), ('removed_at__isnull', True), ('removed_by__isnull', True)), models.Q(('removed_at__isnull', False), ('removed_by__isnull', False), models.Q(('removal_reason', ''), _negated=True)), _connector='OR'), name='counseling_case_session_removal_complete'),
                ],
            },
        ),
    ]
