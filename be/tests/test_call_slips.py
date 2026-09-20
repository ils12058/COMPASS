from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.core.management import call_command
from django.db import IntegrityError, close_old_connections, transaction
from django.test import Client, override_settings
from django.utils import timezone

from compass.accounts.models import Designation, Role, User, UserDesignation
from compass.appointments.models import Appointment
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.authentication.sessions import create_auth_session
from compass.call_slips.models import CallSlip, CallSlipDestinationType
from compass.call_slips.services import (
    CallSlipConfigurationConflict,
    CallSlipCreationConflict,
    CallSlipInterviewEndConflict,
    CallSlipNotFound,
    CallSlipNotPermitted,
    CallSlipReferralConflict,
    InvalidCallSlipInput,
    create_call_slip,
    list_call_slips,
    record_interview_ended,
)
from compass.counseling.models import CounselingEncounter, CounselingSharedSummary
from compass.ecounseling.models import ECounselingRoom
from compass.institutional_forms.models import FormFamily, FormRevision
from compass.institutional_forms.services import SUPPORTED_SCHEMA_VERSIONS
from compass.notifications.delivery import render_notification_email
from compass.notifications.models import EmailDelivery, Notification, NotificationPreference
from compass.notifications.policy import NotificationEvent, NotificationPolicy
from compass.organization.models import (
    Campus,
    College,
    CounselorResponsibility,
    StaffSupervision,
    StudentAffiliation,
)
from compass.referrals.models import ReferralAction
from compass.referrals.services import create_referral, record_action
from compass.routine_interviews.models import RoutineInterview


def sync_policy() -> None:
    call_command("sync_identity_policy", verbosity=0)


def ensure_call_slip_form_revision() -> None:
    family, _ = FormFamily.objects.get_or_create(
        key="call_slip",
        defaults={"title": "Interview Permit / Call Slip"},
    )
    FormRevision.objects.get_or_create(
        family=family,
        official_code="CNSC-OP-GTA-01F8",
        official_revision="0",
        defaults={
            "internal_schema_version": 1,
            "status": "ACTIVE",
        },
    )


def make_user(email: str, role: str) -> User:
    return User.objects.create_user(
        email=email,
        password="a-test-password",
        role=Role.objects.get(code=role),
        first_name=email.split("@")[0].replace(".", " ").title(),
        middle_name="",
        last_name="User",
    )


def make_head(email: str = "head@example.edu") -> User:
    user = make_user(email, "COUNSELOR")
    UserDesignation.objects.create(
        user=user,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )
    return user


def audit_context(actor: User) -> AuditContext:
    return AuditContext.user(actor)


def auth_client(user: User) -> Client:
    issued = create_auth_session(user, now=timezone.now())
    client = Client()
    client.cookies["compass_session"] = issued.token
    return client


def csrf(client: Client) -> dict[str, str]:
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    return {"HTTP_X_CSRFTOKEN": response.json()["csrf_token"]}


def setup_scope():
    campus = Campus.objects.create(code="MAIN", name="Main Campus")
    college_a = College.objects.create(campus=campus, code="A", name="College A")
    college_b = College.objects.create(campus=campus, code="B", name="College B")
    counselor_a = make_user("counselor.a@example.edu", "COUNSELOR")
    counselor_b = make_user("counselor.b@example.edu", "COUNSELOR")
    CounselorResponsibility.objects.create(college=college_a, counselor=counselor_a)
    CounselorResponsibility.objects.create(college=college_b, counselor=counselor_b)
    gss = make_user("gss@example.edu", "GUIDANCE_SERVICES_STAFF")
    StaffSupervision.objects.create(staff=gss, supervisor=counselor_a)
    student_a = make_user("student.a@example.edu", "STUDENT")
    student_b = make_user("student.b@example.edu", "STUDENT")
    StudentAffiliation.objects.create(student=student_a, college=college_a)
    StudentAffiliation.objects.create(student=student_b, college=college_b)
    return counselor_a, counselor_b, gss, student_a, student_b


def create_for(
    actor: User,
    student: User,
    *,
    key: str,
    fingerprint: str,
    report_at: datetime | None = None,
    course_year: str = "BSIS 4",
    destination_type: str = "GUIDANCE_OFFICE",
    other_destination: str = "",
    referral_id=None,
    notify_student: bool = False,
):
    return create_call_slip(
        actor=actor,
        student_id=student.pk,
        course_year=course_year,
        destination_type=destination_type,
        other_destination=other_destination,
        report_at=report_at or (timezone.now() + timedelta(days=1)),
        referral_id=referral_id,
        notify_student=notify_student,
        idempotency_key=key,
        request_fingerprint=fingerprint,
        context=audit_context(actor),
    )


