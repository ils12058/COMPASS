from __future__ import annotations

from datetime import timedelta

import pytest
from django.core.management import call_command
from django.test import Client
from django.utils import timezone

from compass.accounts.models import Designation, Role, User, UserDesignation
from compass.appointments.models import Appointment, AppointmentStatus
from compass.audit.context import AuditContext
from compass.authentication.sessions import create_auth_session
from compass.counseling.context_access import (
    CounselingContextNotFound,
    CounselingContextSource,
    resolve_counseling_context,
)
from compass.counseling.context_services import (
    get_context_inventory,
    get_context_support_indicators,
    list_context_history,
    list_context_shared_summaries,
)
from compass.counseling.models import (
    CounselingEncounter,
    CounselingEntryMode,
    CounselingSharedSummary,
)
from compass.counseling.services import CounselingNotFound, get_encounter_for_actor
from compass.inventory.models import StudentInventory
from compass.inventory.services import (
    ensure_current_inventory,
    replace_current_inventory,
    submit_current_inventory,
)
from compass.notifications.models import EmailDelivery, Notification
from compass.organization.models import (
    AcademicYear,
    Campus,
    College,
    CounselorResponsibility,
    Program,
    StaffSupervision,
    StudentAffiliation,
)
from compass.routine_interviews.services import (
    create_direct,
    get_assigned,
    replace_my_intake,
    submit_my_intake,
)
from compass.service_catalog.services import set_service_active
from compass.student_support.models import (
    FourPsStatus,
    IndigenousPeoplesStatus,
    ParentLifeStatus,
    StudentSupportProfile,
)
from compass.student_support.services import build_student_support_context
from tests.canonical_service_helpers import legacy_counseling_service
from tests.inventory_test_helpers import minimum_normalized_inventory_values


def sync_policy() -> None:
    call_command("sync_identity_policy", verbosity=0)


def make_user(email: str, role: str, *, institutional_id: str | None = None) -> User:
    return User.objects.create_user(
        email=email,
        password="a-test-password",
        role=Role.objects.get(code=role),
        first_name=email.split("@")[0].replace(".", " ").title(),
        last_name="User",
        institutional_id=institutional_id,
    )


def make_head(email: str = "context-head@example.edu") -> User:
    head = make_user(email, "COUNSELOR")
    UserDesignation.objects.create(
        user=head,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )
    return head


def audit_context(actor: User) -> AuditContext:
    return AuditContext.user(actor)


def auth_client(user: User) -> Client:
    session = create_auth_session(user, now=timezone.now())
    client = Client()
    client.cookies["compass_session"] = session.token
    return client


def make_org(code: str) -> tuple[Campus, College, Program]:
    campus = Campus.objects.create(code=f"CTX-{code}", name=f"Context Campus {code}")
    college = College.objects.create(
        campus=campus,
        code=f"CTX-{code}",
        name=f"Context College {code}",
    )
    program = Program.objects.create(
        college=college,
        code=f"CTX-{code}",
        name=f"Context Program {code}",
    )
    return campus, college, program


def make_counseling_service(admin: User):
    service = legacy_counseling_service(
        code="COUNSELING",
        name="Counseling",
        appointment_policy="OPTIONAL",
        default_duration_minutes=60,
        cancellation_cutoff_minutes=30,
        requires_current_inventory=False,
        delivery_modes=["IN_PERSON", "ONLINE"],
        provider_roles=["COUNSELOR"],
        context=audit_context(admin),
    )
    return set_service_active(
        service_id=service.pk,
        is_active=True,
        context=audit_context(admin),
    )


def make_inventory(
    *,
    student: User,
    program: Program,
    submitted: bool = True,
    positive_indicators: bool = False,
) -> StudentInventory:
    ensure_current_inventory(student=student, context=audit_context(student))
    values = minimum_normalized_inventory_values(program_id=program.pk)
    values.update(
        {
            "full_name_snapshot": student.get_full_name(),
            "course_currently_enrolled": program.name,
            "major": "Context Major",
        }
    )
    if positive_indicators:
        values.update(
            {
                "pwd_status": "PWD",
                "physical_disadvantage": "Self-reported PWD detail for test projection.",
                "civil_status_category": "SOLO_PARENT",
                "support_profile": {
                    "four_ps_status": "BENEFICIARY",
                    "indigenous_peoples_status": "MEMBER",
                    "mother_life_status": "DECEASED",
                    "father_life_status": "DECEASED",
                },
            }
        )
    item = replace_current_inventory(student=student, values=values)
    if submitted:
        item = submit_current_inventory(student=student, context=audit_context(student))
    return item


