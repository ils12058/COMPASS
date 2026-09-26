from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, time, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import close_old_connections, connection, transaction
from django.test import Client, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from compass.accounts.models import (
    Designation,
    Role,
    User,
    UserDesignation,
)
from compass.appointments import services as appointment_services
from compass.appointments.models import Appointment
from compass.appointments.services import (
    AppointmentLifecycleConflict,
    AppointmentNotFound,
    AppointmentNotSchedulable,
    AppointmentTimeConflict,
    list_bookable_slots,
    list_reassignment_candidates,
    list_reschedule_slots,
    reschedule_appointment,
)
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.authentication.sessions import create_auth_session
from compass.availability.services import (
    create_office_exception,
    create_provider_exception,
    replace_office_weekly,
    replace_provider_weekly,
)
from compass.call_slips.services import (
    CallSlipDocumentUnavailable,
    build_call_slip_render_context,
    create_call_slip,
)
from compass.call_slips.services import (
    list_eligible_students as list_call_slip_students,
)
from compass.documents.rendering import render_document_html
from compass.organization.models import (
    Campus,
    College,
    CounselorResponsibility,
    StaffSupervision,
    StudentAffiliation,
)
from compass.publications import PublicationAudience
from compass.referrals.services import (
    ReferralDocumentUnavailable,
    build_referral_render_context,
    create_referral,
    record_action,
    void_referral,
)
from compass.referrals.services import (
    list_eligible_students as list_referral_students,
)
from compass.resources.models import ResourceKind
from compass.resources.services import (
    ResourceConflict,
    archive_resource,
    attach_resource_file,
    create_managed_resource_download,
    create_resource,
    publish_resource,
    remove_draft_resource_file,
    update_resource,
)
from compass.service_catalog.services import create_service, set_service_active

ZONE = ZoneInfo("Asia/Manila")


class FakeStorage:
    def __init__(self, *, fail_delete: bool = False, fail_url: bool = False) -> None:
        self.saved: dict[str, bytes] = {}
        self.deleted: list[str] = []
        self.private_url_calls: list[tuple[str, int]] = []
        self.fail_delete = fail_delete
        self.fail_url = fail_url

    def save(self, name: str, content) -> str:
        self.saved[name] = content.read()
        return name

    def delete(self, name: str) -> None:
        self.deleted.append(name)
        if self.fail_delete:
            raise RuntimeError("synthetic cleanup failure")
        self.saved.pop(name, None)

    def private_url(self, name: str, *, expires_seconds: int) -> str:
        if self.fail_url:
            raise RuntimeError("synthetic signing failure")
        self.private_url_calls.append((name, expires_seconds))
        return f"https://private.example/{name}?signature=synthetic"


def sync_policy() -> None:
    call_command("sync_identity_policy", verbosity=0)


def context(actor: User) -> AuditContext:
    return AuditContext.user(actor)


def make_user(
    email: str,
    role: str,
    *,
    active: bool = True,
    institutional_id: str | None = None,
) -> User:
    return User.objects.create_user(
        email=email,
        password="a-test-password",
        role=Role.objects.get(code=role),
        first_name=email.split("@")[0].replace(".", " ").title(),
        middle_name="",
        last_name="User",
        is_active=active,
        institutional_id=institutional_id,
    )


def make_head(email: str = "ergonomics-head@example.edu") -> User:
    user = make_user(email, "COUNSELOR")
    UserDesignation.objects.create(
        user=user,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )
    return user


def auth_client(user: User) -> Client:
    issued = create_auth_session(user, now=timezone.now())
    client = Client()
    client.cookies["compass_session"] = issued.token
    return client


def make_service(actor: User, *, duration: int = 60, policy: str = "OPTIONAL"):
    service = create_service(
        code=f"ERGONOMICS_{uuid4().hex[:8].upper()}",
        name="Ergonomics Service",
        appointment_policy=policy,
        default_duration_minutes=duration,
        cancellation_cutoff_minutes=30,
        delivery_modes=["IN_PERSON"],
        provider_roles=["COUNSELOR"],
        context=context(actor),
    )
    return set_service_active(
        service_id=service.pk,
        is_active=True,
        context=context(actor),
    )