def create_referral_for(actor: User, student: User, *, key: str, fingerprint: str):
    now = timezone.now()
    return create_referral(
        actor=actor,
        student_id=student.pk,
        course_year_block="BSIS 4A",
        reason="SENSITIVE-LINKED-REFERRAL-REASON",
        referrer_name="Source Referrer",
        referred_on=(now - timedelta(days=2)).date(),
        received_at=now - timedelta(days=1),
        idempotency_key=key,
        request_fingerprint=fingerprint,
        context=audit_context(actor),
        now=now,
    )


@pytest.mark.django_db
def test_call_slip_form_family_bootstraps_exact_historical_identity():
    family = FormFamily.objects.get(key="call_slip")
    revision = FormRevision.objects.get(
        family=family,
        official_code="CNSC-OP-GTA-01F8",
        official_revision="0",
    )
    assert family.title == "Interview Permit / Call Slip"
    assert revision.internal_schema_version == 1
    assert revision.status == "ACTIVE"
    assert SUPPORTED_SCHEMA_VERSIONS["call_slip"] == frozenset({1})


@pytest.mark.django_db
def test_uuid_only_identity_and_no_human_reference_counter():
    field_names = {field.name for field in CallSlip._meta.get_fields()}
    assert "reference_code" not in field_names
    assert "counter" not in field_names
    assert CallSlip._meta.get_field("id").get_internal_type() == "UUIDField"


@pytest.mark.django_db
def test_counselor_gss_and_head_issuer_and_scope_rules():
    sync_policy()
    counselor_a, counselor_b, gss, student_a, student_b = setup_scope()

    own = create_for(counselor_a, student_a, key="own", fingerprint="a" * 64)
    encoded = create_for(gss, student_a, key="gss", fingerprint="b" * 64)
    assert own.issued_by_id == counselor_a.pk
    assert own.recorded_by_id == counselor_a.pk
    assert encoded.issued_by_id == counselor_a.pk
    assert encoded.recorded_by_id == gss.pk

    with pytest.raises(CallSlipNotPermitted):
        create_for(
            counselor_a,
            student_b,
            key="out-of-scope",
            fingerprint="c" * 64,
        )

    head = make_head()
    head_item = create_for(head, student_b, key="head", fingerprint="d" * 64)
    assert head_item.issued_by_id == head.pk

    head_staff = make_user("head.staff@example.edu", "GUIDANCE_SERVICES_STAFF")
    StaffSupervision.objects.create(staff=head_staff, supervisor=head)
    inherited = create_for(
        head_staff,
        student_a,
        key="head-staff",
        fingerprint="e" * 64,
    )
    assert inherited.issued_by_id == head.pk

    assert {item.pk for item in list_call_slips(actor=counselor_a).items} == {
        own.pk,
        encoded.pk,
        inherited.pk,
    }
    assert {item.pk for item in list_call_slips(actor=counselor_b).items} == {
        head_item.pk,
    }
    assert head_item.pk in {item.pk for item in list_call_slips(actor=head).items}


@pytest.mark.django_db
def test_gss_requires_current_active_counselor_supervisor():
    sync_policy()
    counselor, _, gss, student, _ = setup_scope()
    StaffSupervision.objects.filter(staff=gss).delete()

    with pytest.raises(CallSlipNotPermitted, match="supervising Counselor"):
        create_for(gss, student, key="no-supervisor", fingerprint="a" * 64)

    StaffSupervision.objects.create(staff=gss, supervisor=counselor)
    counselor.is_active = False
    counselor.save(update_fields=["is_active", "updated_at"])
    with pytest.raises(CallSlipNotPermitted, match="active supervising Counselor"):
        create_for(gss, student, key="inactive-supervisor", fingerprint="b" * 64)


@pytest.mark.django_db
def test_create_requires_meaningful_course_year_and_active_student_target():
    sync_policy()
    head = make_head()
    student = make_user("student@example.edu", "STUDENT")
    admin = make_user("admin@example.edu", "IT_ADMIN")

    with pytest.raises(InvalidCallSlipInput, match="course_year is required"):
        create_for(
            head,
            student,
            key="blank-course",
            fingerprint="a" * 64,
            course_year="   ",
        )
    with pytest.raises(InvalidCallSlipInput, match="active Student"):
        create_for(
            head,
            admin,
            key="non-student",
            fingerprint="b" * 64,
        )
    student.is_active = False
    student.save(update_fields=["is_active", "updated_at"])
    with pytest.raises(InvalidCallSlipInput, match="active Student"):
        create_for(
            head,
            student,
            key="inactive-student",
            fingerprint="c" * 64,
        )


