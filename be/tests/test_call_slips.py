from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone as dt_timezone
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
    get_call_slip,
    list_call_slips,
    record_interview_ended,
)
from compass.counseling.models import CounselingEncounter, CounselingSharedSummary
from compass.ecounseling.models import ECounselingRoom
from compass.institutional_forms.models import FormFamily, FormRevision
from compass.institutional_forms.services import SUPPORTED_SCHEMA_VERSIONS
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
):
    return create_call_slip(
        actor=actor,
        student_id=student.pk,
        course_year=course_year,
        destination_type=destination_type,
        other_destination=other_destination,
        report_at=report_at or (timezone.now() + timedelta(days=1)),
        referral_id=referral_id,
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
    }
    assert {item.pk for item in list_call_slips(actor=counselor_b).items} == set()
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
            student_b,
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
def test_concurrent_same_actor_retry_creates_one_call_slip():
    sync_policy()
    head = make_head()
    student = make_user("student@example.edu", "STUDENT")
    report_at = timezone.now() + timedelta(hours=2)

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
            ).pk
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(lambda _: worker(), range(2)))

    assert len(set(ids)) == 1
    assert CallSlip.objects.count() == 1


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

    same_instant_utc = ended.astimezone(dt_timezone.utc)
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

    payload["issued_by_id"] = str(counselor.pk)
    rejected = client.post(
        "/api/v1/call-slips",
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="api-issued-by-injection",
        **headers,
    )
    assert rejected.status_code == 422
