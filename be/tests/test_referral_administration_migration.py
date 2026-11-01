"""Actual FAC-2 schema upgrade, populated old paper and digital records, plus fresh install."""

from datetime import date
from uuid import uuid4

import pytest
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

from tests.test_organization_policy_migration import upgrade_database  # noqa: F401

BASE = ("referrals", "0002_referral_faculty_home_college_and_more")
TARGET = ("referrals", "0003_referral_acknowledged_by_and_more")


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("populated", [False, True])
def test_upgrade_preserves_received_dates_ciphertext_provenance_and_no_backfill(
    upgrade_database,  # noqa: F811
    populated,
):
    db, _apps = upgrade_database
    executor = MigrationExecutor(db)
    executor.migrate([BASE])
    apps = executor.loader.project_state([BASE]).apps

    def manager(app, model):
        return apps.get_model(app, model).objects.using(db.alias)

    if populated:
        users = {}
        for code in ("STUDENT", "FACULTY", "COUNSELOR"):
            role = manager("accounts", "Role").create(code=code, name=code)
            users[code] = manager("accounts", "User").create(
                role_id=role.pk,
                email=code + "@synthetic.invalid",
                profile_confidential_content_ciphertext="Preserved profile",
            )
        campus = manager("organization", "Campus").create(code="TEST", name="Synthetic")
        college = manager("organization", "College").create(
            campus_id=campus.pk, code="CCMS", name="Synthetic"
        )
        family = manager("institutional_forms", "FormFamily").create(
            key="referral_slip", title="Referral"
        )
        revision = manager("institutional_forms", "FormRevision").create(
            family_id=family.pk, internal_schema_version=1
        )
        event = manager("audit", "AuditEvent").create(
            action="referral.faculty.policy.recorded",
            outcome="SUCCESS",
            actor_type="SYSTEM",
            metadata={"sentinel": "Retained"},
        )
        for index, channel in enumerate(("GCO_RECORDED", "FACULTY_PORTAL")):
            digital = channel == "FACULTY_PORTAL"
            manager("referrals", "Referral").create(
                id=uuid4(),
                student_id=users["STUDENT"].pk,
                student_name_snapshot="Original",
                course_year_block_snapshot="Original course",
                form_revision_id=revision.pk,
                reference_code=f"REF-2025-{index + 1:06}",
                referred_on=date(2025, 1, 1),
                confidential_content_ciphertext="Preserved encrypted source",
                submission_channel=channel,
                recorded_by_id=None if digital else users["COUNSELOR"].pk,
                received_at=None if digital else timezone.now(),
                submitted_by_id=users["FACULTY"].pk if digital else None,
                submitted_at=timezone.now() if digital else None,
                faculty_home_college_id=college.pk if digital else None,
                student_college_at_submission_id=college.pk if digital else None,
                submission_policy_digest="a" * 64 if digital else None,
                submission_policy_event_id=event.pk if digital else None,
            )
    old = list(manager("referrals", "Referral").order_by("id").values())
    audits = list(manager("audit", "AuditEvent").values())
    executor = MigrationExecutor(db)
    executor.migrate([TARGET])
    apps = executor.loader.project_state([TARGET]).apps
    rows = list(manager("referrals", "Referral").order_by("id").values())
    assert [{key: row[key] for key in before} for before, row in zip(old, rows, strict=True)] == old
    assert list(manager("audit", "AuditEvent").values()) == audits
    for row in rows:
        assert row["acknowledged_by_id"] is None and row["administratively_closed_at"] is None
        assert row["administrative_version"] == 1
    MigrationExecutor(db).migrate([TARGET])
