from __future__ import annotations

import json
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.test import Client
from django.utils import timezone

from compass.accounts.models import (
    Capability,
    Designation,
    Role,
    User,
    UserCapabilityOverride,
    UserDesignation,
)
from compass.appointments.access import appointment_management_access_allowed, scope_managed_appointments
from compass.appointments.models import Appointment, AppointmentChangeEvent
from compass.appointments.services import (
    AppointmentNotFound,
    appointment_actions_for,
    count_upcoming_managed_appointments,
    get_appointment_for_actor,
    get_appointment_history,
    list_managed_appointments,
    reassign_appointment,
)
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.authentication.sessions import create_auth_session
from compass.notifications.models import Notification
from compass.organization.access_scope import resolve_general_guidance_college_scope
from compass.organization.models import (
    Campus,
    College,
    CounselorResponsibility,
    StaffSupervision,
    StudentAffiliation,
)
from compass.service_catalog.services import create_service, set_service_active
from tests.canonical_service_helpers import legacy_counseling_service


def sync_policy() -> None:
    call_command("sync_identity_policy", verbosity=0)


def make_user(email: str, role: str, *, active: bool = True) -> User:
    return User.objects.create_user(
        email=email,
        password="a-test-password",
        role=Role.objects.get(code=role),
        first_name=email.split("@")[0].title(),
        last_name="User",
        is_active=active,
    )


def context(actor: User) -> AuditContext:
    return AuditContext.user(actor)


def auth_client(user: User, *, recent_mfa: bool = False) -> Client:
    now = timezone.now()
    issued = create_auth_session(
        user,
        now=now,
        mfa_verified_at=now if recent_mfa else None,
    )
    client = Client()
    client.cookies["compass_session"] = issued.token
    return client


def csrf(client: Client) -> dict[str, str]:
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    return {"HTTP_X_CSRFTOKEN": response.json()["csrf_token"]}


def make_service(actor: User):
    service = create_service(
        code="SCOPE_SERVICE",
        name="Scope Service",
        appointment_booking_enabled=True,
        default_appointment_duration_minutes=60,
        cancellation_cutoff_minutes=30,
        delivery_modes=["IN_PERSON"],
        context=context(actor),
    )
    return set_service_active(service_id=service.pk, is_active=True, context=context(actor))


def make_counseling_service(actor: User):
    service = legacy_counseling_service(
        code="COUNSELING",
        name="Counseling",
        appointment_booking_enabled=True,
        default_appointment_duration_minutes=60,
        cancellation_cutoff_minutes=30,
        delivery_modes=["IN_PERSON"],
        context=context(actor),
    )
    return set_service_active(service_id=service.pk, is_active=True, context=context(actor))


def make_college(code: str, *, campus_active: bool = True, college_active: bool = True):
    campus = Campus.objects.create(
        code=f"C-{code}",
        name=f"{code} Campus",
        is_active=campus_active,
    )
    return College.objects.create(
        campus=campus,
        code=f"COL-{code}",
        name=f"{code} College",
        is_active=college_active,
    )


def affiliate(student: User, college: College) -> None:
    StudentAffiliation.objects.create(student=student, college=college)


def appointment(*, reference: str, student: User, provider: User, service):
    start = timezone.now() + timedelta(days=7)
    return Appointment.objects.create(
        reference_code=reference,
        student=student,
        provider=provider,
        service=service,
        delivery_mode="IN_PERSON",
        starts_at=start,
        ends_at=start + timedelta(hours=1),
        cancellation_cutoff_minutes=30,
        created_by=student,
    )