@pytest.mark.django_db
def test_destination_rules_report_at_history_and_snapshots_are_source_faithful():
    sync_policy()
    head = make_head()
    student = make_user("student@example.edu", "STUDENT")
    past = timezone.now() - timedelta(days=20)

    historical = create_for(
        head,
        student,
        key="historical",
        fingerprint="a" * 64,
        report_at=past,
        destination_type="OTHER",
        other_destination="Registrar Office",
    )
    assert historical.report_at == past
    assert historical.created_at > historical.report_at
    assert historical.other_destination == "Registrar Office"

    future = create_for(
        head,
        student,
        key="future",
        fingerprint="b" * 64,
        report_at=timezone.now() + timedelta(days=5),
    )
    assert future.destination_type == CallSlipDestinationType.GUIDANCE_OFFICE
    assert future.other_destination == ""

    with pytest.raises(InvalidCallSlipInput, match="must be empty"):
        create_for(
            head,
            student,
            key="bad-guidance",
            fingerprint="c" * 64,
            other_destination="Unexpected",
        )
    with pytest.raises(InvalidCallSlipInput, match="required for OTHER"):
        create_for(
            head,
            student,
            key="bad-other",
            fingerprint="d" * 64,
            destination_type="OTHER",
            other_destination="   ",
        )
    with pytest.raises(InvalidCallSlipInput, match="timezone-aware"):
        create_for(
            head,
            student,
            key="naive",
            fingerprint="e" * 64,
            report_at=datetime.now(),
        )

    student_snapshot = historical.student_name_snapshot
    issuer_snapshot = historical.issued_by_name_snapshot
    student.first_name = "Changed"
    student.save(update_fields=["first_name", "updated_at"])
    head.first_name = "Changed"
    head.save(update_fields=["first_name", "updated_at"])
    historical.refresh_from_db()
    assert historical.student_name_snapshot == student_snapshot
    assert historical.issued_by_name_snapshot == issuer_snapshot


@pytest.mark.django_db
def test_destination_database_constraint_preserves_source_invariant():
    sync_policy()
    head = make_head()
    student = make_user("student@example.edu", "STUDENT")
    revision = FormRevision.objects.get(family__key="call_slip", status="ACTIVE")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CallSlip.objects.create(
                student=student,
                student_name_snapshot=student.get_full_name(),
                course_year_snapshot="BSIS 4",
                destination_type="GUIDANCE_OFFICE",
                other_destination="Should fail",
                report_at=timezone.now(),
                issued_by=head,
                issued_by_name_snapshot=head.get_full_name(),
                form_revision=revision,
                recorded_by=head,
            )


@pytest.mark.django_db
def test_referral_link_requires_scope_same_student_action_and_one_to_one():
    sync_policy()
    counselor_a, counselor_b, _, student_a, student_b = setup_scope()
    referral = create_referral_for(
        counselor_a,
        student_a,
        key="ref-a",
        fingerprint="a" * 64,
    )

    with pytest.raises(CallSlipReferralConflict, match="does not record"):
        create_for(
            counselor_a,
            student_a,
            key="missing-action",
            fingerprint="b" * 64,
            referral_id=referral.pk,
        )
    assert ReferralAction.objects.filter(referral=referral).count() == 0

    record_action(
        actor=counselor_a,
        referral_id=referral.pk,
        action_type="SEND_CALL_SLIP_INTERVIEW_PERMIT",
        occurred_at=timezone.now(),
        remarks="Issued source row",
        context=audit_context(counselor_a),
    )
    linked = create_for(
        counselor_a,
        student_a,
        key="linked",
        fingerprint="c" * 64,
        referral_id=referral.pk,
    )
    assert linked.referral_id == referral.pk
    assert not hasattr(linked, "reason")
    assert ReferralAction.objects.filter(referral=referral).count() == 1

    with pytest.raises(CallSlipReferralConflict, match="already has"):
        create_for(
            counselor_a,
            student_a,
            key="duplicate-link",
            fingerprint="d" * 64,
            referral_id=referral.pk,
        )

    other_referral = create_referral_for(
        counselor_b,
        student_b,
        key="ref-b",
        fingerprint="e" * 64,
    )
    record_action(
        actor=counselor_b,
        referral_id=other_referral.pk,
        action_type="SEND_CALL_SLIP_INTERVIEW_PERMIT",
        occurred_at=timezone.now(),
        remarks="Issued",
        context=audit_context(counselor_b),
    )
    with pytest.raises(CallSlipNotFound):
        create_for(
            counselor_a,
            student_a,
            key="outside-referral",
            fingerprint="f" * 64,
            referral_id=other_referral.pk,
        )

    head = make_head("head.link@example.edu")
    with pytest.raises(CallSlipReferralConflict, match="different Student"):
        create_for(
            head,
            student_a,
            key="mismatch",
            fingerprint="1" * 64,
            referral_id=other_referral.pk,
        )


