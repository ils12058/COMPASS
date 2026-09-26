from __future__ import annotations

import json
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.test.client import BOUNDARY, MULTIPART_CONTENT, encode_multipart
from django.utils import timezone

from compass.accounts.models import Designation, UserDesignation
from compass.appointments.models import Appointment, AppointmentChangeEvent, AppointmentStatus
from compass.appointments.services import (
    AppointmentCancellationConflict,
    AppointmentLifecycleConflict,
    cancel_appointment,
    complete_appointment,
    create_student_appointment,
    get_appointment_history,
    mark_appointment_no_show,
    reschedule_appointment,
)
from compass.audit.models import AuditEvent
from compass.availability.services import replace_provider_weekly
from compass.call_slips.models import CallSlip
from compass.call_slips.services import (
    CallSlipVoidConflict,
    create_call_slip,
    list_call_slips,
    record_interview_ended,
    void_call_slip,
)
from compass.counseling.models import CounselingEncounter
from compass.ecounseling.models import ECounselingRoom
from compass.good_moral.models import GoodMoralStatus
from compass.good_moral.services import (
    GoodMoralConflict,
    cancel_request,
    issue_request,
    render_certificate_pdf,
    update_request,
)
from compass.integrations.storage import ObjectStorage
from compass.notifications.models import Notification
from compass.organization.models import AcademicYear, CounselorResponsibility
from compass.referrals.services import (
    ReferralVoidConflict,
    record_action,
    update_status_note,
    void_referral,
)
from tests.test_appointments import (
    active_service,
    configure_availability,
    create_affiliation,
    future_local_start,
    sync_policy,
    weekly,
)
from tests.test_appointments import (
    auth_client as appointment_auth_client,
)
from tests.test_appointments import (
    context as appointment_context,
)
from tests.test_appointments import (
    csrf as appointment_csrf,
)
from tests.test_appointments import (
    make_user as make_appointment_user,
)
from tests.test_call_slips import create_referral_for
from tests.test_good_moral import (
    auth_client as good_moral_auth_client,
)
from tests.test_good_moral import (
    csrf as good_moral_csrf,
)
from tests.test_good_moral import (
    make_graduate_request,
)
from tests.test_good_moral import (
    make_user as make_good_moral_user,
)
from tests.test_notifications import (
    auth_client as notification_auth_client,
)
from tests.test_notifications import (
    make_notification,
)
from tests.test_notifications import (
    make_user as make_notification_user,
)
from tests.test_profile_photos import MemoryBackend, image_upload
from tests.test_student_support import (
    affiliate,
    make_head,
    make_inventory,
    make_org,
)
from tests.test_student_support import (
    auth_client as support_auth_client,
)
from tests.test_student_support import (
    make_user as make_support_user,
)


