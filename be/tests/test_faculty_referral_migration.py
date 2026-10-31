"""Fresh and populated PostgreSQL upgrades preserve historical Referral facts."""

from datetime import date

import pytest
from django.db import connection
from django.db.migrations.exceptions import IrreversibleError
from django.db.migrations.executor import MigrationExecutor

from tests.faculty_referral_helpers import make_world, submit
from tests.test_organization_policy_migration import upgrade_database  # noqa: F401

TARGET = ("referrals", "0002_referral_faculty_home_college_and_more")


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("populated", [False, True])
def test_additive_faculty_referral_upgrade_preserves_legacy_origin_without_backfill(
    upgrade_database,  # noqa: F811
    populated,
):
    db, apps = upgrade_database
    if populated:
        role = (
            apps.get_model("accounts", "Role")
            .objects.using(db.alias)
            .create(code="STUDENT", name="Student")
        )
        student = (
            apps.get_model("accounts", "User")
            .objects.using(db.alias)
            .create(
                email="legacy@synthetic.invalid",
                role_id=role.pk,
                first_name="Legacy",
                last_name="Student",
                profile_confidential_content_ciphertext="historical-profile-ciphertext",
            )
        )
        family = (
            apps.get_model("institutional_forms", "FormFamily")
            .objects.using(db.alias)
            .create(key="referral_slip", title="Referral Slip")
        )
        revision = (
            apps.get_model("institutional_forms", "FormRevision")
            .objects.using(db.alias)
            .create(
                family_id=family.pk,
                official_code="CNSC-OP-GTA-01F9",
                official_revision="1",
                internal_schema_version=1,
            )
        )
        apps.get_model("referrals", "Referral").objects.using(db.alias).create(
            student_id=student.pk,
            student_name_snapshot="Preserved legacy name",
            course_year_block_snapshot="Preserved course",
            confidential_content_ciphertext="historical-referral-ciphertext",
            form_revision_id=revision.pk,
            reference_code="REF-2025-000001",
            referred_on=date(2025, 1, 1),
        )
    old_rows = list(apps.get_model("referrals", "Referral").objects.using(db.alias).values())
    executor = MigrationExecutor(db)
    executor.migrate([TARGET])
    after_apps = executor.loader.project_state([TARGET]).apps
    rows = list(after_apps.get_model("referrals", "Referral").objects.using(db.alias).values())
    assert [
        {key: row[key] for key in before} for before, row in zip(old_rows, rows, strict=True)
    ] == old_rows
    for row in rows:
        assert row["submission_channel"] == "LEGACY_UNSPECIFIED"
        for key in (
            "submitted_by_id",
            "submitted_at",
            "faculty_home_college_id",
            "student_college_at_submission_id",
            "submission_policy_digest",
            "submission_policy_event_id",
        ):
            assert row[key] is None
    if populated:
        # A pre-FAC writer that omits the new columns remains explicitly unspecified,
        # rather than failing or fabricating a Faculty/GCO provenance claim.
        apps.get_model("referrals", "Referral").objects.using(db.alias).create(
            student_id=student.pk,
            student_name_snapshot="Old writer",
            course_year_block_snapshot="Old writer course",
            confidential_content_ciphertext="old-writer-ciphertext",
            form_revision_id=revision.pk,
            reference_code="REF-2025-000002",
            referred_on=date(2025, 1, 2),
        )
        saved = (
            after_apps.get_model("referrals", "Referral")
            .objects.using(db.alias)
            .get(
                reference_code="REF-2025-000002",
            )
        )
        assert saved.submission_channel == "LEGACY_UNSPECIFIED"
        assert saved.submitted_by_id is None
    assert not after_apps.get_model("audit", "AuditEvent").objects.using(db.alias).exists()
    MigrationExecutor(db).migrate([TARGET])
    assert len(rows) == int(populated)


@pytest.mark.django_db(transaction=True)
def test_rollback_cannot_discard_digital_submission_provenance(monkeypatch):
    world = make_world(monkeypatch)
    result, _ = submit(world)
    executor = MigrationExecutor(connection)
    with pytest.raises(IrreversibleError, match="roll forward"):
        executor.migrate([("referrals", "0001_canonical_baseline")])
    from compass.referrals.models import Referral

    assert Referral.objects.get(pk=result["id"]).submitted_by_id == world.faculty.pk