def weekly(start: time = time(8), end: time = time(12)) -> dict[str, object]:
    return {
        "weekday": "MONDAY",
        "start_time": start,
        "end_time": end,
        "mode_scope": "ALL",
    }


def next_monday(*, days: int = 7) -> datetime:
    target = timezone.now().astimezone(ZONE).date() + timedelta(days=days)
    while target.weekday() != 0:
        target += timedelta(days=1)
    return datetime.combine(target, time(8), tzinfo=ZONE)


def configure(provider: User, actor: User, *, start: time = time(8), end: time = time(12)):
    replace_office_weekly(
        windows=[weekly(start, end)],
        context=context(actor),
    )
    replace_provider_weekly(
        provider_id=provider.pk,
        windows=[weekly(start, end)],
        context=context(actor),
    )


def raw_appointment(
    *,
    reference: str,
    student: User,
    provider: User,
    service,
    starts_at: datetime,
    status: str = "SCHEDULED",
) -> Appointment:
    kwargs: dict[str, object] = {}
    marker = starts_at - timedelta(minutes=1)
    if status == "CANCELLED":
        kwargs["cancelled_at"] = marker
        kwargs["cancelled_by"] = student
    elif status == "COMPLETED":
        kwargs["completed_at"] = marker
        kwargs["completed_by"] = provider
    elif status == "NO_SHOW":
        kwargs["no_show_at"] = marker
        kwargs["no_show_by"] = provider
    return Appointment.objects.create(
        reference_code=reference,
        student=student,
        provider=provider,
        service=service,
        delivery_mode="IN_PERSON",
        starts_at=starts_at,
        ends_at=starts_at + timedelta(hours=1),
        status=status,
        cancellation_cutoff_minutes=30,
        created_by=student,
        **kwargs,
    )


def make_scope():
    campus = Campus.objects.create(code=f"C{uuid4().hex[:5]}", name="Main Campus")
    college_a = College.objects.create(
        campus=campus,
        code=f"A{uuid4().hex[:5]}",
        name="College A",
    )
    college_b = College.objects.create(
        campus=campus,
        code=f"B{uuid4().hex[:5]}",
        name="College B",
    )
    counselor_a = make_user(f"counselor-a-{uuid4().hex[:5]}@example.edu", "COUNSELOR")
    counselor_b = make_user(f"counselor-b-{uuid4().hex[:5]}@example.edu", "COUNSELOR")
    CounselorResponsibility.objects.create(college=college_a, counselor=counselor_a)
    CounselorResponsibility.objects.create(college=college_b, counselor=counselor_b)
    gss = make_user(f"gss-{uuid4().hex[:5]}@example.edu", "GUIDANCE_SERVICES_STAFF")
    StaffSupervision.objects.create(staff=gss, supervisor=counselor_a)
    student_a = make_user(
        f"student-a-{uuid4().hex[:5]}@example.edu",
        "STUDENT",
        institutional_id=f"2026-A-{uuid4().hex[:4]}",
    )
    student_b = make_user(
        f"student-b-{uuid4().hex[:5]}@example.edu",
        "STUDENT",
        institutional_id=f"2026-B-{uuid4().hex[:4]}",
    )
    StudentAffiliation.objects.create(student=student_a, college=college_a)
    StudentAffiliation.objects.create(student=student_b, college=college_b)
    return counselor_a, counselor_b, gss, student_a, student_b