@pytest.mark.django_db
@override_settings(TIME_ZONE="Asia/Manila")
def test_appointment_reschedule_history_terminal_outcomes_and_safe_notifications():
    sync_policy()
    catalog_actor = make_appointment_user("final-catalog@example.edu", "IT_ADMIN")
    student = make_appointment_user("final-student@example.edu", "STUDENT")
    provider = make_appointment_user("final-provider@example.edu", "COUNSELOR")
    service = active_service(catalog_actor, duration=60, cutoff=30)
    configure_availability(catalog_actor, provider)
    create_affiliation(student, provider)
    start = future_local_start(hour=10)

    item = create_student_appointment(
        student=student,
        service_id=service.pk,
        provider_id=provider.pk,
        delivery_mode="IN_PERSON",
        starts_at=start,
        context=appointment_context(student),
        now=start - timedelta(days=1),
    )
    original = (
        item.student_id,
        item.service_id,
        item.provider_id,
        item.delivery_mode,
        item.reference_code,
        item.cancellation_cutoff_minutes,
        item.ends_at - item.starts_at,
    )

    changed = reschedule_appointment(
        appointment_id=item.pk,
        actor=student,
        starts_at=start + timedelta(hours=2),
        reason="Student scheduling correction",
        administrative=False,
        context=appointment_context(student),
        now=start - timedelta(hours=1),
    )
    assert (
        changed.student_id,
        changed.service_id,
        changed.provider_id,
        changed.delivery_mode,
        changed.reference_code,
        changed.cancellation_cutoff_minutes,
        changed.ends_at - changed.starts_at,
    ) == original
    assert changed.starts_at == start + timedelta(hours=2)

    event = AppointmentChangeEvent.objects.get(
        appointment=changed,
        event_type="RESCHEDULED",
    )
    notifications = Notification.objects.filter(
        event_code="appointment.rescheduled",
        source_type="appointment_change_event",
        source_id=event.pk,
    )
    assert {row.recipient_id for row in notifications} == {student.pk, provider.pk}
    assert "Student scheduling correction" not in json.dumps(
        list(notifications.values("title", "message"))
    )

    student_history = get_appointment_history(
        appointment_id=changed.pk,
        actor=student,
    )
    manager_history = get_appointment_history(
        appointment_id=changed.pk,
        actor=provider,
    )
    assert [row.event_type for row in student_history] == ["CREATED", "RESCHEDULED"]
    assert student_history[-1].reason == ""
    assert manager_history[-1].reason == "Student scheduling correction"

    completed = complete_appointment(
        appointment_id=changed.pk,
        actor=provider,
        context=appointment_context(provider),
        now=changed.starts_at + timedelta(minutes=1),
    )
    assert completed.status == AppointmentStatus.COMPLETED
    assert completed.completed_at is not None
    assert completed.completed_by_id == provider.pk

    with pytest.raises(AppointmentLifecycleConflict):
        reschedule_appointment(
            appointment_id=completed.pk,
            actor=student,
            starts_at=completed.starts_at + timedelta(days=7),
            reason="Cannot move terminal record",
            administrative=False,
            context=appointment_context(student),
            now=completed.starts_at - timedelta(hours=1),
        )
    with pytest.raises(AppointmentCancellationConflict):
        cancel_appointment(
            appointment_id=completed.pk,
            actor=provider,
            administrative=True,
            context=appointment_context(provider),
            now=completed.starts_at + timedelta(minutes=2),
        )