def make_appointment(
    *,
    student: User,
    counselor: User,
    service,
    starts_at,
    status: str = AppointmentStatus.SCHEDULED,
) -> Appointment:
    terminal = {}
    if status == AppointmentStatus.CANCELLED:
        terminal = {
            "cancelled_at": starts_at - timedelta(hours=1),
            "cancelled_by": student,
        }
    elif status == AppointmentStatus.COMPLETED:
        terminal = {
            "completed_at": starts_at + timedelta(hours=1),
            "completed_by": counselor,
        }
    elif status == AppointmentStatus.NO_SHOW:
        terminal = {
            "no_show_at": starts_at + timedelta(hours=1),
            "no_show_by": counselor,
        }
    return Appointment.objects.create(
        reference_code=f"APT-2099-{Appointment.objects.count() + 1:06d}",
        student=student,
        provider=counselor,
        service=service,
        delivery_mode="IN_PERSON",
        starts_at=starts_at,
        ends_at=starts_at + timedelta(hours=1),
        status=status,
        cancellation_cutoff_minutes=30,
        created_by=student,
        **terminal,
    )


@pytest.fixture
def world(db):
    sync_policy()
    admin = make_user("context-admin@example.edu", "IT_ADMIN")
    anna = make_user("anna.context@example.edu", "STUDENT", institutional_id="ANNA-001")
    counselor_a = make_user("counselor.a.context@example.edu", "COUNSELOR")
    counselor_b = make_user("counselor.b.context@example.edu", "COUNSELOR")
    unrelated = make_user("unrelated.context@example.edu", "COUNSELOR")
    head = make_head()
    gss = make_user("context-gss@example.edu", "GUIDANCE_SERVICES_STAFF")
    StaffSupervision.objects.create(staff=gss, supervisor=head)

    _, cas, cas_program = make_org("CAS")
    _, ccms, _ccms_program = make_org("CCMS")
    StudentAffiliation.objects.create(student=anna, college=cas)
    CounselorResponsibility.objects.create(college=cas, counselor=counselor_a)
    CounselorResponsibility.objects.create(college=ccms, counselor=counselor_b)

    AcademicYear.objects.create(label="2026-2027", is_current=True)
    service = make_counseling_service(admin)
    inventory = make_inventory(
        student=anna,
        program=cas_program,
        submitted=True,
        positive_indicators=True,
    )
    return {
        "admin": admin,
        "anna": anna,
        "a": counselor_a,
        "b": counselor_b,
        "unrelated": unrelated,
        "head": head,
        "gss": gss,
        "cas": cas,
        "cas_program": cas_program,
        "ccms": ccms,
        "service": service,
        "inventory": inventory,
    }


@pytest.mark.django_db
def test_appointment_context_is_exact_provider_time_bounded_and_cancel_revokes(world):
    base = timezone.now().replace(microsecond=0)
    appointment = make_appointment(
        student=world["anna"],
        counselor=world["b"],
        service=world["service"],
        starts_at=base + timedelta(days=3),
    )

    with pytest.raises(CounselingContextNotFound):
        resolve_counseling_context(
            actor=world["b"],
            anchor_type=CounselingContextSource.APPOINTMENT,
            anchor_id=appointment.pk,
            now=base,
        )

    inside = appointment.starts_at - timedelta(hours=12)
    access = resolve_counseling_context(
        actor=world["b"],
        anchor_type="APPOINTMENT",
        anchor_id=appointment.pk,
        now=inside,
    )
    assert access.student_id == world["anna"].pk
    assert access.counselor_id == world["b"].pk
    assert access.appointment_id == appointment.pk

    for actor in (world["a"], world["head"], world["unrelated"], world["gss"]):
        with pytest.raises(CounselingContextNotFound):
            resolve_counseling_context(
                actor=actor,
                anchor_type="APPOINTMENT",
                anchor_id=appointment.pk,
                now=inside,
            )

    appointment.status = AppointmentStatus.CANCELLED
    appointment.cancelled_at = inside
    appointment.cancelled_by = world["anna"]
    appointment.save(update_fields=["status", "cancelled_at", "cancelled_by", "updated_at"])
    with pytest.raises(CounselingContextNotFound):
        resolve_counseling_context(
            actor=world["b"],
            anchor_type="APPOINTMENT",
            anchor_id=appointment.pk,
            now=inside,
        )