@pytest.mark.django_db
def test_managed_resource_download_and_draft_removal_are_lifecycle_safe():
    sync_policy()
    counselor = make_user("resource-final@example.edu", "COUNSELOR")
    storage = FakeStorage()
    item = create_resource(
        actor=counselor,
        title="Managed PDF",
        body_markdown="Managed file",
        category="GENERAL",
        kind=ResourceKind.FILE,
        audience=PublicationAudience.ALL_AUTHENTICATED,
        external_url=None,
        display_order=0,
        context=context(counselor),
    )
    item = attach_resource_file(
        actor=counselor,
        resource_id=item.pk,
        uploaded_file=SimpleUploadedFile(
            "managed.pdf",
            b"%PDF-1.7\nsynthetic",
            content_type="application/pdf",
        ),
        context=context(counselor),
        storage=storage,
    )
    old_key = item.storage_key

    draft_download = create_managed_resource_download(
        resource_id=item.pk,
        storage=storage,
    )
    assert draft_download.url.startswith("https://private.example/")

    detached = remove_draft_resource_file(
        actor=counselor,
        resource_id=item.pk,
        context=context(counselor),
        storage=storage,
    )
    assert detached.storage_key == ""
    assert detached.original_filename == ""
    assert detached.content_type == ""
    assert detached.size_bytes == 0
    assert old_key in storage.deleted
    assert (
        AuditEvent.objects.filter(
            action="resource.file_removed",
            target_id=str(item.pk),
        ).count()
        == 1
    )

    retry = remove_draft_resource_file(
        actor=counselor,
        resource_id=item.pk,
        context=context(counselor),
        storage=storage,
    )
    assert retry.pk == item.pk
    assert (
        AuditEvent.objects.filter(
            action="resource.file_removed",
            target_id=str(item.pk),
        ).count()
        == 1
    )

    converted = update_resource(
        actor=counselor,
        resource_id=item.pk,
        values={
            "kind": "ARTICLE",
            "body_markdown": "Converted after detaching the PDF.",
        },
        context=context(counselor),
    )
    assert converted.kind == "ARTICLE"

    with pytest.raises(ResourceConflict):
        create_managed_resource_download(resource_id=converted.pk, storage=storage)


@pytest.mark.django_db
def test_managed_resource_download_includes_published_and_archived_but_removal_does_not():
    sync_policy()
    counselor = make_user("resource-history@example.edu", "COUNSELOR")
    storage = FakeStorage()
    item = create_resource(
        actor=counselor,
        title="Historical PDF",
        body_markdown="Historical file",
        category="GENERAL",
        kind=ResourceKind.FILE,
        audience=PublicationAudience.ALL_AUTHENTICATED,
        external_url=None,
        display_order=0,
        context=context(counselor),
    )
    item = attach_resource_file(
        actor=counselor,
        resource_id=item.pk,
        uploaded_file=SimpleUploadedFile(
            "history.pdf",
            b"%PDF-1.7\nhistory",
            content_type="application/pdf",
        ),
        context=context(counselor),
        storage=storage,
    )
    item = publish_resource(
        actor=counselor,
        resource_id=item.pk,
        context=context(counselor),
    )
    assert create_managed_resource_download(
        resource_id=item.pk,
        storage=storage,
    ).url
    with pytest.raises(ResourceConflict):
        remove_draft_resource_file(
            actor=counselor,
            resource_id=item.pk,
            context=context(counselor),
            storage=storage,
        )

    item = archive_resource(
        actor=counselor,
        resource_id=item.pk,
        context=context(counselor),
    )
    assert create_managed_resource_download(
        resource_id=item.pk,
        storage=storage,
    ).url
    with pytest.raises(ResourceConflict):
        remove_draft_resource_file(
            actor=counselor,
            resource_id=item.pk,
            context=context(counselor),
            storage=storage,
        )


@pytest.mark.django_db
def test_resource_removal_stays_detached_when_object_cleanup_fails():
    sync_policy()
    counselor = make_user("resource-cleanup@example.edu", "COUNSELOR")
    storage = FakeStorage(fail_delete=True)
    item = create_resource(
        actor=counselor,
        title="Cleanup PDF",
        body_markdown="Cleanup",
        category="GENERAL",
        kind=ResourceKind.FILE,
        audience=PublicationAudience.ALL_AUTHENTICATED,
        external_url=None,
        display_order=0,
        context=context(counselor),
    )
    item = attach_resource_file(
        actor=counselor,
        resource_id=item.pk,
        uploaded_file=SimpleUploadedFile(
            "cleanup.pdf",
            b"%PDF-1.7\ncleanup",
            content_type="application/pdf",
        ),
        context=context(counselor),
        storage=storage,
    )
    detached = remove_draft_resource_file(
        actor=counselor,
        resource_id=item.pk,
        context=context(counselor),
        storage=storage,
    )
    assert detached.storage_key == ""
    assert storage.deleted == [item.storage_key]


