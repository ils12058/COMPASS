"""CW-4 lifecycle boundaries across Privacy activity and independent audience resources."""

import json
from dataclasses import asdict
from uuid import uuid4

import pytest

from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.audit.services import record_event
from compass.counseling.case_closure_services import close_case, reopen_case
from compass.counseling.student_session_summaries import (
    list_my_student_session_summaries,
    publish_assigned_student_session_summary,
    put_assigned_student_session_summary,
)
from compass.notifications.models import Notification
from compass.privacy_governance.activity import _present, list_privacy_activity
from compass.referrals import faculty_services
from compass.referrals.models import Referral
from tests.faculty_referral_helpers import make_world, submit
from tests.test_counseling import context, create_counseling_service, make_user
from tests.test_counseling_cases import intake, link, record
from tests.test_cw3_transfers import transfer_world

pytestmark = pytest.mark.django_db


def test_lifecycle_privacy_activity_has_reference_and_no_closure_content(settings):
    w = transfer_world(settings, "cw4-privacy")
    note = "Private closure note never available to office projections."
    close_case(
        actor=w.a,
        case_id=w.case.pk,
        expected_version=w.case.version,
        reason="CONTACT_NOT_REESTABLISHED",
        outcome="NOT_ASSESSED",
        note=note,
    )
    w.case.refresh_from_db()
    reopen_case(
        actor=w.a,
        case_id=w.case.pk,
        expected_version=w.case.version,
        reason="SAME_CONCERN_RETURNED",
    )
    page = list_privacy_activity()
    items = [
        item
        for item in page.items
        if item.type in {"counseling.case.closed", "counseling.case.reopened"}
    ]
    assert {item.type for item in items} == {"counseling.case.closed", "counseling.case.reopened"}
    assert all(item.resource_reference == w.case.reference_code for item in items)
    projection = json.dumps([asdict(item) for item in items], default=str)
    for private in (note, "CONTACT_NOT_REESTABLISHED", "NOT_ASSESSED", str(w.student.pk)):
        assert private not in projection
    assert not Notification.objects.exists()


@pytest.mark.parametrize("invalid", ["target", "closure_id", "version", "reference_code"])
def test_malformed_lifecycle_evidence_is_not_projected(settings, invalid):
    w = transfer_world(settings, "cw4-malformed")
    metadata = {
        "case_id": str(w.case.pk),
        "closure_id": str(uuid4()),
        "version": 2,
        "reference_code": w.case.reference_code,
    }
    target = "counseling.case"
    if invalid == "target":
        target = "accounts.user"
    else:
        metadata[invalid] = "untrusted narrative instead of a bounded identifier"
    event = record_event(
        context=AuditContext.user(w.a),
        action="counseling.case.closed",
        outcome="SUCCESS",
        target_type=target,
        target_id=w.case.pk,
        metadata=metadata,
    )
    assert _present(event) is None


def test_faculty_referral_and_student_summary_are_identical_across_case_cycles(
    settings, monkeypatch
):
    w = make_world(monkeypatch)
    create_counseling_service(w.admin)
    owner = make_user("cw4-audience-owner@synthetic.test", "COUNSELOR")
    case = intake(owner, w.student)
    encounter = record(owner, w.student)
    link(owner, case, encounter)
    put_assigned_student_session_summary(
        counselor=owner,
        encounter_id=encounter.pk,
        content="Separately published Student resource.",
    )
    publish_assigned_student_session_summary(
        counselor=owner, encounter_id=encounter.pk, context=context(owner)
    )
    submitted, _ = submit(w)
    referral = Referral.objects.get(pk=submitted["id"])
    before_referral = {
        field.attname: getattr(referral, field.attname) for field in referral._meta.concrete_fields
    }
    before_student = [
        item.pk for item in list_my_student_session_summaries(student=w.student).items
    ]
    before_notifications = Notification.objects.count()
    args = {"actor": w.faculty, "actor_session": w.issued.session, "referral_id": referral.pk}
    faculty_before = faculty_services.get_own_submission(**args)
    for reason in ("PLANNED_SUPPORT_CONCLUDED", "CONTACT_NOT_REESTABLISHED"):
        case.refresh_from_db()
        close_case(
            actor=owner,
            case_id=case.pk,
            expected_version=case.version,
            reason=reason,
            outcome="GOALS_PARTLY_MET",
            note="Documented synthetic contact attempts remain private.",
        )
        assert faculty_services.get_own_submission(**args) == faculty_before
        assert [
            item.pk for item in list_my_student_session_summaries(student=w.student).items
        ] == before_student
        case.refresh_from_db()
        reopen_case(
            actor=owner,
            case_id=case.pk,
            expected_version=case.version,
            reason="FURTHER_SUPPORT_NEEDED",
        )
    referral.refresh_from_db()
    assert {
        field.attname: getattr(referral, field.attname) for field in referral._meta.concrete_fields
    } == before_referral
    assert Notification.objects.count() == before_notifications
    assert (
        AuditEvent.objects.filter(action="counseling.case.closed", target_id=str(case.pk)).count()
        == 2
    )