@pytest.mark.django_db
def test_head_has_context_only_when_head_is_exact_appointment_provider(world):
    now = timezone.now().replace(microsecond=0)
    head_appointment = make_appointment(
        student=world["anna"],
        counselor=world["head"],
        service=world["service"],
        starts_at=now + timedelta(hours=4),
    )
    b_appointment = make_appointment(
        student=world["anna"],
        counselor=world["b"],
        service=world["service"],
        starts_at=now + timedelta(hours=8),
    )

    access = resolve_counseling_context(
        actor=world["head"],
        anchor_type="APPOINTMENT",
        anchor_id=head_appointment.pk,
        now=now,
    )
    assert access.counselor_id == world["head"].pk

    with pytest.raises(CounselingContextNotFound):
        resolve_counseling_context(
            actor=world["head"],
            anchor_type="APPOINTMENT",
            anchor_id=b_appointment.pk,
            now=now,
        )


@pytest.mark.django_db
def test_appointment_completed_encounter_extends_context_but_own_record_survives_expiry(world):
    appointment_start = timezone.now().replace(microsecond=0) - timedelta(hours=1)
    appointment = make_appointment(
        student=world["anna"],
        counselor=world["b"],
        service=world["service"],
        starts_at=appointment_start,
    )
    encounter = CounselingEncounter.objects.create(
        student=world["anna"],
        counselor=world["b"],
        service=world["service"],
        appointment=appointment,
        entry_mode=CounselingEntryMode.APPOINTMENT,
        delivery_mode="IN_PERSON",
        started_at=appointment_start,
        ended_at=appointment_start + timedelta(minutes=50),
        created_by=world["b"],
    )

    within_extension = encounter.ended_at + timedelta(days=6)
    access = resolve_counseling_context(
        actor=world["b"],
        anchor_type="APPOINTMENT",
        anchor_id=appointment.pk,
        now=within_extension,
    )
    assert access.encounter_id == encounter.pk
    assert access.valid_until == encounter.ended_at + timedelta(days=7)

    after_expiry = encounter.ended_at + timedelta(days=8)
    with pytest.raises(CounselingContextNotFound):
        resolve_counseling_context(
            actor=world["b"],
            anchor_type="APPOINTMENT",
            anchor_id=appointment.pk,
            now=after_expiry,
        )

    assert get_encounter_for_actor(encounter_id=encounter.pk, actor=world["b"]).pk == encounter.pk


@pytest.mark.django_db
def test_appointment_without_encounter_expires_after_uncompleted_grace(world):
    start = timezone.now().replace(microsecond=0) - timedelta(days=3)
    appointment = make_appointment(
        student=world["anna"],
        counselor=world["b"],
        service=world["service"],
        starts_at=start,
    )
    with pytest.raises(CounselingContextNotFound):
        resolve_counseling_context(
            actor=world["b"],
            anchor_type="APPOINTMENT",
            anchor_id=appointment.pk,
            now=appointment.ends_at + timedelta(hours=25),
        )