@pytest.mark.django_db
@override_settings(TIME_ZONE="Asia/Manila")
def test_booking_slots_use_service_cadence_conflicts_statuses_and_boundaries():
    sync_policy()
    admin = make_user("slots-admin@example.edu", "IT_ADMIN")
    student = make_user("slots-student@example.edu", "STUDENT")
    other_student = make_user("slots-other-student@example.edu", "STUDENT")
    provider = make_user("slots-provider@example.edu", "COUNSELOR")
    other_provider = make_user("slots-other-provider@example.edu", "COUNSELOR")
    service = make_service(admin, duration=60)
    configure(provider, admin)
    target = next_monday()
    now = target - timedelta(hours=1)

    with CaptureQueriesContext(connection) as queries:
        initial = list_bookable_slots(
            student=student,
            service_id=service.pk,
            provider_id=provider.pk,
            delivery_mode="IN_PERSON",
            target_date=target.date(),
            now=now,
        )
    reservation_queries = [
        query for query in queries if 'FROM "appointments_appointment"' in query["sql"]
    ]
    assert len(reservation_queries) == 1
    assert [row.starts_at.hour for row in initial.items] == [8, 9, 10, 11]

    raw_appointment(
        reference="APT-2099-SLOT01",
        student=other_student,
        provider=provider,
        service=service,
        starts_at=target + timedelta(hours=1),
    )
    raw_appointment(
        reference="APT-2099-SLOT02",
        student=student,
        provider=other_provider,
        service=service,
        starts_at=target + timedelta(hours=2),
    )
    raw_appointment(
        reference="APT-2099-CANCEL",
        student=other_student,
        provider=provider,
        service=service,
        starts_at=target,
        status="CANCELLED",
    )
    raw_appointment(
        reference="APT-2099-NOSHOW",
        student=other_student,
        provider=provider,
        service=service,
        starts_at=target + timedelta(hours=3),
        status="NO_SHOW",
    )
    raw_appointment(
        reference="APT-2099-ADJ01",
        student=other_student,
        provider=provider,
        service=service,
        starts_at=target - timedelta(hours=1),
    )
    raw_appointment(
        reference="APT-2099-ADJ02",
        student=other_student,
        provider=provider,
        service=service,
        starts_at=target + timedelta(hours=4),
    )

    filtered = list_bookable_slots(
        student=student,
        service_id=service.pk,
        provider_id=provider.pk,
        delivery_mode="IN_PERSON",
        target_date=target.date(),
        now=now,
    )
    assert [row.starts_at.hour for row in filtered.items] == [8, 11]

    after_eight = list_bookable_slots(
        student=student,
        service_id=service.pk,
        provider_id=provider.pk,
        delivery_mode="IN_PERSON",
        target_date=target.date(),
        now=target,
    )
    assert [row.starts_at.hour for row in after_eight.items] == [11]


@pytest.mark.django_db(transaction=True)
@override_settings(TIME_ZONE="Asia/Manila")
def test_reschedule_rechecks_overlap_after_the_shared_participant_lock(monkeypatch):
    sync_policy()
    admin = make_user("reschedule-race-admin@example.edu", "IT_ADMIN")
    student_a = make_user("reschedule-race-a@example.edu", "STUDENT")
    student_b = make_user("reschedule-race-b@example.edu", "STUDENT")
    provider = make_user("reschedule-race-provider@example.edu", "COUNSELOR")
    service = make_service(admin)
    configure(provider, admin)
    start = next_monday()
    desired = start + timedelta(hours=2)
    now = start - timedelta(days=1)
    first = raw_appointment(
        reference="APT-2099-RACE01",
        student=student_a,
        provider=provider,
        service=service,
        starts_at=start,
    )
    second = raw_appointment(
        reference="APT-2099-RACE02",
        student=student_b,
        provider=provider,
        service=service,
        starts_at=start + timedelta(hours=3),
    )

    lock_reached = threading.Event()
    original_lock_users = appointment_services._lock_users

    def observed_lock_users(*user_ids):
        if threading.current_thread() is not threading.main_thread():
            lock_reached.set()
        return original_lock_users(*user_ids)

    monkeypatch.setattr(appointment_services, "_lock_users", observed_lock_users)

    def reschedule_first():
        close_old_connections()
        try:
            try:
                reschedule_appointment(
                    appointment_id=first.pk,
                    actor=student_a,
                    starts_at=desired,
                    reason="",
                    administrative=False,
                    context=context(student_a),
                    now=now,
                )
            except AppointmentTimeConflict:
                return "conflict"
            return "rescheduled"
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=1) as executor:
        with transaction.atomic():
            User.objects.select_for_update().get(pk=provider.pk)
            future = executor.submit(reschedule_first)
            assert lock_reached.wait(timeout=5)
            assert not future.done()
            reschedule_appointment(
                appointment_id=second.pk,
                actor=student_b,
                starts_at=desired,
                reason="",
                administrative=False,
                context=context(student_b),
                now=now,
            )
        assert future.result(timeout=10) == "conflict"

    first.refresh_from_db()
    second.refresh_from_db()
    assert first.starts_at == start
    assert second.starts_at == desired