@pytest.mark.django_db
def test_call_slip_creation_never_creates_downstream_clinical_or_scheduling_records():
    sync_policy()
    head = make_head()
    student = make_user("student@example.edu", "STUDENT")
    create_for(head, student, key="boundary", fingerprint="a" * 64)

    assert Appointment.objects.count() == 0
    assert CounselingEncounter.objects.count() == 0
    assert CounselingSharedSummary.objects.count() == 0
    assert RoutineInterview.objects.count() == 0
    assert ECounselingRoom.objects.count() == 0


@pytest.mark.django_db
def test_create_persistent_idempotency_does_not_store_raw_key():
    sync_policy()
    head = make_head()
    student = make_user("student@example.edu", "STUDENT")

    first = create_for(head, student, key="private-retry-key", fingerprint="a" * 64)
    repeat = create_for(head, student, key="private-retry-key", fingerprint="a" * 64)
    assert repeat.pk == first.pk
    assert CallSlip.objects.count() == 1
    assert first.creation_key_digest != "private-retry-key"
    assert len(first.creation_key_digest) == 64

    with pytest.raises(CallSlipCreationConflict):
        create_for(head, student, key="private-retry-key", fingerprint="b" * 64)
    assert CallSlip.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_concurrent_same_actor_retry_creates_one_call_slip(monkeypatch):
    sync_policy()
    ensure_call_slip_form_revision()
    head = make_head()
    student = make_user("student@example.edu", "STUDENT")
    report_at = timezone.now() + timedelta(hours=2)
    monkeypatch.setattr(
        "compass.notifications.services._safe_kick_email_delivery",
        lambda delivery_id: None,
    )

    def worker():
        close_old_connections()
        try:
            actor = User.objects.select_related("role").get(pk=head.pk)
            target = User.objects.get(pk=student.pk)
            return create_for(
                actor,
                target,
                key="concurrent-retry",
                fingerprint="a" * 64,
                report_at=report_at,
                notify_student=True,
            ).pk
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(lambda _: worker(), range(2)))

    assert len(set(ids)) == 1
    assert CallSlip.objects.count() == 1
    assert Notification.objects.count() == 1
    assert EmailDelivery.objects.count() == 1


@pytest.mark.django_db
def test_form_revision_snapshot_survives_future_activation_and_unsupported_active_blocks_create():
    sync_policy()
    head = make_head()
    student = make_user("student@example.edu", "STUDENT")
    first = create_for(head, student, key="form-first", fingerprint="a" * 64)
    original_revision_id = first.form_revision_id

    family = FormFamily.objects.get(key="call_slip")
    FormRevision.objects.filter(family=family, status="ACTIVE").update(status="INACTIVE")
    unsupported = FormRevision.objects.create(
        family=family,
        official_code="CNSC-OP-GTA-01F8",
        official_revision="future-unsupported",
        internal_schema_version=2,
        status="ACTIVE",
    )
    with pytest.raises(CallSlipConfigurationConflict, match="not supported"):
        create_for(head, student, key="unsupported", fingerprint="b" * 64)

    unsupported.status = "INACTIVE"
    unsupported.save(update_fields=["status", "updated_at"])
    replacement = FormRevision.objects.create(
        family=family,
        official_code="CNSC-OP-GTA-01F8",
        official_revision="1",
        internal_schema_version=1,
        status="ACTIVE",
    )
    second = create_for(head, student, key="form-second", fingerprint="c" * 64)
    first.refresh_from_db()
    assert first.form_revision_id == original_revision_id
    assert second.form_revision_id == replacement.pk