@pytest.mark.django_db
def test_direct_creation_needs_student_submission_and_notification_is_idempotent(world):
    item = create_direct(
        counselor=world["b"],
        student_id=world["anna"].pk,
        entry_mode="WALK_IN",
        delivery_mode="IN_PERSON",
        idempotency_key="context-direct-key",
        request_fingerprint="a" * 64,
        context=audit_context(world["b"]),
    )
    replay = create_direct(
        counselor=world["b"],
        student_id=world["anna"].pk,
        entry_mode="WALK_IN",
        delivery_mode="IN_PERSON",
        idempotency_key="context-direct-key",
        request_fingerprint="a" * 64,
        context=audit_context(world["b"]),
    )
    assert replay.pk == item.pk
    assert get_assigned(counselor=world["b"], routine_interview_id=item.pk).pk == item.pk

    notifications = Notification.objects.filter(
        recipient=world["anna"],
        event_code="routine_interview.intake_ready",
        source_type="routine_interview",
        source_id=item.pk,
    )
    assert notifications.count() == 1
    notification = notifications.get()
    combined = f"{notification.title} {notification.message}"
    for forbidden in (
        "FOUR_PS_BENEFICIARY",
        "PWD",
        "INDIGENOUS_PEOPLES_MEMBER",
        "concern",
        "evaluation",
        "referral reason",
    ):
        assert forbidden.lower() not in combined.lower()
    assert not EmailDelivery.objects.filter(notification=notification).exists()

    with pytest.raises(CounselingContextNotFound):
        resolve_counseling_context(
            actor=world["b"],
            anchor_type="ROUTINE_INTERVIEW",
            anchor_id=item.pk,
        )

    replace_my_intake(
        student=world["anna"],
        routine_interview_id=item.pk,
        values={"coping_with_college_challenges": "PRIVATE-DRAFT-INTAKE-SENTINEL"},
    )
    with pytest.raises(CounselingContextNotFound):
        resolve_counseling_context(
            actor=world["b"],
            anchor_type="ROUTINE_INTERVIEW",
            anchor_id=item.pk,
        )

    submitted = submit_my_intake(
        student=world["anna"],
        routine_interview_id=item.pk,
        context=audit_context(world["anna"]),
    )
    access = resolve_counseling_context(
        actor=world["b"],
        anchor_type="ROUTINE_INTERVIEW",
        anchor_id=item.pk,
        now=submitted.intake_submitted_at + timedelta(minutes=1),
    )
    assert access.student_id == world["anna"].pk

    for actor in (world["a"], world["head"], world["unrelated"], world["gss"]):
        with pytest.raises(CounselingContextNotFound):
            resolve_counseling_context(
                actor=actor,
                anchor_type="ROUTINE_INTERVIEW",
                anchor_id=item.pk,
                now=submitted.intake_submitted_at + timedelta(minutes=1),
            )


@pytest.mark.django_db
@pytest.mark.parametrize("entry_mode", ["WALK_IN", "CALLED_IN", "REFERRED"])
def test_matching_direct_encounter_extends_context_and_mismatch_does_not(world, entry_mode):
    item = create_direct(
        counselor=world["b"],
        student_id=world["anna"].pk,
        entry_mode=entry_mode,
        delivery_mode="IN_PERSON",
        idempotency_key=f"context-{entry_mode}",
        request_fingerprint={
            "WALK_IN": "b",
            "CALLED_IN": "c",
            "REFERRED": "d",
        }[entry_mode]
        * 64,
        context=audit_context(world["b"]),
    )
    replace_my_intake(
        student=world["anna"],
        routine_interview_id=item.pk,
        values={"college_experience": f"Submitted for {entry_mode}"},
    )
    item = submit_my_intake(
        student=world["anna"],
        routine_interview_id=item.pk,
        context=audit_context(world["anna"]),
    )
    activation = item.intake_submitted_at.replace(microsecond=0)
    type(item).objects.filter(pk=item.pk).update(intake_submitted_at=activation)
    item.refresh_from_db()

    mismatched = CounselingEncounter.objects.create(
        student=world["anna"],
        counselor=world["b"],
        service=world["service"],
        appointment=None,
        entry_mode="REFERRED" if entry_mode != "REFERRED" else "WALK_IN",
        delivery_mode="IN_PERSON",
        started_at=activation + timedelta(hours=1),
        ended_at=activation + timedelta(hours=2),
        created_by=world["b"],
    )
    assert mismatched.pk is not None
    with pytest.raises(CounselingContextNotFound):
        resolve_counseling_context(
            actor=world["b"],
            anchor_type="ROUTINE_INTERVIEW",
            anchor_id=item.pk,
            now=activation + timedelta(hours=25),
        )

    matching = CounselingEncounter.objects.create(
        student=world["anna"],
        counselor=world["b"],
        service=world["service"],
        appointment=None,
        entry_mode=entry_mode,
        delivery_mode="IN_PERSON",
        started_at=activation + timedelta(hours=3),
        ended_at=activation + timedelta(hours=4),
        created_by=world["b"],
    )
    access = resolve_counseling_context(
        actor=world["b"],
        anchor_type="ROUTINE_INTERVIEW",
        anchor_id=item.pk,
        now=matching.ended_at + timedelta(days=6),
    )
    assert access.encounter_id == matching.pk

    with pytest.raises(CounselingContextNotFound):
        resolve_counseling_context(
            actor=world["b"],
            anchor_type="ROUTINE_INTERVIEW",
            anchor_id=item.pk,
            now=matching.ended_at + timedelta(days=8),
        )