@pytest.mark.django_db
@override_settings(TIME_ZONE="Asia/Manila")
def test_booking_slots_respect_base_exceptions_and_duration_boundaries():
    sync_policy()
    admin = make_user("slot-exception-admin@example.edu", "IT_ADMIN")
    student = make_user("slot-exception-student@example.edu", "STUDENT")
    provider = make_user("slot-exception-provider@example.edu", "COUNSELOR")
    service = make_service(admin, duration=60)
    configure(provider, admin)
    target = next_monday()
    now = target - timedelta(hours=1)

    create_office_exception(
        starts_at=target,
        ends_at=target + timedelta(hours=1),
        mode_scope="ALL",
        reason="Office opening delay",
        context=context(admin),
    )
    create_provider_exception(
        provider_id=provider.pk,
        starts_at=target + timedelta(hours=2),
        ends_at=target + timedelta(hours=3),
        mode_scope="ALL",
        reason="Provider exception",
        context=context(admin),
    )
    rows = list_bookable_slots(
        student=student,
        service_id=service.pk,
        provider_id=provider.pk,
        delivery_mode="IN_PERSON",
        target_date=target.date(),
        now=now,
    )
    assert [row.starts_at.hour for row in rows.items] == [9, 11]

    boundary_target = target + timedelta(days=7)
    boundary_now = boundary_target - timedelta(hours=1)
    configure(provider, admin, start=time(8), end=time(8, 30))
    empty = list_bookable_slots(
        student=student,
        service_id=service.pk,
        provider_id=provider.pk,
        delivery_mode="IN_PERSON",
        target_date=boundary_target.date(),
        now=boundary_now,
    )
    assert empty.items == ()

    configure(provider, admin, start=time(8), end=time(9))
    exact = list_bookable_slots(
        student=student,
        service_id=service.pk,
        provider_id=provider.pk,
        delivery_mode="IN_PERSON",
        target_date=boundary_target.date(),
        now=boundary_now,
    )
    assert len(exact.items) == 1


@pytest.mark.django_db
@override_settings(TIME_ZONE="Asia/Manila")
def test_reschedule_slots_exclude_self_preserve_snapshot_duration_and_apply_student_cutoff():
    sync_policy()
    admin = make_user("reschedule-admin@example.edu", "IT_ADMIN")
    student = make_user("reschedule-student@example.edu", "STUDENT")
    provider = make_user("reschedule-provider@example.edu", "COUNSELOR")
    service = make_service(admin, duration=60)
    configure(provider, admin)
    target = next_monday()
    item = raw_appointment(
        reference="APT-2099-RESLOT",
        student=student,
        provider=provider,
        service=service,
        starts_at=target + timedelta(hours=1),
    )
    service.default_duration_minutes = 30
    service.save(update_fields=["default_duration_minutes", "updated_at"])

    before_cutoff = target
    own = list_reschedule_slots(
        appointment_id=item.pk,
        actor=student,
        target_date=target.date(),
        administrative=False,
        now=before_cutoff,
    )
    assert own.duration_minutes == 60
    assert 9 in [row.starts_at.hour for row in own.items]

    after_cutoff = item.starts_at - timedelta(minutes=15)
    with pytest.raises(AppointmentLifecycleConflict, match="cutoff"):
        list_reschedule_slots(
            appointment_id=item.pk,
            actor=student,
            target_date=target.date(),
            administrative=False,
            now=after_cutoff,
        )

    managed = list_reschedule_slots(
        appointment_id=item.pk,
        actor=provider,
        target_date=target.date(),
        administrative=True,
        now=after_cutoff,
    )
    assert managed.duration_minutes == 60