@pytest.mark.django_db
def test_report_date_filters_use_institution_timezone_boundaries():
    sync_policy()
    head = make_head()
    student = make_user("student@example.edu", "STUDENT")

    with override_settings(TIME_ZONE="Asia/Manila"):
        local = ZoneInfo("Asia/Manila")
        included = create_for(
            head,
            student,
            key="included",
            fingerprint="a" * 64,
            report_at=datetime(2026, 9, 21, 0, 30, tzinfo=local),
        )
        create_for(
            head,
            student,
            key="previous-day",
            fingerprint="b" * 64,
            report_at=datetime(2026, 9, 20, 23, 30, tzinfo=local),
        )
        page = list_call_slips(
            actor=head,
            from_date=datetime(2026, 9, 21).date(),
            to_date=datetime(2026, 9, 21).date(),
        )
    assert [item.pk for item in page.items] == [included.pk]


@pytest.mark.django_db
def test_interview_end_is_aware_nonfuture_immutable_and_instant_idempotent():
    sync_policy()
    head = make_head()
    student = make_user("student@example.edu", "STUDENT")
    item = create_for(
        head,
        student,
        key="end",
        fingerprint="a" * 64,
        report_at=timezone.now() + timedelta(hours=3),
    )
    now = timezone.now()
    ended = now - timedelta(minutes=10)

    first = record_interview_ended(
        actor=head,
        call_slip_id=item.pk,
        interview_ended_at=ended,
        context=audit_context(head),
        now=now,
    )
    assert first.interview_ended_at == ended

    same_instant_utc = ended.astimezone(UTC)
    retry = record_interview_ended(
        actor=head,
        call_slip_id=item.pk,
        interview_ended_at=same_instant_utc,
        context=audit_context(head),
        now=now,
    )
    assert retry.interview_ended_at == ended

    with pytest.raises(CallSlipInterviewEndConflict):
        record_interview_ended(
            actor=head,
            call_slip_id=item.pk,
            interview_ended_at=ended - timedelta(minutes=1),
            context=audit_context(head),
            now=now,
        )
    with pytest.raises(InvalidCallSlipInput, match="future"):
        record_interview_ended(
            actor=head,
            call_slip_id=create_for(
                head,
                student,
                key="future-end-record",
                fingerprint="b" * 64,
            ).pk,
            interview_ended_at=now + timedelta(minutes=1),
            context=audit_context(head),
            now=now,
        )
    with pytest.raises(InvalidCallSlipInput, match="timezone-aware"):
        record_interview_ended(
            actor=head,
            call_slip_id=create_for(
                head,
                student,
                key="naive-end-record",
                fingerprint="c" * 64,
            ).pk,
            interview_ended_at=datetime.now(),
            context=audit_context(head),
            now=now,
        )
    assert CounselingEncounter.objects.count() == 0
    assert RoutineInterview.objects.count() == 0
    assert Appointment.objects.count() == 0


@pytest.mark.django_db
def test_audit_metadata_excludes_source_and_referral_sensitive_text():
    sync_policy()
    head = make_head()
    student = make_user("student@example.edu", "STUDENT")
    referral = create_referral_for(head, student, key="audit-ref", fingerprint="a" * 64)
    record_action(
        actor=head,
        referral_id=referral.pk,
        action_type="SEND_CALL_SLIP_INTERVIEW_PERMIT",
        occurred_at=timezone.now(),
        remarks="SENSITIVE-REFERRAL-ACTION-REMARK",
        context=audit_context(head),
    )
    item = create_for(
        head,
        student,
        key="audit-call",
        fingerprint="b" * 64,
        course_year="SENSITIVE-COURSE-YEAR",
        destination_type="OTHER",
        other_destination="SENSITIVE-OTHER-DESTINATION",
        referral_id=referral.pk,
    )
    record_interview_ended(
        actor=head,
        call_slip_id=item.pk,
        interview_ended_at=timezone.now() - timedelta(minutes=1),
        context=audit_context(head),
    )

    serialized = json.dumps(
        list(
            AuditEvent.objects.filter(action__startswith="call_slip.").values_list(
                "metadata", flat=True
            )
        )
    )
    for marker in (
        "SENSITIVE-COURSE-YEAR",
        "SENSITIVE-OTHER-DESTINATION",
        "SENSITIVE-LINKED-REFERRAL-REASON",
        "SENSITIVE-REFERRAL-ACTION-REMARK",
        item.student_name_snapshot,
        item.issued_by_name_snapshot,
    ):
        assert marker not in serialized


