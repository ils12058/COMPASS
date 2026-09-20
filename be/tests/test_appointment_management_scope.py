from __future__ import annotations

import json
from datetime import timedelta

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
from compass.appointments.models import Appointment
from compass.appointments.services import (
    AppointmentNotFound,
    get_appointment_for_actor,
    list_managed_appointments,
)
from compass.audit.context import AuditContext
from compass.authentication.sessions import create_auth_session
from compass.organization.models import (
    Campus,
    College,
    CounselorResponsibility,
    StaffSupervision,
    StudentAffiliation,
)
from compass.service_catalog.services import create_service, set_service_active


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
        appointment_policy="OPTIONAL",
        default_duration_minutes=60,
        cancellation_cutoff_minutes=30,
        delivery_modes=["IN_PERSON"],
        provider_roles=["COUNSELOR"],
        context=context(actor),
    )
    return set_service_active(service_id=service.pk, is_active=True, context=context(actor))


def make_counseling_service(actor: User):
    service = create_service(
        code="COUNSELING",
        name="Counseling",
        appointment_policy="OPTIONAL",
        default_duration_minutes=60,
        cancellation_cutoff_minutes=30,
        delivery_modes=["IN_PERSON"],
        provider_roles=["COUNSELOR"],
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
def test_head_and_gss_supervised_by_head_are_institution_wide_for_ordinary_appointments():
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

    assert {row.pk for row in list_managed_appointments(actor=head).items} == {
        inside.pk,
        outside.pk,
    }
    assert {row.pk for row in list_managed_appointments(actor=gss).items} == {
        inside.pk,
        outside.pk,
    }
    assert get_appointment_for_actor(appointment_id=outside.pk, actor=head).pk == outside.pk
    assert get_appointment_for_actor(appointment_id=outside.pk, actor=gss).pk == outside.pk


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