@pytest.mark.django_db
@override_settings(TIME_ZONE="Asia/Manila")
def test_reassignment_candidates_are_scoped_to_appointment_and_actual_availability():
    sync_policy()
    admin = make_user("reassign-admin@example.edu", "IT_ADMIN")
    student = make_user("reassign-student@example.edu", "STUDENT")
    current = make_user("reassign-current@example.edu", "COUNSELOR")
    available = make_user("reassign-available@example.edu", "COUNSELOR")
    overlapping = make_user("reassign-overlap@example.edu", "COUNSELOR")
    unavailable = make_user("reassign-unavailable@example.edu", "COUNSELOR")
    make_user("reassign-inactive@example.edu", "COUNSELOR", active=False)
    service = make_service(admin, duration=60)
    for provider in (current, available, overlapping):
        configure(provider, admin)
    target = next_monday()
    item = raw_appointment(
        reference="APT-2099-REASSIGN",
        student=student,
        provider=current,
        service=service,
        starts_at=target + timedelta(hours=1),
    )
    other_student = make_user("reassign-other-student@example.edu", "STUDENT")
    raw_appointment(
        reference="APT-2099-OVERLAP",
        student=other_student,
        provider=overlapping,
        service=service,
        starts_at=item.starts_at,
    )

    rows = list_reassignment_candidates(
        appointment_id=item.pk,
        actor=current,
        now=target,
    )
    ids = {row.user.pk for row in rows}
    assert available.pk in ids
    assert current.pk not in ids
    assert overlapping.pk not in ids
    assert unavailable.pk not in ids

    outsider = make_user("reassign-outsider@example.edu", "GUIDANCE_SERVICES_STAFF")
    with pytest.raises(AppointmentNotFound):
        list_reassignment_candidates(
            appointment_id=item.pk,
            actor=outsider,
            now=target,
        )


@pytest.mark.django_db
def test_domain_student_selectors_share_scope_search_pagination_and_minimal_projection():
    sync_policy()
    counselor_a, _, gss, student_a, student_b = make_scope()
    head = make_head("selector-head@example.edu")
    unaffiliated = make_user(
        "selector-unaffiliated@example.edu",
        "STUDENT",
        institutional_id="2026-UNAFFILIATED",
    )
    inactive = make_user(
        "selector-inactive@example.edu",
        "STUDENT",
        active=False,
        institutional_id="2026-INACTIVE",
    )
    make_user("selector-admin@example.edu", "IT_ADMIN", institutional_id="EMP-ADMIN")

    for listing in (list_referral_students, list_call_slip_students):
        counselor_page = listing(actor=counselor_a)
        assert [row.id for row in counselor_page.items] == [student_a.pk]
        gss_page = listing(actor=gss)
        assert [row.id for row in gss_page.items] == [student_a.pk]
        head_ids = {row.id for row in listing(actor=head).items}
        assert {student_a.pk, student_b.pk, unaffiliated.pk} <= head_ids
        assert inactive.pk not in head_ids

        searched = listing(actor=head, search=student_b.institutional_id)
        assert [row.id for row in searched.items] == [student_b.pk]
        paged = listing(actor=head, page=1, page_size=1)
        assert len(paged.items) == 1
        assert paged.has_next

    response = auth_client(counselor_a).get("/api/v1/referrals/students")
    assert response.status_code == 200
    assert {row["id"] for row in response.json()["items"]} == {str(student_a.pk)}
    assert "email" not in response.json()["items"][0]

    response = auth_client(gss).get("/api/v1/call-slips/students")
    assert response.status_code == 200
    assert {row["id"] for row in response.json()["items"]} == {str(student_a.pk)}
    assert "email" not in response.json()["items"][0]


def create_referral_for(actor: User, student: User):
    now = timezone.now()
    return create_referral(
        actor=actor,
        student_id=student.pk,
        course_year_block="BSIS 4A",
        reason="Persisted referral reason",
        referrer_name="Prof. Persisted Referrer",
        referred_on=(now - timedelta(days=2)).date(),
        received_at=now - timedelta(days=1),
        idempotency_key=f"ref-{uuid4()}",
        request_fingerprint="a" * 64,
        context=context(actor),
        now=now,
    )