@pytest.mark.django_db
def test_student_self_api_is_safe_and_operational_api_keeps_referral_content_separate():
    sync_policy()
    head = make_head()
    student = make_user("student@example.edu", "STUDENT")
    other_student = make_user("other@example.edu", "STUDENT")
    referral = create_referral_for(head, student, key="self-ref", fingerprint="a" * 64)
    record_action(
        actor=head,
        referral_id=referral.pk,
        action_type="SEND_CALL_SLIP_INTERVIEW_PERMIT",
        occurred_at=timezone.now(),
        remarks="Source action",
        context=audit_context(head),
    )
    item = create_for(
        head,
        student,
        key="self-call",
        fingerprint="b" * 64,
        referral_id=referral.pk,
    )
    create_for(head, other_student, key="other-call", fingerprint="c" * 64)

    student_client = auth_client(student)
    mine = student_client.get("/api/v1/call-slips/me")
    assert mine.status_code == 200
    assert [row["id"] for row in mine.json()["items"]] == [str(item.pk)]
    row = mine.json()["items"][0]
    assert "referral" not in row
    assert "recorded_by" not in row
    assert "SENSITIVE-LINKED-REFERRAL-REASON" not in json.dumps(row)

    detail = student_client.get(f"/api/v1/call-slips/me/{item.pk}")
    assert detail.status_code == 200
    assert "referral" not in detail.json()
    assert "recorded_by" not in detail.json()

    other_item = CallSlip.objects.exclude(student=student).first()
    denied_other = student_client.get(f"/api/v1/call-slips/me/{other_item.pk}")
    assert denied_other.status_code == 404

    denied_end = student_client.patch(
        f"/api/v1/call-slips/{item.pk}/interview-ended",
        data=json.dumps({"interview_ended_at": timezone.now().isoformat()}),
        content_type="application/json",
        **csrf(student_client),
    )
    assert denied_end.status_code == 403

    guidance_client = auth_client(head)
    operational = guidance_client.get(f"/api/v1/call-slips/{item.pk}")
    assert operational.status_code == 200
    assert operational.json()["referral"] == {
        "id": str(referral.pk),
        "reference_code": referral.reference_code,
    }
    assert "reason" not in operational.json()["referral"]


@pytest.mark.django_db
def test_student_it_admin_and_dpo_cannot_create_or_read_operational_content():
    sync_policy()
    head = make_head()
    student = make_user("student@example.edu", "STUDENT")
    admin = make_user("admin@example.edu", "IT_ADMIN")
    dpo = make_user("dpo@example.edu", "IT_ADMIN")
    UserDesignation.objects.create(
        user=dpo,
        designation=Designation.objects.get(code="DPO"),
    )
    item = create_for(head, student, key="authorization", fingerprint="a" * 64)

    assert student.has_capability("call_slips.view_self")
    assert not student.has_capability("call_slips.manage")
    assert not admin.has_capability("call_slips.view")
    assert not dpo.has_capability("call_slips.view")

    for user in (admin, dpo):
        client = auth_client(user)
        assert client.get("/api/v1/call-slips").status_code == 403
        assert client.get(f"/api/v1/call-slips/{item.pk}").status_code == 403

    student_client = auth_client(student)
    payload = {
        "student_id": str(student.pk),
        "course_year": "BSIS 4",
        "destination_type": "GUIDANCE_OFFICE",
        "other_destination": "",
        "report_at": (timezone.now() + timedelta(hours=1)).isoformat(),
        "referral_id": None,
    }
    create_response = student_client.post(
        "/api/v1/call-slips",
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="student-forbidden",
        **csrf(student_client),
    )
    assert create_response.status_code == 403


@pytest.mark.django_db
def test_create_api_uses_server_resolved_issuer_and_does_not_accept_issued_by_override():
    sync_policy()
    counselor, _, _, student, _ = setup_scope()
    client = auth_client(counselor)
    headers = csrf(client)
    payload = {
        "student_id": str(student.pk),
        "course_year": "BSIS 4",
        "destination_type": "GUIDANCE_OFFICE",
        "other_destination": "",
        "report_at": (timezone.now() + timedelta(hours=1)).isoformat(),
        "referral_id": None,
    }
    created = client.post(
        "/api/v1/call-slips",
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="api-create",
        **headers,
    )
    assert created.status_code == 201
    assert created.json()["issued_by"]["id"] == str(counselor.pk)
    created_id = created.json()["id"]
    notification = Notification.objects.get(source_id=created_id)
    assert notification.recipient_id == student.pk
    assert EmailDelivery.objects.filter(notification=notification).count() == 1

    payload["issued_by_id"] = str(counselor.pk)
    rejected = client.post(
        "/api/v1/call-slips",
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="api-issued-by-injection",
        **headers,
    )
    assert rejected.status_code == 422


