from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.core.management import call_command
from django.db import close_old_connections
from django.test import Client, override_settings
from django.utils import timezone

from compass.accounts.models import Designation, Role, User, UserDesignation
from compass.appointments.models import Appointment, AppointmentReferenceCounter
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.authentication.sessions import create_auth_session
from compass.counseling.models import CounselingEncounter
from compass.institutional_forms.models import FormFamily, FormRevision
from compass.institutional_forms.services import SUPPORTED_SCHEMA_VERSIONS
from compass.organization.models import (
    Campus,
    College,
    CounselorResponsibility,
    StaffSupervision,
    StudentAffiliation,
)
from compass.referrals.models import Referral, ReferralAction, ReferralReferenceCounter
from compass.referrals.services import (
    InvalidReferralInput,
    ReferralActionConflict,
    ReferralConfigurationConflict,
    ReferralCreationConflict,
    ReferralNotFound,
    ReferralNotPermitted,
    ReferralReferenceConflict,
    create_referral,
    get_referral,
    list_referrals,
    record_action,
    update_status_note,
)
from compass.routine_interviews.models import RoutineInterview


def sync_policy() -> None:
    call_command("sync_identity_policy", verbosity=0)


def ensure_referral_form_revision() -> None:
    family, _ = FormFamily.objects.get_or_create(
        key="referral_slip",
        defaults={"title": "Referral Slip"},
    )
    FormRevision.objects.get_or_create(
        family=family,
        official_code="CNSC-OP-GTA-01F9",
        official_revision="1",
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


def context(actor: User) -> AuditContext:
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
    unaffiliated = make_user("student.none@example.edu", "STUDENT")
    StudentAffiliation.objects.create(student=student_a, college=college_a)
    StudentAffiliation.objects.create(student=student_b, college=college_b)
    return counselor_a, counselor_b, gss, student_a, student_b, unaffiliated


def create_for(
    actor: User,
    student: User,
    *,
    key: str,
    fingerprint: str,
    now: datetime | None = None,
    received_at: datetime | None = None,
    reason: str = "Source referral reason",
    referrer_name: str = "Prof. Source Referrer",
):
    current = now or timezone.now()
    return create_referral(
        actor=actor,
        student_id=student.pk,
        course_year_block="BSIS 4A",
        reason=reason,
        referrer_name=referrer_name,
        referred_on=(current - timedelta(days=3)).astimezone(ZoneInfo("UTC")).date(),
        received_at=received_at,
        idempotency_key=key,
        request_fingerprint=fingerprint,
        context=context(actor),
        now=current,
    )


@pytest.mark.django_db
def test_referral_form_family_bootstraps_exact_historical_qms_identity():
    family = FormFamily.objects.get(key="referral_slip")
    revision = FormRevision.objects.get(
        family=family,
        official_code="CNSC-OP-GTA-01F9",
        official_revision="1",
    )
    assert family.title == "Referral Slip"
    assert revision.internal_schema_version == 1
    assert revision.status == "ACTIVE"
    assert SUPPORTED_SCHEMA_VERSIONS["referral_slip"] == frozenset({1})


@pytest.mark.django_db
def test_back_entered_referral_preserves_referred_received_and_created_chronology():
    sync_policy()
    head = make_head()
    student = make_user("student@example.edu", "STUDENT")
    now = timezone.now()
    received_at = now - timedelta(days=1)
    item = create_for(
        head,
        student,
        key="chronology-key",
        fingerprint="a" * 64,
        now=now,
        received_at=received_at,
    )
    item.refresh_from_db()

    assert item.referred_on < item.received_at.date()
    assert item.received_at == received_at
    assert item.created_at > item.received_at
    assert timezone.is_aware(item.received_at)

    original_received = item.received_at
    Referral.objects.filter(pk=item.pk).update(created_at=item.created_at + timedelta(minutes=1))
    item.refresh_from_db()
    assert item.received_at == original_received


@pytest.mark.django_db
def test_received_at_is_optional_but_naive_or_invalid_chronology_is_rejected():
    sync_policy()
    head = make_head()
    student = make_user("student@example.edu", "STUDENT")
    now = timezone.now()

    item = create_for(head, student, key="no-receipt", fingerprint="a" * 64, now=now)
    assert item.received_at is None

    with pytest.raises(InvalidReferralInput, match="timezone-aware"):
        create_for(
            head,
            student,
            key="naive-receipt",
            fingerprint="b" * 64,
            now=now,
            received_at=datetime.now(),
        )
    with pytest.raises(InvalidReferralInput, match="future"):
        create_for(
            head,
            student,
            key="future-receipt",
            fingerprint="c" * 64,
            now=now,
            received_at=now + timedelta(hours=1),
        )
    with pytest.raises(InvalidReferralInput, match="earlier than referred_on"):
        create_referral(
            actor=head,
            student_id=student.pk,
            course_year_block="BSIS 4A",
            reason="Reason",
            referrer_name="Referrer",
            referred_on=(now - timedelta(days=1)).date(),
            received_at=now - timedelta(days=2),
            idempotency_key="bad-order",
            request_fingerprint="d" * 64,
            context=context(head),
            now=now,
        )


@pytest.mark.django_db
def test_create_is_persistently_idempotent_and_received_at_participates_in_request_identity():
    sync_policy()
    head = make_head()
    student = make_user("student@example.edu", "STUDENT")
    received_at = timezone.now() - timedelta(hours=3)

    first = create_for(
        head,
        student,
        key="retry-key",
        fingerprint="a" * 64,
        received_at=received_at,
    )
    repeat = create_for(
        head,
        student,
        key="retry-key",
        fingerprint="a" * 64,
        received_at=received_at,
    )
    assert repeat.pk == first.pk
    assert repeat.reference_code == first.reference_code
    assert repeat.received_at == first.received_at
    assert Referral.objects.count() == 1
    assert first.creation_key_digest != "retry-key"
    assert len(first.creation_key_digest) == 64

    with pytest.raises(ReferralCreationConflict):
        create_for(
            head,
            student,
            key="retry-key",
            fingerprint="b" * 64,
            received_at=received_at + timedelta(minutes=1),
        )
    assert Referral.objects.count() == 1


@pytest.mark.django_db
def test_reference_sequence_is_yearly_independent_from_appointments_and_exhaustion_is_controlled():
    sync_policy()
    head = make_head()
    student = make_user("student@example.edu", "STUDENT")
    AppointmentReferenceCounter.objects.create(year=2026, next_value=58)

    with override_settings(TIME_ZONE="Asia/Manila"):
        first_now = datetime(2026, 12, 31, 23, 30, tzinfo=ZoneInfo("Asia/Manila"))
        second_now = datetime(2027, 1, 1, 0, 30, tzinfo=ZoneInfo("Asia/Manila"))
        first = create_referral(
            actor=head,
            student_id=student.pk,
            course_year_block="BSIS 4A",
            reason="First",
            referrer_name="Referrer",
            referred_on=first_now.date(),
            received_at=first_now - timedelta(minutes=30),
            idempotency_key="year-one",
            request_fingerprint="a" * 64,
            context=context(head),
            now=first_now,
        )
        second = create_referral(
            actor=head,
            student_id=student.pk,
            course_year_block="BSIS 4A",
            reason="Second",
            referrer_name="Referrer",
            referred_on=second_now.date(),
            received_at=second_now,
            idempotency_key="year-two",
            request_fingerprint="b" * 64,
            context=context(head),
            now=second_now,
        )

    assert first.reference_code == "REF-2026-000001"
    assert second.reference_code == "REF-2027-000001"
    assert AppointmentReferenceCounter.objects.get(year=2026).next_value == 58

    ReferralReferenceCounter.objects.update_or_create(year=2028, defaults={"next_value": 1_000_000})
    future = datetime(2028, 1, 2, 12, tzinfo=ZoneInfo("UTC"))
    with pytest.raises(ReferralReferenceConflict, match="exhausted"):
        create_referral(
            actor=head,
            student_id=student.pk,
            course_year_block="BSIS 4A",
            reason="Exhausted",
            referrer_name="Referrer",
            referred_on=future.date(),
            received_at=future,
            idempotency_key="exhausted",
            request_fingerprint="c" * 64,
            context=context(head),
            now=future,
        )


@pytest.mark.django_db
def test_referral_scope_is_current_organization_scope_without_assigned_counselor_field():
    sync_policy()
    counselor_a, counselor_b, gss, student_a, student_b, unaffiliated = setup_scope()
    head = make_head()
    now = timezone.now()

    student_a.institutional_id = "REF-A-001"
    student_a.first_name = "Alpha"
    student_a.middle_name = "ReferralMiddle"
    student_a.last_name = "Student"
    student_a.save(
        update_fields=[
            "institutional_id",
            "first_name",
            "middle_name",
            "last_name",
            "updated_at",
        ]
    )
    student_b.institutional_id = "REF-B-001"
    student_b.first_name = "Beta"
    student_b.last_name = "Outside"
    student_b.save(
        update_fields=[
            "institutional_id",
            "first_name",
            "last_name",
            "updated_at",
        ]
    )

    a = create_for(counselor_a, student_a, key="a", fingerprint="a" * 64, now=now)
    b = create_for(counselor_b, student_b, key="b", fingerprint="b" * 64, now=now)
    gss_item = create_for(gss, student_a, key="gss", fingerprint="c" * 64, now=now)

    assert {item.pk for item in list_referrals(actor=counselor_a).items} == {a.pk, gss_item.pk}
    assert {item.pk for item in list_referrals(actor=gss).items} == {a.pk, gss_item.pk}
    assert {item.pk for item in list_referrals(actor=counselor_b).items} == {b.pk}
    assert {item.pk for item in list_referrals(actor=head).items} == {a.pk, b.pk, gss_item.pk}

    student_a.first_name = "Current"
    student_a.middle_name = "LiveMiddle"
    student_a.last_name = "Identity"
    student_a.save(
        update_fields=[
            "first_name",
            "middle_name",
            "last_name",
            "updated_at",
        ]
    )

    assert [
        item.pk for item in list_referrals(actor=counselor_a, search=a.reference_code).items
    ] == [a.pk]
    for term in ("REF-A-001", "Current", "LiveMiddle", "Identity", "Alpha ReferralMiddle"):
        assert {item.pk for item in list_referrals(actor=counselor_a, search=term).items} == {
            a.pk,
            gss_item.pk,
        }
    assert {
        item.pk for item in list_referrals(actor=counselor_a, student_id=student_a.pk).items
    } == {
        a.pk,
        gss_item.pk,
    }
    assert list_referrals(actor=counselor_a, search="REF-B-001").items == ()
    assert list_referrals(actor=counselor_a, student_id=student_b.pk).items == ()

    overlong = auth_client(counselor_a).get(
        "/api/v1/referrals",
        {"search": "x" * 161},
    )
    assert overlong.status_code == 422
    assert overlong.json()["error"]["code"] == "invalid_referral_request"

    with pytest.raises(ReferralNotFound):
        get_referral(actor=counselor_a, referral_id=b.pk)
    with pytest.raises(ReferralNotPermitted):
        create_for(
            counselor_a,
            student_b,
            key="wrong-scope",
            fingerprint="d" * 64,
            now=now,
        )
    with pytest.raises(ReferralNotPermitted):
        create_for(
            counselor_a,
            unaffiliated,
            key="unaffiliated",
            fingerprint="e" * 64,
            now=now,
        )


@pytest.mark.django_db
def test_status_and_exact_three_actions_are_source_shaped_immutable_and_side_effect_free():
    sync_policy()
    head = make_head()
    student = make_user("student@example.edu", "STUDENT")
    now = timezone.now()
    received = now - timedelta(hours=3)
    item = create_for(
        head,
        student,
        key="actions",
        fingerprint="a" * 64,
        now=now,
        received_at=received,
    )
    identity = (
        item.reference_code,
        item.student_id,
        item.reason,
        item.referrer_name,
        item.referred_on,
        item.received_at,
        item.form_revision_id,
    )

    status = update_status_note(
        actor=head,
        referral_id=item.pk,
        status_note="For follow-up",
        context=context(head),
    )
    assert status.status_note == "For follow-up"

    action_types = [
        "CALL_PARENT_GUARDIAN",
        "SEND_PARENT_NOTIFICATION_LETTER",
        "SEND_CALL_SLIP_INTERVIEW_PERMIT",
    ]
    for index, action_type in enumerate(action_types):
        action = record_action(
            actor=head,
            referral_id=item.pk,
            action_type=action_type,
            occurred_at=received + timedelta(minutes=index + 1),
            remarks=f"Source remarks {index}",
            context=context(head),
            now=now,
        )
        assert action.action_type == action_type

    with pytest.raises(ReferralActionConflict):
        record_action(
            actor=head,
            referral_id=item.pk,
            action_type="CALL_PARENT_GUARDIAN",
            occurred_at=received + timedelta(minutes=10),
            remarks="Duplicate",
            context=context(head),
            now=now,
        )

    item.refresh_from_db()
    assert (
        item.reference_code,
        item.student_id,
        item.reason,
        item.referrer_name,
        item.referred_on,
        item.received_at,
        item.form_revision_id,
    ) == identity
    assert ReferralAction.objects.filter(referral=item).count() == 3
    assert Appointment.objects.count() == 0
    assert RoutineInterview.objects.count() == 0
    assert CounselingEncounter.objects.count() == 0


@pytest.mark.django_db
def test_action_cannot_predate_known_gco_receipt():
    sync_policy()
    head = make_head()
    student = make_user("student@example.edu", "STUDENT")
    now = timezone.now()
    received = now - timedelta(hours=2)
    item = create_for(
        head,
        student,
        key="receipt-action",
        fingerprint="a" * 64,
        now=now,
        received_at=received,
    )
    with pytest.raises(InvalidReferralInput, match="earlier than received_at"):
        record_action(
            actor=head,
            referral_id=item.pk,
            action_type="CALL_PARENT_GUARDIAN",
            occurred_at=received - timedelta(minutes=1),
            remarks="Impossible chronology",
            context=context(head),
            now=now,
        )


@pytest.mark.django_db
def test_active_unsupported_form_revision_blocks_new_referrals_and_history_keeps_snapshot():
    sync_policy()
    head = make_head()
    student = make_user("student@example.edu", "STUDENT")
    first = create_for(head, student, key="first-form", fingerprint="a" * 64)
    first_revision_id = first.form_revision_id

    family = FormFamily.objects.get(key="referral_slip")
    FormRevision.objects.filter(family=family, status="ACTIVE").update(status="INACTIVE")
    unsupported = FormRevision.objects.create(
        family=family,
        official_code="CNSC-OP-GTA-01F9",
        official_revision="future-unsupported",
        internal_schema_version=2,
        status="ACTIVE",
    )
    with pytest.raises(ReferralConfigurationConflict, match="not supported"):
        create_for(head, student, key="unsupported", fingerprint="b" * 64)

    unsupported.status = "INACTIVE"
    unsupported.save(update_fields=["status", "updated_at"])
    replacement = FormRevision.objects.create(
        family=family,
        official_code="CNSC-OP-GTA-01F9",
        official_revision="2",
        internal_schema_version=1,
        status="ACTIVE",
    )
    second = create_for(head, student, key="second-form", fingerprint="c" * 64)
    first.refresh_from_db()
    assert first.form_revision_id == first_revision_id
    assert second.form_revision_id == replacement.pk


@pytest.mark.django_db
def test_referral_audit_metadata_excludes_sensitive_source_text():
    sync_policy()
    head = make_head()
    student = make_user("student@example.edu", "STUDENT")
    now = timezone.now()
    received = now - timedelta(hours=2)
    item = create_for(
        head,
        student,
        key="audit",
        fingerprint="a" * 64,
        now=now,
        received_at=received,
        reason="SENSITIVE-REASON-MARKER",
        referrer_name="SENSITIVE-REFERRER-MARKER",
    )
    update_status_note(
        actor=head,
        referral_id=item.pk,
        status_note="SENSITIVE-STATUS-MARKER",
        context=context(head),
    )
    record_action(
        actor=head,
        referral_id=item.pk,
        action_type="CALL_PARENT_GUARDIAN",
        occurred_at=received + timedelta(minutes=1),
        remarks="SENSITIVE-REMARKS-MARKER",
        context=context(head),
        now=now,
    )

    serialized = json.dumps(
        list(
            AuditEvent.objects.filter(action__startswith="referral.").values_list(
                "metadata", flat=True
            )
        )
    )
    for marker in (
        "SENSITIVE-REASON-MARKER",
        "SENSITIVE-REFERRER-MARKER",
        "SENSITIVE-STATUS-MARKER",
        "SENSITIVE-REMARKS-MARKER",
        item.student_name_snapshot,
        item.course_year_block_snapshot,
    ):
        assert marker not in serialized


@pytest.mark.django_db
def test_referral_capabilities_and_api_deny_student_it_admin_and_dpo():
    sync_policy()
    head = make_head()
    student = make_user("student@example.edu", "STUDENT")
    admin = make_user("admin@example.edu", "IT_ADMIN")
    dpo = make_user("dpo@example.edu", "IT_ADMIN")
    UserDesignation.objects.create(
        user=dpo,
        designation=Designation.objects.get(code="DPO"),
    )

    assert head.has_capability("referrals.view")
    assert head.has_capability("referrals.manage")
    assert not student.has_capability("referrals.view")
    assert not admin.has_capability("referrals.view")
    assert not dpo.has_capability("referrals.view")

    for user in (student, admin, dpo):
        client = auth_client(user)
        response = client.get("/api/v1/referrals")
        assert response.status_code == 403


@pytest.mark.django_db
def test_create_api_preserves_received_at_and_rejects_naive_received_at():
    sync_policy()
    head = make_head()
    student = make_user("student@example.edu", "STUDENT")
    client = auth_client(head)
    headers = csrf(client)
    now = timezone.now()
    received = now - timedelta(days=1)
    payload = {
        "student_id": str(student.pk),
        "course_year_block": "BSIS 4A",
        "reason": "Paper referral encoded later",
        "referrer_name": "Professor Example",
        "referred_on": (now - timedelta(days=2)).date().isoformat(),
        "received_at": received.isoformat(),
    }
    created = client.post(
        "/api/v1/referrals",
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="api-received",
        **headers,
    )
    assert created.status_code == 201
    returned_received = datetime.fromisoformat(created.json()["received_at"])
    assert abs(returned_received - received) < timedelta(milliseconds=1)

    payload["received_at"] = received.replace(tzinfo=None).isoformat()
    invalid = client.post(
        "/api/v1/referrals",
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="api-naive",
        **headers,
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "invalid_referral_request"


@pytest.mark.django_db(transaction=True)
def test_concurrent_head_creations_allocate_unique_referral_references():
    sync_policy()
    ensure_referral_form_revision()
    head_a = make_head("head.a@example.edu")
    head_b = make_head("head.b@example.edu")
    student_a = make_user("student.a@example.edu", "STUDENT")
    student_b = make_user("student.b@example.edu", "STUDENT")
    now = timezone.now()

    def worker(actor_id, student_id, key, fingerprint):
        close_old_connections()
        try:
            actor = User.objects.select_related("role").get(pk=actor_id)
            student = User.objects.get(pk=student_id)
            item = create_for(
                actor,
                student,
                key=key,
                fingerprint=fingerprint,
                now=now,
            )
            return item.reference_code
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        refs = list(
            pool.map(
                lambda args: worker(*args),
                [
                    (head_a.pk, student_a.pk, "concurrent-a", "a" * 64),
                    (head_b.pk, student_b.pk, "concurrent-b", "b" * 64),
                ],
            )
        )

    assert set(refs) == {f"REF-{now.year:04d}-000001", f"REF-{now.year:04d}-000002"}
    assert len(set(refs)) == 2