def create_call_slip_for(actor: User, student: User):
    return create_call_slip(
        actor=actor,
        student_id=student.pk,
        course_year="BSIS 4",
        destination_type="GUIDANCE_OFFICE",
        other_destination="",
        report_at=timezone.now() + timedelta(days=1),
        referral_id=None,
        notify_student=False,
        idempotency_key=f"call-{uuid4()}",
        request_fingerprint="b" * 64,
        context=context(actor),
    )


@pytest.mark.django_db
def test_referral_pdf_uses_bound_form_metadata_actions_void_state_and_release_audit(
    monkeypatch,
):
    sync_policy()
    head = make_head("referral-pdf-head@example.edu")
    student = make_user("referral-pdf-student@example.edu", "STUDENT")
    item = create_referral_for(head, student)
    record_action(
        actor=head,
        referral_id=item.pk,
        action_type="CALL_PARENT_GUARDIAN",
        occurred_at=timezone.now(),
        remarks="Parent contacted",
        context=context(head),
    )
    item = void_referral(
        actor=head,
        referral_id=item.pk,
        reason="Duplicate source form",
        context=context(head),
    )

    render_context = build_referral_render_context(item)
    assert render_context["controlled_form"]["official_code"] == (item.form_revision.official_code)
    assert render_context["controlled_form"]["official_revision"] == (
        item.form_revision.official_revision
    )
    assert render_context["referral"]["is_voided"] is True
    assert any(
        row["recorded"] and row["remarks"] == "Parent contacted"
        for row in render_context["referral"]["actions"]
    )
    html, spec = render_document_html(
        "referral_slip",
        item.form_revision.internal_schema_version,
        context=render_context,
    )
    assert spec.key == "referral_slip"
    assert item.reference_code in html
    assert "VOIDED" in html

    monkeypatch.setattr(
        "compass.referrals.api.render_referral_pdf",
        lambda _item: b"%PDF synthetic referral",
    )
    response = auth_client(head).get(f"/api/v1/referrals/{item.pk}/pdf")
    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert "attachment;" in response["Content-Disposition"]
    event = AuditEvent.objects.get(
        action="document.download_released",
        target_type="referrals.referral",
        target_id=str(item.pk),
    )
    assert event.metadata == {
        "document_type": "referral_slip",
        "access_mode": "GCO",
        "form_revision_id": str(item.form_revision_id),
        "official_code": item.form_revision.official_code,
        "official_revision": item.form_revision.official_revision,
    }


@pytest.mark.django_db
def test_referral_pdf_fails_closed_for_render_and_release_audit(monkeypatch):
    sync_policy()
    head = make_head("referral-fail-head@example.edu")
    student = make_user("referral-fail-student@example.edu", "STUDENT")
    item = create_referral_for(head, student)
    client = auth_client(head)

    monkeypatch.setattr(
        "compass.referrals.api.render_referral_pdf",
        lambda _item: (_ for _ in ()).throw(
            ReferralDocumentUnavailable("synthetic referral render failure")
        ),
    )
    failed = client.get(f"/api/v1/referrals/{item.pk}/pdf")
    assert failed.status_code == 503
    assert failed.json()["error"]["code"] == "referral_document_unavailable"

    monkeypatch.setattr(
        "compass.referrals.api.render_referral_pdf",
        lambda _item: b"%PDF must not escape",
    )
    monkeypatch.setattr(
        "compass.privacy_governance.releases.record_event",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("audit unavailable")),
    )
    blocked = client.get(f"/api/v1/referrals/{item.pk}/pdf")
    assert blocked.status_code == 503
    assert blocked.json()["error"]["code"] == "release_audit_unavailable"
    assert b"must not escape" not in blocked.content