@pytest.mark.django_db
def test_live_call_slip_creates_one_mandatory_notification_and_email_delivery():
    sync_policy()
    head = make_head("head.notification@example.edu")
    student = make_user("student.notification@example.edu", "STUDENT")

    item = create_for(
        head,
        student,
        key="live-notification",
        fingerprint="1" * 64,
        notify_student=True,
    )

    notification = Notification.objects.get()
    delivery = EmailDelivery.objects.get()
    assert notification.recipient_id == student.pk
    assert notification.event_code == NotificationEvent.CALL_SLIP_ISSUED
    assert notification.policy == NotificationPolicy.MANDATORY_OPERATIONAL
    assert notification.source_type == "call_slip"
    assert notification.source_id == item.pk
    assert notification.target_type == "CALL_SLIP"
    assert notification.target_id == item.pk
    assert delivery.notification_id == notification.pk
    assert delivery.status == "PENDING"


@pytest.mark.django_db
def test_historical_back_entry_explicitly_suppresses_notification_regardless_of_report_time():
    sync_policy()
    head = make_head("head.history@example.edu")
    student = make_user("student.history@example.edu", "STUDENT")

    item = create_for(
        head,
        student,
        key="history-no-notify",
        fingerprint="2" * 64,
        report_at=timezone.now() - timedelta(days=90),
        notify_student=False,
    )

    assert CallSlip.objects.filter(pk=item.pk).exists()
    assert Notification.objects.count() == 0
    assert EmailDelivery.objects.count() == 0


@pytest.mark.django_db
def test_call_slip_idempotent_retry_does_not_duplicate_notification_intent():
    sync_policy()
    head = make_head("head.retry@example.edu")
    student = make_user("student.retry@example.edu", "STUDENT")

    first = create_for(
        head,
        student,
        key="notify-retry",
        fingerprint="3" * 64,
        notify_student=True,
    )
    repeated = create_for(
        head,
        student,
        key="notify-retry",
        fingerprint="3" * 64,
        notify_student=True,
    )

    assert repeated.pk == first.pk
    assert CallSlip.objects.count() == 1
    assert Notification.objects.count() == 1
    assert EmailDelivery.objects.count() == 1


@pytest.mark.django_db
def test_call_slip_same_idempotency_key_conflicts_when_notification_intent_changes():
    sync_policy()
    head = make_head("head.intent@example.edu")
    student = make_user("student.intent@example.edu", "STUDENT")

    create_for(
        head,
        student,
        key="intent-conflict",
        fingerprint="4" * 64,
        notify_student=True,
    )
    with pytest.raises(CallSlipCreationConflict):
        create_for(
            head,
            student,
            key="intent-conflict",
            fingerprint="5" * 64,
            notify_student=False,
        )


@pytest.mark.django_db
def test_live_call_slip_rolls_back_when_durable_notification_intent_fails(monkeypatch):
    sync_policy()
    head = make_head("head.atomic@example.edu")
    student = make_user("student.atomic@example.edu", "STUDENT")

    def fail_notification(**kwargs):
        raise RuntimeError("synthetic durable notification persistence failure")

    monkeypatch.setattr(
        "compass.call_slips.services.create_notification_for_event",
        fail_notification,
    )
    with pytest.raises(RuntimeError, match="durable notification"):
        create_for(
            head,
            student,
            key="atomic-failure",
            fingerprint="6" * 64,
            notify_student=True,
        )

    assert CallSlip.objects.count() == 0
    assert Notification.objects.count() == 0
    assert EmailDelivery.objects.count() == 0
    assert AuditEvent.objects.filter(action="call_slip.created").count() == 0


@pytest.mark.django_db
def test_mandatory_call_slip_email_bypasses_optional_email_preference():
    sync_policy()
    head = make_head("head.preference@example.edu")
    student = make_user("student.preference@example.edu", "STUDENT")
    NotificationPreference.objects.create(
        user=student,
        optional_email_enabled=False,
    )

    create_for(
        head,
        student,
        key="mandatory-preference",
        fingerprint="7" * 64,
        notify_student=True,
    )

    notification = Notification.objects.get()
    assert notification.policy == NotificationPolicy.MANDATORY_OPERATIONAL
    assert EmailDelivery.objects.filter(notification=notification).count() == 1