@pytest.mark.django_db
def test_contextual_inventory_and_support_do_not_weaken_generic_authorization(world):
    now = timezone.now().replace(microsecond=0)
    appointment = make_appointment(
        student=world["anna"],
        counselor=world["b"],
        service=world["service"],
        starts_at=now + timedelta(hours=2),
    )
    access = resolve_counseling_context(
        actor=world["b"],
        anchor_type="APPOINTMENT",
        anchor_id=appointment.pk,
        now=now,
    )

    inventory_context = get_context_inventory(access)
    assert inventory_context.available is True
    assert inventory_context.inventory.id == world["inventory"].pk

    support = get_context_support_indicators(access)
    codes = [indicator.code for indicator in support.indicators]
    assert codes == [
        "PWD",
        "SOLO_PARENT",
        "FOUR_PS_BENEFICIARY",
        "INDIGENOUS_PEOPLES_MEMBER",
        "MOTHER_DECEASED",
        "FATHER_DECEASED",
    ]
    canonical = build_student_support_context(student=world["anna"])
    assert [indicator.code for indicator in canonical.indicators] == codes

    b_client = auth_client(world["b"])
    contextual_inventory = b_client.get(
        f"/api/v1/counseling/context/APPOINTMENT/{appointment.pk}/inventory"
    )
    contextual_support = b_client.get(
        f"/api/v1/counseling/context/APPOINTMENT/{appointment.pk}/support-indicators"
    )
    assert contextual_inventory.status_code == 200
    contextual_inventory_body = contextual_inventory.json()
    assert contextual_inventory_body["available"] is True
    full_inventory = contextual_inventory_body["inventory"]
    assert full_inventory["id"] == str(world["inventory"].pk)
    assert full_inventory["physical_disadvantage"] == (
        "Self-reported PWD detail for test projection."
    )
    assert len(full_inventory["family_members"]) == 2
    assert full_inventory["support_profile"]["four_ps_status"] == "BENEFICIARY"
    assert "current_concerns" in full_inventory
    assert "geographic_locations" in full_inventory
    assert contextual_support.status_code == 200
    assert b_client.get(f"/api/v1/inventory/records/{world['inventory'].pk}").status_code == 404
    assert (
        b_client.get(f"/api/v1/student-support/students/{world['anna'].pk}/context").status_code
        == 404
    )

    a_client = auth_client(world["a"])
    assert a_client.get(f"/api/v1/inventory/records/{world['inventory'].pk}").status_code == 200
    assert (
        a_client.get(f"/api/v1/student-support/students/{world['anna'].pk}/context").status_code
        == 200
    )


@pytest.mark.django_db
def test_context_support_indicators_use_only_current_submitted_inventory(world):
    now = timezone.now().replace(microsecond=0)

    draft_student = make_user("draft.context@example.edu", "STUDENT", institutional_id="DRAFT-001")
    _, draft_college, draft_program = make_org("DRAFT")
    StudentAffiliation.objects.create(student=draft_student, college=draft_college)
    draft_inventory = make_inventory(
        student=draft_student,
        program=draft_program,
        submitted=False,
        positive_indicators=True,
    )
    draft_appointment = make_appointment(
        student=draft_student,
        counselor=world["b"],
        service=world["service"],
        starts_at=now + timedelta(hours=3),
    )
    draft_access = resolve_counseling_context(
        actor=world["b"],
        anchor_type="APPOINTMENT",
        anchor_id=draft_appointment.pk,
        now=now,
    )
    draft_context = get_context_support_indicators(draft_access)
    assert draft_context.inventory_status == "DRAFT"
    assert draft_context.available is False
    assert draft_context.indicators == ()
    assert draft_inventory.submitted_at is None

    missing_student = make_user(
        "missing.context@example.edu",
        "STUDENT",
        institutional_id="MISSING-001",
    )
    _, missing_college, missing_program = make_org("MISSING")
    StudentAffiliation.objects.create(student=missing_student, college=missing_college)
    historical_year = AcademicYear.objects.create(label="2025-2026", is_current=False)
    historical = StudentInventory.objects.create(
        student=missing_student,
        academic_year=historical_year,
        form_revision=world["inventory"].form_revision,
        program=missing_program,
        year_level=1,
        submitted_at=now - timedelta(days=200),
        pwd_status="NOT_SPECIFIED",
        civil_status_category="NOT_SPECIFIED",
    )
    StudentSupportProfile.objects.create(
        inventory=historical,
        four_ps_status=FourPsStatus.BENEFICIARY,
        indigenous_peoples_status=IndigenousPeoplesStatus.NOT_SPECIFIED,
        mother_life_status=ParentLifeStatus.NOT_SPECIFIED,
        father_life_status=ParentLifeStatus.NOT_SPECIFIED,
    )
    missing_appointment = make_appointment(
        student=missing_student,
        counselor=world["b"],
        service=world["service"],
        starts_at=now + timedelta(hours=4),
    )
    missing_access = resolve_counseling_context(
        actor=world["b"],
        anchor_type="APPOINTMENT",
        anchor_id=missing_appointment.pk,
        now=now,
    )
    missing_context = get_context_support_indicators(missing_access)
    assert missing_context.inventory_status == "MISSING"
    assert missing_context.available is False
    assert missing_context.indicators == ()
    assert historical.submitted_at is not None