@pytest.mark.django_db
def test_call_slip_pdf_preserves_self_privacy_and_records_gco_and_self_releases(
    monkeypatch,
):
    sync_policy()
    head = make_head("call-pdf-head@example.edu")
    student = make_user("call-pdf-student@example.edu", "STUDENT")
    other_student = make_user("call-pdf-other@example.edu", "STUDENT")
    item = create_call_slip_for(head, student)

    item.voided_at = timezone.now()
    item.void_reason = "INTERNAL-VOID-REASON"
    self_context = build_call_slip_render_context(item, access_mode="SELF")
    gco_context = build_call_slip_render_context(item, access_mode="GCO")
    assert self_context["call_slip"]["void_reason"] == ""
    assert gco_context["call_slip"]["void_reason"] == "INTERNAL-VOID-REASON"
    item.voided_at = None
    item.void_reason = ""

    html, spec = render_document_html(
        "call_slip",
        item.form_revision.internal_schema_version,
        context=build_call_slip_render_context(item, access_mode="SELF"),
    )
    assert spec.key == "call_slip"
    assert item.student_name_snapshot in html

    monkeypatch.setattr(
        "compass.call_slips.api.render_call_slip_pdf",
        lambda _item, *, access_mode: b"%PDF synthetic call slip",
    )
    gco = auth_client(head).get(f"/api/v1/call-slips/{item.pk}/pdf")
    assert gco.status_code == 200
    assert gco["Content-Type"] == "application/pdf"

    mine = auth_client(student).get(f"/api/v1/call-slips/me/{item.pk}/pdf")
    assert mine.status_code == 200
    denied = auth_client(other_student).get(f"/api/v1/call-slips/me/{item.pk}/pdf")
    assert denied.status_code == 404

    events = AuditEvent.objects.filter(
        action="document.download_released",
        target_type="callslips.callslip",
        target_id=str(item.pk),
    )
    assert {event.metadata["access_mode"] for event in events} == {"GCO", "SELF"}
    for event in events:
        assert "void_reason" not in event.metadata
        assert event.metadata["form_revision_id"] == str(item.form_revision_id)


@pytest.mark.django_db
def test_call_slip_pdf_fails_closed_for_render_and_release_audit(monkeypatch):
    sync_policy()
    head = make_head("call-fail-head@example.edu")
    student = make_user("call-fail-student@example.edu", "STUDENT")
    item = create_call_slip_for(head, student)
    client = auth_client(head)

    monkeypatch.setattr(
        "compass.call_slips.api.render_call_slip_pdf",
        lambda _item, *, access_mode: (_ for _ in ()).throw(
            CallSlipDocumentUnavailable("synthetic call slip render failure")
        ),
    )
    failed = client.get(f"/api/v1/call-slips/{item.pk}/pdf")
    assert failed.status_code == 503
    assert failed.json()["error"]["code"] == "call_slip_document_unavailable"

    monkeypatch.setattr(
        "compass.call_slips.api.render_call_slip_pdf",
        lambda _item, *, access_mode: b"%PDF must not escape",
    )
    monkeypatch.setattr(
        "compass.privacy_governance.releases.record_event",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("audit unavailable")),
    )
    blocked = client.get(f"/api/v1/call-slips/{item.pk}/pdf")
    assert blocked.status_code == 503
    assert blocked.json()["error"]["code"] == "release_audit_unavailable"
    assert b"must not escape" not in blocked.content


@pytest.mark.django_db
def test_slot_discovery_rejects_non_schedulable_service():
    sync_policy()
    admin = make_user("slot-policy-admin@example.edu", "IT_ADMIN")
    student = make_user("slot-policy-student@example.edu", "STUDENT")
    provider = make_user("slot-policy-provider@example.edu", "COUNSELOR")
    service = create_service(
        code=f"NO_APPOINTMENT_{uuid4().hex[:8].upper()}",
        name="No Appointment",
        appointment_policy="NONE",
        delivery_modes=["IN_PERSON"],
        provider_roles=["COUNSELOR"],
        context=context(admin),
    )
    service = set_service_active(
        service_id=service.pk,
        is_active=True,
        context=context(admin),
    )
    configure(provider, admin)
    target = next_monday()
    with pytest.raises(AppointmentNotSchedulable):
        list_bookable_slots(
            student=student,
            service_id=service.pk,
            provider_id=provider.pk,
            delivery_mode="IN_PERSON",
            target_date=target.date(),
            now=target - timedelta(hours=1),
        )