@pytest.mark.django_db
def test_call_slip_notification_and_email_do_not_copy_sensitive_source_content():
    sync_policy()
    head = make_head("head.privacy@example.edu")
    student = make_user("student.privacy@example.edu", "STUDENT")
    referral = create_referral_for(
        head,
        student,
        key="privacy-referral",
        fingerprint="8" * 64,
    )
    record_action(
        actor=head,
        referral_id=referral.pk,
        action_type="SEND_CALL_SLIP_INTERVIEW_PERMIT",
        occurred_at=timezone.now(),
        remarks="SENSITIVE-REFERRAL-ACTION-REMARK",
        context=audit_context(head),
    )

    create_for(
        head,
        student,
        key="privacy-call-slip",
        fingerprint="9" * 64,
        course_year="SENSITIVE-COURSE-YEAR",
        destination_type="OTHER",
        other_destination="SENSITIVE-CUSTOM-DESTINATION",
        referral_id=referral.pk,
        notify_student=True,
    )

    notification = Notification.objects.get()
    rendered = render_notification_email(NotificationEvent.CALL_SLIP_ISSUED)
    serialized = "\n".join(
        [
            notification.title,
            notification.message,
            rendered.subject,
            rendered.text_body,
            rendered.html_body,
        ]
    )
    for marker in (
        "SENSITIVE-LINKED-REFERRAL-REASON",
        "SENSITIVE-REFERRAL-ACTION-REMARK",
        "SENSITIVE-COURSE-YEAR",
        "SENSITIVE-CUSTOM-DESTINATION",
    ):
        assert marker not in serialized
        assert marker not in " ".join(
            str(value) for value in EmailDelivery.objects.values().get().values()
        )


@pytest.mark.django_db
def test_call_slip_api_fingerprint_includes_notify_student_command_intent():
    sync_policy()
    counselor, _, _, student, _ = setup_scope()
    client = auth_client(counselor)
    headers = csrf(client)
    payload = {
        "student_id": str(student.pk),
        "course_year": "BSIS 4",
        "destination_type": "GUIDANCE_OFFICE",
        "other_destination": "",
        "report_at": (timezone.now() + timedelta(hours=1)).isoformat(),
        "referral_id": None,
        "notify_student": True,
    }
    first = client.post(
        "/api/v1/call-slips",
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="notify-intent-api",
        **headers,
    )
    assert first.status_code == 201

    payload["notify_student"] = False
    conflict = client.post(
        "/api/v1/call-slips",
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="notify-intent-api",
        **headers,
    )
    assert conflict.status_code == 409


@pytest.mark.django_db
def test_operational_call_slip_search_is_identity_reference_only_and_scope_first():
    sync_policy()
    counselor_a, counselor_b, _, student_a, student_b = setup_scope()
    student_a.institutional_id = "CS-A-001"
    student_b.institutional_id = "CS-B-001"
    student_a.save(update_fields=["institutional_id", "updated_at"])
    student_b.save(update_fields=["institutional_id", "updated_at"])

    item_a = create_for(counselor_a, student_a, key="search-a", fingerprint="a" * 64)
    create_for(counselor_b, student_b, key="search-b", fingerprint="b" * 64)

    client_a = auth_client(counselor_a)
    by_id = client_a.get("/api/v1/call-slips", {"search": "CS-A-001"})
    assert by_id.status_code == 200
    assert [row["id"] for row in by_id.json()["items"]] == [str(item_a.pk)]

    out_of_scope = client_a.get("/api/v1/call-slips", {"search": "CS-B-001"})
    assert out_of_scope.status_code == 200
    assert out_of_scope.json()["items"] == []

    head = make_head("call-search-head@example.edu")
    referral = create_referral_for(head, student_a, key="search-ref", fingerprint="c" * 64)
    linked = create_for(
        head,
        student_a,
        key="search-linked",
        fingerprint="d" * 64,
        referral_id=referral.pk,
    )
    by_reference = auth_client(head).get(
        "/api/v1/call-slips",
        {"search": referral.reference_code},
    )
    assert by_reference.status_code == 200
    assert str(linked.pk) in {row["id"] for row in by_reference.json()["items"]}

    assert (
        client_a.get(
            "/api/v1/call-slips",
            {"search": "x" * 161},
        ).status_code
        == 422
    )