@pytest.mark.django_db
def test_gss_default_capability_and_scope_list_get_filters_and_cancel():
    sync_policy()
    admin = make_user("scope-admin@example.edu", "IT_ADMIN")
    supervisor = make_user("scope-supervisor@example.edu", "COUNSELOR")
    other_counselor = make_user("scope-other-counselor@example.edu", "COUNSELOR")
    provider = make_user("scope-provider@example.edu", "COUNSELOR")
    gss = make_user("scope-gss@example.edu", "GUIDANCE_SERVICES_STAFF")
    in_student = make_user("scope-in-student@example.edu", "STUDENT")
    out_student = make_user("scope-out-student@example.edu", "STUDENT")
    in_college = make_college("IN")
    out_college = make_college("OUT")
    affiliate(in_student, in_college)
    affiliate(out_student, out_college)
    CounselorResponsibility.objects.create(college=in_college, counselor=supervisor)
    CounselorResponsibility.objects.create(college=out_college, counselor=other_counselor)
    StaffSupervision.objects.create(staff=gss, supervisor=supervisor)
    service = make_service(admin)
    inside = appointment(
        reference="APT-2099-100001",
        student=in_student,
        provider=provider,
        service=service,
    )
    outside = appointment(
        reference="APT-2099-100002",
        student=out_student,
        provider=provider,
        service=service,
    )

    assert gss.has_capability("appointments.manage")
    assert not gss.has_capability("counseling.view_assigned")
    assert not gss.has_capability("counseling.manage_assigned")
    assert not gss.has_capability("ecounseling.view_assigned")

    client = auth_client(gss, recent_mfa=True)
    listed = client.get("/api/v1/appointments")
    assert listed.status_code == 200
    assert [row["id"] for row in listed.json()["items"]] == [str(inside.pk)]

    filtered = client.get(f"/api/v1/appointments?student_id={outside.student_id}")
    assert filtered.status_code == 200
    assert filtered.json()["items"] == []
    searched = client.get("/api/v1/appointments?search=100002")
    assert searched.status_code == 200
    assert searched.json()["items"] == []

    assert client.get(f"/api/v1/appointments/{inside.pk}").status_code == 200
    assert client.get(f"/api/v1/appointments/{outside.pk}").status_code == 404

    denied = client.post(
        f"/api/v1/appointments/{outside.pk}/cancel",
        data=json.dumps({}),
        content_type="application/json",
        **csrf(client),
    )
    assert denied.status_code == 404
    outside.refresh_from_db()
    assert outside.status == "SCHEDULED"

    cancelled = client.post(
        f"/api/v1/appointments/{inside.pk}/cancel",
        data=json.dumps({}),
        content_type="application/json",
        **csrf(client),
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"


@pytest.mark.django_db
def test_gss_scope_fails_closed_for_broken_or_inactive_supervision_chain():
    sync_policy()
    admin = make_user("failclosed-admin@example.edu", "IT_ADMIN")
    provider = make_user("failclosed-provider@example.edu", "COUNSELOR")
    student = make_user("failclosed-student@example.edu", "STUDENT")
    college = make_college("BASE")
    affiliate(student, college)
    service = make_service(admin)
    appointment(
        reference="APT-2099-200001",
        student=student,
        provider=provider,
        service=service,
    )

    no_supervision = make_user("gss-none@example.edu", "GUIDANCE_SERVICES_STAFF")
    assert list_managed_appointments(actor=no_supervision).items == ()

    inactive_supervisor = make_user(
        "inactive-supervisor@example.edu",
        "COUNSELOR",
        active=False,
    )
    gss_inactive = make_user("gss-inactive@example.edu", "GUIDANCE_SERVICES_STAFF")
    StaffSupervision.objects.create(staff=gss_inactive, supervisor=inactive_supervisor)
    assert list_managed_appointments(actor=gss_inactive).items == ()

    no_responsibility = make_user("no-responsibility@example.edu", "COUNSELOR")
    gss_no_responsibility = make_user(
        "gss-no-responsibility@example.edu", "GUIDANCE_SERVICES_STAFF"
    )
    StaffSupervision.objects.create(
        staff=gss_no_responsibility,
        supervisor=no_responsibility,
    )
    assert list_managed_appointments(actor=gss_no_responsibility).items == ()

    inactive_college = make_college("INACTIVE-COLLEGE", college_active=False)
    inactive_college_student = make_user("inactive-college-student@example.edu", "STUDENT")
    affiliate(inactive_college_student, inactive_college)
    inactive_college_supervisor = make_user("inactive-college-supervisor@example.edu", "COUNSELOR")
    CounselorResponsibility.objects.create(
        college=inactive_college,
        counselor=inactive_college_supervisor,
    )
    gss_inactive_college = make_user("gss-inactive-college@example.edu", "GUIDANCE_SERVICES_STAFF")
    StaffSupervision.objects.create(
        staff=gss_inactive_college,
        supervisor=inactive_college_supervisor,
    )
    appointment(
        reference="APT-2099-200002",
        student=inactive_college_student,
        provider=provider,
        service=service,
    )
    assert list_managed_appointments(actor=gss_inactive_college).items == ()

    inactive_campus_college = make_college("INACTIVE-CAMPUS", campus_active=False)
    inactive_campus_student = make_user("inactive-campus-student@example.edu", "STUDENT")
    affiliate(inactive_campus_student, inactive_campus_college)
    inactive_campus_supervisor = make_user("inactive-campus-supervisor@example.edu", "COUNSELOR")
    CounselorResponsibility.objects.create(
        college=inactive_campus_college,
        counselor=inactive_campus_supervisor,
    )
    gss_inactive_campus = make_user("gss-inactive-campus@example.edu", "GUIDANCE_SERVICES_STAFF")
    StaffSupervision.objects.create(
        staff=gss_inactive_campus,
        supervisor=inactive_campus_supervisor,
    )
    appointment(
        reference="APT-2099-200003",
        student=inactive_campus_student,
        provider=provider,
        service=service,
    )
    assert list_managed_appointments(actor=gss_inactive_campus).items == ()


@pytest.mark.django_db
def test_head_provider_only_and_gss_under_head_still_use_handled_non_counseling_workload():
    sync_policy()
    admin = make_user("headscope-admin@example.edu", "IT_ADMIN")
    provider = make_user("headscope-provider@example.edu", "COUNSELOR")
    head = make_user("headscope-head@example.edu", "COUNSELOR")
    UserDesignation.objects.create(
        user=head,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )
    gss = make_user("headscope-gss@example.edu", "GUIDANCE_SERVICES_STAFF")
    StaffSupervision.objects.create(staff=gss, supervisor=head)

    assigned_college = make_college("HEAD-ASSIGNED")
    other_college = make_college("HEAD-OTHER")
    CounselorResponsibility.objects.create(college=assigned_college, counselor=head)
    CounselorResponsibility.objects.create(college=other_college, counselor=provider)
    assigned_student = make_user("head-assigned-student@example.edu", "STUDENT")
    other_student = make_user("head-other-student@example.edu", "STUDENT")
    affiliate(assigned_student, assigned_college)
    affiliate(other_student, other_college)
    service = make_service(admin)
    inside = appointment(
        reference="APT-2099-300001",
        student=assigned_student,
        provider=provider,
        service=service,
    )
    outside = appointment(
        reference="APT-2099-300002",
        student=other_student,
        provider=provider,
        service=service,
    )

    # General Guidance College visibility does not grant Appointment ownership.
    assert set(resolve_general_guidance_college_scope(gss).college_ids) == {
        assigned_college.pk,
        other_college.pk,
    }
    assert list_managed_appointments(actor=head).items == ()
    assert {row.pk for row in list_managed_appointments(actor=gss).items} == {inside.pk}
    assert {row.pk for row in list_managed_appointments(actor=provider).items} == {
        inside.pk,
        outside.pk,
    }
    for item in (inside, outside):
        with pytest.raises(AppointmentNotFound):
            get_appointment_for_actor(appointment_id=item.pk, actor=head)
    with pytest.raises(AppointmentNotFound):
        get_appointment_for_actor(appointment_id=outside.pk, actor=gss)

    # Head provider assignment, even in someone else's College, is sufficient.
    head_student = make_user("headscope-own-student@example.edu", "STUDENT")
    affiliate(head_student, other_college)
    mine = appointment(
        reference="APT-2099-300003",
        student=head_student,
        provider=head,
        service=service,
    )
    assert [row.pk for row in list_managed_appointments(actor=head).items] == [mine.pk]
    assert get_appointment_for_actor(appointment_id=mine.pk, actor=head).pk == mine.pk
    assert not appointment_management_access_allowed(gss, mine)


@pytest.mark.django_db
def test_counseling_appointment_is_relationship_only_across_list_get_filters_and_cancel():
    sync_policy()
    admin = make_user("privacy-admin@example.edu", "IT_ADMIN")
    anna = make_user("anna@example.edu", "STUDENT")
    counselor_a = make_user("privacy-counselor-a@example.edu", "COUNSELOR")
    counselor_b = make_user("privacy-counselor-b@example.edu", "COUNSELOR")
    head = make_user("privacy-head@example.edu", "COUNSELOR")
    gss = make_user("privacy-gss@example.edu", "GUIDANCE_SERVICES_STAFF")
    UserDesignation.objects.create(
        user=head,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )
    StaffSupervision.objects.create(staff=gss, supervisor=head)

    cas = make_college("PRIV-CAS")
    ccms = make_college("PRIV-CCMS")
    affiliate(anna, cas)
    CounselorResponsibility.objects.create(college=cas, counselor=counselor_a)
    CounselorResponsibility.objects.create(college=ccms, counselor=counselor_b)
    service = make_counseling_service(admin)
    item = appointment(
        reference="APT-2099-350001",
        student=anna,
        provider=counselor_b,
        service=service,
    )

    student_client = auth_client(anna)
    provider_client = auth_client(counselor_b, recent_mfa=True)
    counselor_a_client = auth_client(counselor_a, recent_mfa=True)
    head_client = auth_client(head, recent_mfa=True)
    gss_client = auth_client(gss, recent_mfa=True)

    own = student_client.get("/api/v1/appointments/me")
    assert own.status_code == 200
    assert [row["id"] for row in own.json()["items"]] == [str(item.pk)]
    assert student_client.get(f"/api/v1/appointments/{item.pk}").status_code == 200

    provider_list = provider_client.get("/api/v1/appointments")
    assert provider_list.status_code == 200
    assert [row["id"] for row in provider_list.json()["items"]] == [str(item.pk)]
    assert provider_client.get(f"/api/v1/appointments/{item.pk}").status_code == 200

    for client in (counselor_a_client, head_client, gss_client):
        listed = client.get("/api/v1/appointments")
        assert listed.status_code == 200
        assert listed.json()["items"] == []
        assert client.get(f"/api/v1/appointments/{item.pk}").status_code == 404

    probed = counselor_a_client.get(
        "/api/v1/appointments",
        {"student_id": str(anna.pk), "service_id": str(service.pk), "search": "350001"},
    )
    assert probed.status_code == 200
    assert probed.json()["items"] == []

    for client in (counselor_a_client, head_client, gss_client):
        denied = client.post(
            f"/api/v1/appointments/{item.pk}/cancel",
            data=json.dumps({}),
            content_type="application/json",
            **csrf(client),
        )
        assert denied.status_code == 404

    item.refresh_from_db()
    assert item.status == "SCHEDULED"

    cancelled = provider_client.post(
        f"/api/v1/appointments/{item.pk}/cancel",
        data=json.dumps({}),
        content_type="application/json",
        **csrf(provider_client),
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"


@pytest.mark.django_db
def test_head_sees_counseling_appointment_only_when_head_is_selected_provider():
    sync_policy()
    admin = make_user("provider-head-admin@example.edu", "IT_ADMIN")
    head = make_user("provider-head@example.edu", "COUNSELOR")
    other = make_user("provider-other@example.edu", "COUNSELOR")
    first_student = make_user("provider-head-student@example.edu", "STUDENT")
    second_student = make_user("provider-other-student@example.edu", "STUDENT")
    UserDesignation.objects.create(
        user=head,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )
    college = make_college("PROVIDER-HEAD")
    affiliate(first_student, college)
    affiliate(second_student, college)
    service = make_counseling_service(admin)
    assigned = appointment(
        reference="APT-2099-360001",
        student=first_student,
        provider=head,
        service=service,
    )
    unrelated = appointment(
        reference="APT-2099-360002",
        student=second_student,
        provider=other,
        service=service,
    )

    rows = list_managed_appointments(actor=head).items
    assert [row.pk for row in rows] == [assigned.pk]
    assert get_appointment_for_actor(appointment_id=assigned.pk, actor=head).pk == assigned.pk
    with pytest.raises(AppointmentNotFound):
        get_appointment_for_actor(appointment_id=unrelated.pk, actor=head)


@pytest.mark.django_db
def test_counselor_override_is_scoped_and_unsupported_role_overrides_fail_closed():
    sync_policy()
    admin = make_user("override-admin@example.edu", "IT_ADMIN")
    counselor = make_user("override-counselor@example.edu", "COUNSELOR")
    provider = make_user("override-provider@example.edu", "COUNSELOR")
    in_student = make_user("override-in-student@example.edu", "STUDENT")
    out_student = make_user("override-out-student@example.edu", "STUDENT")
    in_college = make_college("OVERRIDE-IN")
    out_college = make_college("OVERRIDE-OUT")
    affiliate(in_student, in_college)
    affiliate(out_student, out_college)
    CounselorResponsibility.objects.create(college=in_college, counselor=counselor)
    service = make_service(admin)
    inside = appointment(
        reference="APT-2099-400001",
        student=in_student,
        provider=provider,
        service=service,
    )
    outside = appointment(
        reference="APT-2099-400002",
        student=out_student,
        provider=provider,
        service=service,
    )
    capability = Capability.objects.get(code="appointments.manage")
    UserCapabilityOverride.objects.create(
        user=counselor,
        capability=capability,
        effect="GRANT",
        reason="temporary operational override",
    )
    assert counselor.has_capability("appointments.manage")
    assert [row.pk for row in list_managed_appointments(actor=counselor).items] == [inside.pk]
    with pytest.raises(AppointmentNotFound):
        get_appointment_for_actor(appointment_id=outside.pk, actor=counselor)

    institutional = make_user("override-officer@example.edu", "INSTITUTIONAL_OFFICER")
    UserDesignation.objects.create(
        user=institutional,
        designation=Designation.objects.get(code="DPO"),
    )
    student = make_user("override-student@example.edu", "STUDENT")
    for actor in (admin, institutional, student):
        UserCapabilityOverride.objects.create(
            user=actor,
            capability=capability,
            effect="GRANT",
            reason="synthetic stale override",
        )
        assert actor.has_capability("appointments.manage")
        assert list_managed_appointments(actor=actor).items == ()
        with pytest.raises(AppointmentNotFound):
            get_appointment_for_actor(appointment_id=inside.pk, actor=actor)


@pytest.mark.django_db
def test_counselor_baseline_management_is_limited_to_assigned_colleges():
    sync_policy()
    admin = make_user("baseline-scope-admin@example.edu", "IT_ADMIN")
    counselor = make_user("baseline-scope-counselor@example.edu", "COUNSELOR")
    provider = make_user("baseline-scope-provider@example.edu", "COUNSELOR")
    in_student = make_user("baseline-scope-in-student@example.edu", "STUDENT")
    out_student = make_user("baseline-scope-out-student@example.edu", "STUDENT")
    in_college = make_college("BASELINE-IN")
    out_college = make_college("BASELINE-OUT")
    affiliate(in_student, in_college)
    affiliate(out_student, out_college)
    CounselorResponsibility.objects.create(college=in_college, counselor=counselor)
    service = make_service(admin)
    inside = appointment(
        reference="APT-2099-500001",
        student=in_student,
        provider=provider,
        service=service,
    )
    outside = appointment(
        reference="APT-2099-500002",
        student=out_student,
        provider=provider,
        service=service,
    )

    assert counselor.has_capability("appointments.manage")
    client = auth_client(counselor, recent_mfa=True)

    listed = client.get("/api/v1/appointments")
    assert listed.status_code == 200
    assert [row["id"] for row in listed.json()["items"]] == [str(inside.pk)]
    assert client.get(f"/api/v1/appointments/{inside.pk}").status_code == 200
    assert client.get(f"/api/v1/appointments/{outside.pk}").status_code == 404

    filtered = client.get(f"/api/v1/appointments?student_id={outside.student_id}")
    assert filtered.status_code == 200
    assert filtered.json()["items"] == []
    searched = client.get("/api/v1/appointments?search=500002")
    assert searched.status_code == 200
    assert searched.json()["items"] == []

    denied = client.post(
        f"/api/v1/appointments/{outside.pk}/cancel",
        data=json.dumps({}),
        content_type="application/json",
        **csrf(client),
    )
    assert denied.status_code == 404
    outside.refresh_from_db()
    assert outside.status == "SCHEDULED"

    cancelled = client.post(
        f"/api/v1/appointments/{inside.pk}/cancel",
        data=json.dumps({}),
        content_type="application/json",
        **csrf(client),
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"


@pytest.mark.django_db
def test_head_provider_scope_matches_single_resource_lists_filters_counts_and_gss_delegation():
    sync_policy()
    admin = make_user("provider-boundary-admin@example.edu", "IT_ADMIN")
    carlo = make_user("provider-boundary-carlo@example.edu", "COUNSELOR")
    head = make_user("provider-boundary-head@example.edu", "COUNSELOR")
    head.designations.add(Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"))
    head_staff = make_user("provider-boundary-staff@example.edu", "GUIDANCE_SERVICES_STAFF")
    StaffSupervision.objects.create(staff=head_staff, supervisor=head)

    ccms = make_college("BEA-CCMS")
    head_college = make_college("BEA-HEAD")
    CounselorResponsibility.objects.create(college=ccms, counselor=carlo)
    CounselorResponsibility.objects.create(college=head_college, counselor=head)
    bea = make_user("provider-bea@example.edu", "STUDENT")
    bea_counseling = make_user("provider-bea-counseling@example.edu", "STUDENT")
    other = make_user("provider-other@example.edu", "STUDENT")
    head_student = make_user("provider-head-student@example.edu", "STUDENT")
    head_counseling_student = make_user("provider-head-counseling@example.edu", "STUDENT")
    for student, college in (
        (bea, ccms),
        (bea_counseling, ccms),
        (other, head_college),
        (head_student, ccms),
        (head_counseling_student, head_college),
    ):
        affiliate(student, college)
    ordinary = make_service(admin)
    counseling = make_counseling_service(admin)
    carlo_ordinary = appointment(
        reference="APT-2099-610001", student=bea, provider=carlo, service=ordinary
    )
    carlo_counseling = appointment(
        reference="APT-2099-610002",
        student=bea_counseling,
        provider=carlo,
        service=counseling,
    )
    # Even an explicitly Head-assigned College cannot authorize a different provider.
    head_college_other = appointment(
        reference="APT-2099-610003", student=other, provider=carlo, service=ordinary
    )
    head_ordinary = appointment(
        reference="APT-2099-610004",
        student=head_student,
        provider=head,
        service=ordinary,
    )
    head_counseling = appointment(
        reference="APT-2099-610005",
        student=head_counseling_student,
        provider=head,
        service=counseling,
    )
    all_items = (
        carlo_ordinary,
        carlo_counseling,
        head_college_other,
        head_ordinary,
        head_counseling,
    )
    assert set(resolve_general_guidance_college_scope(head).college_ids) == {
        ccms.pk,
        head_college.pk,
    }
    assert set(resolve_general_guidance_college_scope(head_staff).college_ids) == {
        ccms.pk,
        head_college.pk,
    }
    assert {row.pk for row in list_managed_appointments(actor=head).items} == {
        head_ordinary.pk,
        head_counseling.pk,
    }
    assert {row.pk for row in list_managed_appointments(actor=head_staff).items} == {
        head_college_other.pk,
    }
    assert count_upcoming_managed_appointments(actor=head) == 2
    assert count_upcoming_managed_appointments(actor=head_staff) == 1
    # Carlo also retains College-delegated management of Head's non-Counseling appointment.
    assert count_upcoming_managed_appointments(actor=carlo) == 4

    # Queryset, single-resource and action authorization must have identical ownership.
    scoped = {row.pk for row in scope_managed_appointments(Appointment.objects.all(), head)}
    for item in all_items:
        expected = item.provider_id == head.pk
        assert appointment_management_access_allowed(head, item) is expected
        assert (item.pk in scoped) is expected
        if not expected:
            actions = appointment_actions_for(actor=head, item=item)
            assert actions.cancel.blocker == "NOT_PERMITTED"
            assert actions.reschedule.blocker == "NOT_PERMITTED"
        if expected:
            assert get_appointment_for_actor(appointment_id=item.pk, actor=head).pk == item.pk
        else:
            with pytest.raises(AppointmentNotFound):
                get_appointment_for_actor(appointment_id=item.pk, actor=head)
            with pytest.raises(AppointmentNotFound):
                get_appointment_history(appointment_id=item.pk, actor=head)

    head_client = auth_client(head, recent_mfa=True)
    ids = {str(head_ordinary.pk), str(head_counseling.pk)}
    for query in (
        {},
        {"provider_id": str(carlo.pk)},
        {"student_id": str(bea.pk)},
        {"service_id": str(ordinary.pk)},
        {"delivery_mode": "IN_PERSON"},
        {"status": "SCHEDULED"},
        {"search": "610001"},
        {"upcoming": "true"},
        {"page": "1", "page_size": "1"},
    ):
        response = head_client.get("/api/v1/appointments", query)
        assert response.status_code == 200
        assert {row["id"] for row in response.json()["items"]} <= ids
    assert head_client.get(
        "/api/v1/appointments", {"search": carlo_ordinary.reference_code}
    ).json()["items"] == []
    for item in (carlo_ordinary, carlo_counseling, head_college_other):
        assert head_client.get(f"/api/v1/appointments/{item.pk}").status_code == 404
        assert head_client.get(f"/api/v1/appointments/{item.pk}/history").status_code == 404
    assert head_client.get(f"/api/v1/appointments/{head_ordinary.pk}").status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize("service_type", ["NON_COUNSELING", "COUNSELING"])
def test_head_unowned_appointment_all_actions_denied_before_mutation(service_type):
    sync_policy()
    admin = make_user(f"denied-admin-{service_type}@example.edu", "IT_ADMIN")
    carlo = make_user(f"denied-carlo-{service_type}@example.edu", "COUNSELOR")
    head = make_user(f"denied-head-{service_type}@example.edu", "COUNSELOR")
    head.designations.add(Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"))
    college = make_college(f"DENIED-{service_type}")
    CounselorResponsibility.objects.create(college=college, counselor=head)
    bea = make_user(f"denied-bea-{service_type}@example.edu", "STUDENT")
    affiliate(bea, college)
    service = (
        make_counseling_service(admin)
        if service_type == "COUNSELING"
        else make_service(admin)
    )
    item = appointment(
        reference=f"APT-2099-{620001 if service_type == 'COUNSELING' else 620002}",
        student=bea,
        provider=carlo,
        service=service,
    )
    assert not appointment_management_access_allowed(head, item)
    assert all(
        state.blocker == "NOT_PERMITTED"
        for state in (
            appointment_actions_for(actor=head, item=item).cancel,
            appointment_actions_for(actor=head, item=item).reschedule,
            appointment_actions_for(actor=head, item=item).reassign,
            appointment_actions_for(actor=head, item=item).complete,
            appointment_actions_for(actor=head, item=item).mark_no_show,
        )
    )
    client = auth_client(head, recent_mfa=True)
    headers = csrf(client)
    baseline_audit = AuditEvent.objects.count()
    baseline_notifications = Notification.objects.count()
    baseline_history = AppointmentChangeEvent.objects.count()
    base = f"/api/v1/appointments/{item.pk}"
    for path in (
        base,
        base + "/history",
        base + "/reschedule-slots?date=" + item.starts_at.date().isoformat(),
        base + "/reassignment-candidates",
    ):
        assert client.get(path).status_code == 404
    for route, data in (
        ("cancel", {}),
        ("reschedule", {"starts_at": (item.starts_at + timedelta(days=1)).isoformat()}),
        ("reassign", {"provider_id": str(head.pk), "reason": "Synthetic reassignment"}),
        ("complete", {}),
        ("no-show", {}),
    ):
        response = client.post(
            base + "/" + route,
            data=json.dumps(data),
            content_type="application/json",
            **headers,
        )
        assert response.status_code == 404, (route, response.content)
    item.refresh_from_db()
    assert item.status == "SCHEDULED"
    assert item.provider_id == carlo.pk
    assert AppointmentChangeEvent.objects.count() == baseline_history
    assert AuditEvent.objects.count() == baseline_audit
    assert Notification.objects.count() == baseline_notifications
    # Valid provider and Student self access are unaffected.
    assert get_appointment_for_actor(appointment_id=item.pk, actor=carlo).pk == item.pk
    assert get_appointment_for_actor(appointment_id=item.pk, actor=bea).pk == item.pk


@pytest.mark.django_db
def test_head_revoked_manage_capability_allows_self_view_but_no_management():
    sync_policy()
    admin = make_user("revoked-head-admin@example.edu", "IT_ADMIN")
    head = make_user("revoked-head@example.edu", "COUNSELOR")
    head.designations.add(Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"))
    student = make_user("revoked-head-student@example.edu", "STUDENT")
    affiliate(student, make_college("REVOKED-HEAD"))
    item = appointment(
        reference="APT-2099-630001",
        student=student,
        provider=head,
        service=make_service(admin),
    )
    revoke = UserCapabilityOverride.objects.create(
        user=head,
        capability=Capability.objects.get(code="appointments.manage"),
        effect="REVOKE",
        reason="Synthetic management restriction",
    )
    assert head.has_capability("appointments.view_self")
    assert not appointment_management_access_allowed(head, item)
    assert list_managed_appointments(actor=head).items == ()
    assert count_upcoming_managed_appointments(actor=head) is None
    assert get_appointment_for_actor(appointment_id=item.pk, actor=head).pk == item.pk
    assert get_appointment_history(appointment_id=item.pk, actor=head)
    assert all(
        state.blocker == "NOT_PERMITTED"
        for state in (
            appointment_actions_for(actor=head, item=item).cancel,
            appointment_actions_for(actor=head, item=item).reassign,
        )
    )
    assert auth_client(head).get(f"/api/v1/appointments/{item.pk}").status_code == 200
    revoke.delete()
    assert appointment_management_access_allowed(head, item)


@pytest.mark.django_db
def test_multiple_heads_have_independent_provider_ownership():
    sync_policy()
    admin = make_user("heads-admin@example.edu", "IT_ADMIN")
    head_a = make_user("heads-a@example.edu", "COUNSELOR")
    head_b = make_user("heads-b@example.edu", "COUNSELOR")
    designation = Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR")
    head_a.designations.add(designation)
    head_b.designations.add(designation)
    college = make_college("HEADS-INSTITUTION")
    student_a = make_user("heads-student-a@example.edu", "STUDENT")
    student_b = make_user("heads-student-b@example.edu", "STUDENT")
    affiliate(student_a, college)
    affiliate(student_b, college)
    service = make_service(admin)
    appointment_a = appointment(
        reference="APT-2099-640001", student=student_a, provider=head_a, service=service
    )
    appointment_b = appointment(
        reference="APT-2099-640002", student=student_b, provider=head_b, service=service
    )
    assert set(resolve_general_guidance_college_scope(head_a).college_ids) == {college.pk}
    assert set(resolve_general_guidance_college_scope(head_b).college_ids) == {college.pk}
    assert [row.pk for row in list_managed_appointments(actor=head_a).items] == [appointment_a.pk]
    assert [row.pk for row in list_managed_appointments(actor=head_b).items] == [appointment_b.pk]
    with pytest.raises(AppointmentNotFound):
        get_appointment_for_actor(appointment_id=appointment_b.pk, actor=head_a)
    with pytest.raises(AppointmentNotFound):
        get_appointment_for_actor(appointment_id=appointment_a.pk, actor=head_b)


@pytest.mark.django_db
def test_reassignment_immediately_transfers_head_provider_authorization():
    sync_policy()
    admin = make_user("transfer-admin@example.edu", "IT_ADMIN")
    head = make_user("transfer-head@example.edu", "COUNSELOR")
    carlo = make_user("transfer-carlo@example.edu", "COUNSELOR")
    head.designations.add(Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"))
    student = make_user("transfer-student@example.edu", "STUDENT")
    college = make_college("TRANSFER")
    CounselorResponsibility.objects.create(college=college, counselor=carlo)
    affiliate(student, college)
    item = appointment(
        reference="APT-2099-650001",
        student=student,
        provider=head,
        service=make_service(admin),
    )
    assert get_appointment_for_actor(appointment_id=item.pk, actor=head).pk == item.pk
    # This test isolates ownership transfer from the independent availability
    # and service-qualification engines, which have their own regression suites.
    with (
        patch("compass.appointments.services._validate_existing_service"),
        patch("compass.appointments.services._interval_is_available", return_value=True),
        patch("compass.appointments.services._has_overlap", return_value=False),
    ):
        reassign_appointment(
            appointment_id=item.pk,
            actor=head,
            provider_id=carlo.pk,
            reason="Synthetic provider transfer",
            context=context(head),
        )
        with pytest.raises(AppointmentNotFound):
            get_appointment_for_actor(appointment_id=item.pk, actor=head)
        assert list_managed_appointments(actor=head).items == ()
        assert get_appointment_for_actor(appointment_id=item.pk, actor=carlo).pk == item.pk
        assert get_appointment_history(appointment_id=item.pk, actor=carlo)
        reassign_appointment(
            appointment_id=item.pk,
            actor=carlo,
            provider_id=head.pk,
            reason="Synthetic return transfer",
            context=context(carlo),
        )
    item.refresh_from_db()
    assert item.provider_id == head.pk
    assert get_appointment_for_actor(appointment_id=item.pk, actor=head).pk == item.pk
    assert AppointmentChangeEvent.objects.filter(appointment=item).count() == 2


