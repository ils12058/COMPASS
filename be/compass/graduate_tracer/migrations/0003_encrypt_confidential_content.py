"""Phase A: nullable envelopes and verified identifiable backfill; anonymous stays NULL."""

from django.db import migrations, models
from compass.graduate_tracer.migrations._graduate_tracer_confidential_content_v1 import (
    FAMILIES,
    decrypt,
    encrypt,
    keyring,
    plaintext,
    verify_anonymous,
    failure,
)


def backfill(apps, schema_editor):
    ring = keyring()
    alias = schema_editor.connection.alias
    children = [apps.get_model("graduate_tracer", name) for name, _, _ in FAMILIES[1:]]
    roots = apps.get_model("graduate_tracer", "GraduateTracerResponse").objects.using(alias)
    for name, column, _ in FAMILIES:
        rows = apps.get_model("graduate_tracer", name).objects.using(alias)
        for row in rows.order_by("pk").iterator(chunk_size=200):
            if name == "GraduateTracerResponse" and row.student_id is None:
                verify_anonymous(row, rows, children)
                continue
            if (
                name != "GraduateTracerResponse"
                and not roots.filter(
                    pk=row.response_id, student__isnull=False, anonymized_at__isnull=True
                ).exists()
            ):
                raise failure(row, "malformed", name)
            payload = plaintext(row, name)
            token = encrypt(ring, row, payload, name)
            if decrypt(ring, row, token, name) != payload:
                raise failure(row, "malformed", name)
            rows.filter(pk=row.pk).update(**{column: token})


class Migration(migrations.Migration):
    dependencies = [("graduate_tracer", "0002_graduatetracerdisposedparticipation_and_more")]
    operations = [
        migrations.AddField(
            model_name=name.lower(),
            name=column,
            field=models.TextField(null=True, blank=True, editable=False),
        )
        for name, column, _ in FAMILIES
    ] + [migrations.RunPython(backfill, migrations.RunPython.noop)]