@pytest.mark.django_db
def test_context_history_is_minimized_and_private_encounters_stay_hidden(world):
    now = timezone.now().replace(microsecond=0)
    appointment = make_appointment(
        student=world["anna"],
        counselor=world["b"],
        service=world["service"],
        starts_at=now + timedelta(hours=2),
    )
    access = resolve_counseling_context(
        actor=world["b"],
        anchor_type="APPOINTMENT",
        anchor_id=appointment.pk,
        now=now,
    )

    private_encounter = CounselingEncounter.objects.create(
        student=world["anna"],
        counselor=world["a"],
        service=world["service"],
        appointment=None,
        entry_mode="WALK_IN",
        delivery_mode="IN_PERSON",
        started_at=now - timedelta(days=3, hours=1),
        ended_at=now - timedelta(days=3),
        created_by=world["a"],
    )
    with pytest.raises(CounselingNotFound):
        get_encounter_for_actor(encounter_id=private_encounter.pk, actor=world["b"])

    history = list_context_history(access, limit=10)
    assert private_encounter.pk not in {item.id for item in history}
    assert all(not hasattr(item, "reason") for item in history)
    assert all(not hasattr(item, "intake") for item in history)
    assert all(not hasattr(item, "evaluation") for item in history)


@pytest.mark.django_db
def test_context_shared_summaries_are_published_only(world):
    now = timezone.now().replace(microsecond=0)
    appointment = make_appointment(
        student=world["anna"],
        counselor=world["b"],
        service=world["service"],
        starts_at=now + timedelta(hours=2),
    )
    access = resolve_counseling_context(
        actor=world["b"],
        anchor_type="APPOINTMENT",
        anchor_id=appointment.pk,
        now=now,
    )

    published_encounter = CounselingEncounter.objects.create(
        student=world["anna"],
        counselor=world["a"],
        service=world["service"],
        appointment=None,
        entry_mode="WALK_IN",
        delivery_mode="IN_PERSON",
        started_at=now - timedelta(days=5, hours=1),
        ended_at=now - timedelta(days=5),
        created_by=world["a"],
    )
    draft_encounter = CounselingEncounter.objects.create(
        student=world["anna"],
        counselor=world["a"],
        service=world["service"],
        appointment=None,
        entry_mode="REFERRED",
        delivery_mode="IN_PERSON",
        started_at=now - timedelta(days=4, hours=1),
        ended_at=now - timedelta(days=4),
        created_by=world["a"],
    )
    published = CounselingSharedSummary.objects.create(
        encounter=published_encounter,
        content="Published context-safe summary.",
        published_at=now - timedelta(days=4),
    )
    CounselingSharedSummary.objects.create(
        encounter=draft_encounter,
        content="UNPUBLISHED-PRIVATE-SENTINEL",
        published_at=None,
    )

    summaries = list_context_shared_summaries(access)
    assert [item.id for item in summaries] == [published.pk]
    assert "UNPUBLISHED-PRIVATE-SENTINEL" not in " ".join(item.content for item in summaries)