@pytest.mark.django_db
@override_settings(TIME_ZONE="Asia/Manila")
def test_admin_reschedule_reassign_step_up_and_downstream_binding_safety():
    sync_policy()
    catalog_actor = make_appointment_user("admin-catalog@example.edu", "IT_ADMIN")
    student = make_appointment_user("admin-student@example.edu", "STUDENT")
    manager = make_appointment_user("admin-manager@example.edu", "COUNSELOR")
    new_provider = make_appointment_user("admin-new-provider@example.edu", "COUNSELOR")
    service = active_service(catalog_actor)
    configure_availability(catalog_actor, manager)
    replace_provider_weekly(
        provider_id=new_provider.pk,
        windows=[weekly()],
        context=appointment_context(catalog_actor),
    )
    create_affiliation(student, manager)
    start = future_local_start(hour=10)
    item = create_student_appointment(
        student=student,
        service_id=service.pk,
        provider_id=manager.pk,
        delivery_mode="IN_PERSON",
        starts_at=start,
        context=appointment_context(student),
        now=start - timedelta(days=1),
    )

    stale = appointment_auth_client(manager)
    denied = stale.post(
        f"/api/v1/appointments/{item.pk}/reschedule",
        data=json.dumps({"starts_at": (start + timedelta(hours=2)).isoformat(), "reason": ""}),
        content_type="application/json",
        **appointment_csrf(stale),
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "recent_mfa_required"

    fresh = appointment_auth_client(manager, recent_mfa=True)
    moved = fresh.post(
        f"/api/v1/appointments/{item.pk}/reschedule",
        data=json.dumps({"starts_at": (start + timedelta(hours=2)).isoformat(), "reason": ""}),
        content_type="application/json",
        **appointment_csrf(fresh),
    )
    assert moved.status_code == 200

    reassigned = fresh.post(
        f"/api/v1/appointments/{item.pk}/reassign",
        data=json.dumps(
            {
                "provider_id": str(new_provider.pk),
                "reason": "Operational reassignment",
            }
        ),
        content_type="application/json",
        **appointment_csrf(fresh),
    )
    assert reassigned.status_code == 200
    assert reassigned.json()["provider"]["id"] == str(new_provider.pk)

    ECounselingRoom.objects.create(
        appointment=item,
        daily_room_name=f"final-room-{item.pk}",
    )
    blocked = fresh.post(
        f"/api/v1/appointments/{item.pk}/reassign",
        data=json.dumps(
            {
                "provider_id": str(manager.pk),
                "reason": "Must not rewrite bound provider context",
            }
        ),
        content_type="application/json",
        **appointment_csrf(fresh),
    )
    assert blocked.status_code == 409


@pytest.mark.django_db
def test_no_show_is_terminal_and_rejects_existing_counseling_encounter():
    sync_policy()
    catalog_actor = make_appointment_user("noshow-catalog@example.edu", "IT_ADMIN")
    student = make_appointment_user("noshow-student@example.edu", "STUDENT")
    manager = make_appointment_user("noshow-manager@example.edu", "COUNSELOR")
    service = active_service(catalog_actor)
    create_affiliation(student, manager)
    now = timezone.now()
    item = Appointment.objects.create(
        reference_code="APT-2099-800001",
        student=student,
        provider=manager,
        service=service,
        delivery_mode="IN_PERSON",
        starts_at=now - timedelta(hours=2),
        ends_at=now - timedelta(hours=1),
        created_by=student,
    )
    result = mark_appointment_no_show(
        appointment_id=item.pk,
        actor=manager,
        context=appointment_context(manager),
        now=now,
    )
    assert result.status == AppointmentStatus.NO_SHOW
    assert result.no_show_at == now
    assert (
        mark_appointment_no_show(
            appointment_id=item.pk,
            actor=manager,
            context=appointment_context(manager),
            now=now + timedelta(minutes=1),
        ).status
        == AppointmentStatus.NO_SHOW
    )

    linked = Appointment.objects.create(
        reference_code="APT-2099-800002",
        student=student,
        provider=manager,
        service=service,
        delivery_mode="IN_PERSON",
        starts_at=now - timedelta(hours=3),
        ends_at=now - timedelta(hours=2),
        created_by=student,
    )
    CounselingEncounter.objects.create(
        student=student,
        counselor=manager,
        service=service,
        appointment=linked,
        entry_mode="APPOINTMENT",
        delivery_mode="IN_PERSON",
        started_at=linked.starts_at,
        ended_at=linked.ends_at,
        created_by=manager,
    )
    with pytest.raises(AppointmentLifecycleConflict):
        mark_appointment_no_show(
            appointment_id=linked.pk,
            actor=manager,
            context=appointment_context(manager),
            now=now,
        )


@pytest.mark.django_db
def test_student_support_roster_is_scoped_current_privacy_minimized_and_filterable():
    sync_policy()
    counselor = make_support_user("roster-final-counselor@example.edu", "COUNSELOR")
    no_scope = make_support_user("roster-final-none@example.edu", "COUNSELOR")
    gss = make_support_user("roster-final-gss@example.edu", "GUIDANCE_SERVICES_STAFF")
    head = make_head("roster-final-head@example.edu")
    year = AcademicYear.objects.create(label="2099-2100", is_current=True)
    _, college, program = make_org("FINAL")
    submitted = make_support_user("alpha.roster@example.edu")
    submitted.institutional_id = "FINAL-001"
    submitted.save(update_fields=["institutional_id", "updated_at"])
    draft = make_support_user("beta.roster@example.edu")
    missing = make_support_user("gamma.roster@example.edu")
    affiliate(submitted, college)
    affiliate(draft, college)
    affiliate(missing, college)
    CounselorResponsibility.objects.create(college=college, counselor=counselor)
    make_inventory(
        student=submitted,
        year=year,
        program=program,
        suffix="final-submitted",
        pwd_status="PWD",
        four_ps_status="BENEFICIARY",
    )
    make_inventory(
        student=draft,
        year=year,
        program=program,
        suffix="final-draft",
        submitted=False,
        pwd_status="PWD",
    )

    client = support_auth_client(counselor)
    roster = client.get("/api/v1/student-support/students", {"page_size": 2})
    assert roster.status_code == 200
    assert roster.json()["page_size"] == 2
    assert roster.json()["has_next"] is True
    assert "total_count" not in roster.json()

    searched = client.get("/api/v1/student-support/students", {"search": "FINAL-001"})
    assert searched.status_code == 200
    row = searched.json()["items"][0]
    assert row["student"]["id"] == str(submitted.pk)
    assert row["inventory_status"] == "SUBMITTED"
    assert {item["code"] for item in row["indicators"]} >= {"PWD", "FOUR_PS_BENEFICIARY"}
    serialized = json.dumps(row)
    for forbidden in ("current_address", "income", "fears", "counseling_history"):
        assert forbidden not in serialized

    filtered = client.get(
        "/api/v1/student-support/students",
        {"indicator": "PWD"},
    )
    assert filtered.status_code == 200
    assert [item["student"]["id"] for item in filtered.json()["items"]] == [str(submitted.pk)]
    assert (
        support_auth_client(no_scope).get("/api/v1/student-support/students").json()["items"] == []
    )
    assert support_auth_client(gss).get("/api/v1/student-support/students").status_code == 403
    head_ids = {
        row["student"]["id"]
        for row in support_auth_client(head)
        .get(
            "/api/v1/student-support/students",
            {"page_size": 50},
        )
        .json()["items"]
    }
    assert {str(submitted.pk), str(draft.pk), str(missing.pk)} <= head_ids


@pytest.mark.django_db
def test_notification_mark_all_read_is_owner_only_idempotent_and_uses_one_timestamp():
    owner = make_notification_user("read-all-owner@example.edu")
    other = make_notification_user("read-all-other@example.edu")
    first = make_notification(owner)
    second = make_notification(owner)
    already = make_notification(owner)
    other_row = make_notification(other)
    original_read_at = timezone.now() - timedelta(days=1)
    Notification.objects.filter(pk=already.pk).update(read_at=original_read_at)

    client = notification_auth_client(owner)
    response = client.patch(
        "/api/v1/notifications/read-all",
        data="{}",
        content_type="application/json",
    )
    assert response.status_code == 200
    assert response.json() == {"updated_count": 2}

    first.refresh_from_db()
    second.refresh_from_db()
    already.refresh_from_db()
    other_row.refresh_from_db()
    assert first.read_at == second.read_at
    assert already.read_at == original_read_at
    assert other_row.read_at is None
    assert client.get("/api/v1/notifications/unread-count").json()["unread_count"] == 0
    assert client.patch(
        "/api/v1/notifications/read-all",
        data="{}",
        content_type="application/json",
    ).json() == {"updated_count": 0}


@pytest.mark.django_db
def test_profile_photo_http_set_replace_remove_uses_existing_private_photo_service():
    sync_policy()
    user = make_appointment_user("photo-http@example.edu", "STUDENT")
    client = appointment_auth_client(user)
    backend = MemoryBackend()
    storage = ObjectStorage(backend)

    raw = image_upload("PNG").read()
    payload = encode_multipart(
        BOUNDARY,
        {
            "photo": SimpleUploadedFile(
                "avatar.png",
                raw,
                content_type="image/png",
            )
        },
    )
    with patch("compass.accounts.profile_photos.ObjectStorage", return_value=storage):
        response = client.generic(
            "PUT",
            "/api/v1/me/profile/photo",
            payload,
            content_type=MULTIPART_CONTENT,
        )
        assert response.status_code == 200
        assert response.json()["profile_photo_url"].startswith("https://signed.example.test/")
        user.refresh_from_db()
        key = user.profile_photo_object_key
        assert key is not None
        assert "profile_photo_object_key" not in response.json()

        removed = client.delete("/api/v1/me/profile/photo")
        assert removed.status_code == 200
        assert removed.json()["profile_photo_url"] is None
        assert client.delete("/api/v1/me/profile/photo").status_code == 200


@pytest.mark.django_db
def test_referral_and_call_slip_void_preserve_history_and_enable_corrected_reissue():
    sync_policy()
    head = make_appointment_user("void-head@example.edu", "COUNSELOR")
    UserDesignation.objects.create(
        user=head,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )
    student = make_appointment_user("void-student@example.edu", "STUDENT")
    referral = create_referral_for(
        head,
        student,
        key="void-referral",
        fingerprint="a" * 64,
    )
    record_action(
        actor=head,
        referral_id=referral.pk,
        action_type="SEND_CALL_SLIP_INTERVIEW_PERMIT",
        occurred_at=timezone.now(),
        remarks="Permit action",
        context=appointment_context(head),
    )
    first = create_call_slip(
        actor=head,
        student_id=student.pk,
        course_year="BSIS 4",
        destination_type="GUIDANCE_OFFICE",
        other_destination="",
        report_at=timezone.now() + timedelta(days=1),
        referral_id=referral.pk,
        notify_student=True,
        idempotency_key="void-first",
        request_fingerprint="b" * 64,
        context=appointment_context(head),
    )

    with pytest.raises(ReferralVoidConflict):
        void_referral(
            actor=head,
            referral_id=referral.pk,
            reason="Wrong encoded referral",
            context=appointment_context(head),
        )

    voided = void_call_slip(
        actor=head,
        call_slip_id=first.pk,
        reason="Issued in error - internal detail",
        context=appointment_context(head),
    )
    assert voided.lifecycle_state == "VOIDED"
    assert first.pk not in {row.pk for row in list_call_slips(actor=head).items}
    assert first.pk in {row.pk for row in list_call_slips(actor=head, include_voided=True).items}
    notice = Notification.objects.get(
        recipient=student,
        event_code="call_slip.voided",
        source_id=first.pk,
    )
    assert "Issued in error" not in notice.message
    with pytest.raises(CallSlipVoidConflict):
        record_interview_ended(
            actor=head,
            call_slip_id=first.pk,
            interview_ended_at=timezone.now(),
            context=appointment_context(head),
        )

    replacement = create_call_slip(
        actor=head,
        student_id=student.pk,
        course_year="BSIS 4",
        destination_type="GUIDANCE_OFFICE",
        other_destination="",
        report_at=timezone.now() + timedelta(days=2),
        referral_id=referral.pk,
        notify_student=False,
        idempotency_key="void-replacement",
        request_fingerprint="c" * 64,
        context=appointment_context(head),
    )
    assert replacement.pk != first.pk
    assert CallSlip.objects.filter(referral=referral).count() == 2
    assert (
        CallSlip.objects.filter(
            referral=referral,
            voided_at__isnull=True,
        ).count()
        == 1
    )

    void_call_slip(
        actor=head,
        call_slip_id=replacement.pk,
        reason="Replacement also withdrawn for Referral correction",
        context=appointment_context(head),
    )
    # The replacement was a quiet historical entry, so its void stays quiet too.
    assert not Notification.objects.filter(
        event_code="call_slip.voided",
        source_id=replacement.pk,
    ).exists()
    voided_referral = void_referral(
        actor=head,
        referral_id=referral.pk,
        reason="Wrong source paper record",
        context=appointment_context(head),
    )
    assert voided_referral.voided_at is not None
    assert voided_referral.pk not in {
        row.pk
        for row in __import__(
            "compass.referrals.services",
            fromlist=["list_referrals"],
        )
        .list_referrals(actor=head)
        .items
    }
    with pytest.raises(ReferralVoidConflict):
        update_status_note(
            actor=head,
            referral_id=referral.pk,
            status_note="Must not change",
            context=appointment_context(head),
        )


@pytest.mark.django_db
def test_good_moral_requested_cancellation_is_retained_and_issued_remains_immutable():
    sync_policy()
    student = make_good_moral_user(
        "cancel-good-moral@example.edu",
        lifecycle="GRADUATED",
    )
    counselor = make_good_moral_user("cancel-good-moral-counselor@example.edu", role="COUNSELOR")
    item = make_graduate_request(student)

    client = good_moral_auth_client(student)
    cancelled = client.post(
        f"/api/v1/good-moral/me/{item.pk}/cancel",
        data=json.dumps({"reason": "Duplicate pending request"}),
        content_type="application/json",
        **good_moral_csrf(client),
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == GoodMoralStatus.CANCELLED
    item.refresh_from_db()
    assert item.cancelled_at is not None
    assert item.cancellation_reason == "Duplicate pending request"
    event = AuditEvent.objects.get(
        action="good_moral.request.cancelled",
        target_id=str(item.pk),
    )
    assert "Duplicate pending request" not in json.dumps(event.metadata)
    assert "cancellation" not in cancelled.json()
    assert "Duplicate pending request" not in cancelled.content.decode()
    operational = good_moral_auth_client(counselor).get(f"/api/v1/good-moral/requests/{item.pk}")
    assert operational.status_code == 200
    assert operational.json()["cancellation"] == {
        "cancelled_by": {"id": str(student.pk), "display_name": student.get_full_name()},
        "reason": "Duplicate pending request",
    }
    with pytest.raises(GoodMoralConflict):
        update_request(
            actor=counselor,
            request_id=item.pk,
            changes={"degree_snapshot": "Cannot edit"},
            context=appointment_context(counselor),
        )
    with pytest.raises(GoodMoralConflict):
        issue_request(
            actor=counselor,
            request_id=item.pk,
            context=appointment_context(counselor),
        )
    with pytest.raises(GoodMoralConflict):
        render_certificate_pdf(item)

    issued_item = make_graduate_request(student)
    issued = issue_request(
        actor=counselor,
        request_id=issued_item.pk,
        context=appointment_context(counselor),
    )
    assert issued.status == GoodMoralStatus.ISSUED
    with pytest.raises(GoodMoralConflict):
        cancel_request(
            actor=counselor,
            request_id=issued.pk,
            reason="Issued records stay immutable",
            self_service=False,
            context=appointment_context(counselor),
        )


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("indicator", "historical_values"),
    [
        ("PWD", {"pwd_status": "PWD"}),
        ("FOUR_PS_BENEFICIARY", {"four_ps_status": "BENEFICIARY"}),
        ("MOTHER_DECEASED", {"mother_life_status": "DECEASED"}),
    ],
)
def test_roster_indicator_filter_uses_only_the_current_submitted_inventory(
    indicator, historical_values
):
    sync_policy()
    head = make_head(f"indicator-head-{indicator.lower()}@example.edu")
    previous = AcademicYear.objects.create(label="2098-2099")
    current = AcademicYear.objects.create(label="2099-2100", is_current=True)
    _, college, program = make_org(f"IND-{indicator}")
    student = make_support_user(f"indicator-{indicator.lower()}@example.edu")
    affiliate(student, college)
    make_inventory(
        student=student,
        year=previous,
        program=program,
        suffix=f"{indicator}-previous",
        **historical_values,
    )
    make_inventory(student=student, year=current, program=program, suffix=f"{indicator}-current")

    client = support_auth_client(head)
    filtered = client.get("/api/v1/student-support/students", {"indicator": indicator})

    assert filtered.status_code == 200
    assert filtered.json()["items"] == []