@pytest.mark.django_db
def test_context_api_privacy_denials_and_draft_intake_never_leak(world):
    item = create_direct(
        counselor=world["b"],
        student_id=world["anna"].pk,
        entry_mode="REFERRED",
        delivery_mode="IN_PERSON",
        idempotency_key="context-api-direct",
        request_fingerprint="e" * 64,
        context=audit_context(world["b"]),
    )
    replace_my_intake(
        student=world["anna"],
        routine_interview_id=item.pk,
        values={"concerns_explanation": "PRIVATE-INTAKE-BODY-SENTINEL"},
    )

    b_client = auth_client(world["b"])
    closed = b_client.get(f"/api/v1/counseling/context/ROUTINE_INTERVIEW/{item.pk}")
    assert closed.status_code == 404
    assert "PRIVATE-INTAKE-BODY-SENTINEL" not in closed.content.decode()

    submitted = submit_my_intake(
        student=world["anna"],
        routine_interview_id=item.pk,
        context=audit_context(world["anna"]),
    )
    assert submitted.intake_submitted_at is not None

    opened = b_client.get(f"/api/v1/counseling/context/ROUTINE_INTERVIEW/{item.pk}")
    assert opened.status_code == 200
    assert "PRIVATE-INTAKE-BODY-SENTINEL" not in opened.content.decode()
    assert opened.json()["student"]["id"] == str(world["anna"].pk)

    for actor in (world["a"], world["head"], world["unrelated"]):
        response = auth_client(actor).get(f"/api/v1/counseling/context/ROUTINE_INTERVIEW/{item.pk}")
        assert response.status_code == 404
        assert str(world["anna"].pk) not in response.content.decode()

    gss_response = auth_client(world["gss"]).get(
        f"/api/v1/counseling/context/ROUTINE_INTERVIEW/{item.pk}"
    )
    assert gss_response.status_code == 403


@pytest.mark.django_db
def test_context_does_not_persist_support_indicator_snapshots(world):
    now = timezone.now().replace(microsecond=0)
    appointment = make_appointment(
        student=world["anna"],
        counselor=world["b"],
        service=world["service"],
        starts_at=now + timedelta(hours=2),
    )
    access = resolve_counseling_context(
        actor=world["b"],
        anchor_type="APPOINTMENT",
        anchor_id=appointment.pk,
        now=now,
    )
    assert get_context_support_indicators(access).indicators

    encounter_fields = {field.name for field in CounselingEncounter._meta.get_fields()}
    assert "support_indicators" not in encounter_fields
    assert "student_support_profile" not in encounter_fields
    assert "four_ps_status" not in encounter_fields
    assert "pwd_status" not in encounter_fields


@pytest.mark.django_db
def test_detail_responses_project_counseling_context_availability(world):
    now = timezone.now().replace(microsecond=0)
    soon = make_appointment(
        student=world["anna"],
        counselor=world["b"],
        service=world["service"],
        starts_at=now + timedelta(hours=2),
    )
    later = make_appointment(
        student=world["anna"],
        counselor=world["b"],
        service=world["service"],
        starts_at=now + timedelta(days=3),
    )

    provider = auth_client(world["b"])
    detail = provider.get(f"/api/v1/appointments/{soon.pk}")
    assert detail.status_code == 200
    assert detail.json()["counseling_context_available"] is True
    assert (
        provider.get(f"/api/v1/appointments/{later.pk}").json()["counseling_context_available"]
        is False
    )
    student_view = auth_client(world["anna"]).get(f"/api/v1/appointments/{soon.pk}")
    assert student_view.status_code == 200
    assert student_view.json()["counseling_context_available"] is False

    item = create_direct(
        counselor=world["b"],
        student_id=world["anna"].pk,
        entry_mode="WALK_IN",
        delivery_mode="IN_PERSON",
        idempotency_key="context-availability-key",
        request_fingerprint="b" * 64,
        context=audit_context(world["b"]),
    )
    draft = provider.get(f"/api/v1/routine-interviews/{item.pk}")
    assert draft.status_code == 200
    assert draft.json()["counseling_context_available"] is False

    replace_my_intake(
        student=world["anna"],
        routine_interview_id=item.pk,
        values={"coping_with_college_challenges": "Managing deadlines."},
    )
    submit_my_intake(
        student=world["anna"],
        routine_interview_id=item.pk,
        context=audit_context(world["anna"]),
    )
    submitted = provider.get(f"/api/v1/routine-interviews/{item.pk}")
    assert submitted.json()["counseling_context_available"] is True
