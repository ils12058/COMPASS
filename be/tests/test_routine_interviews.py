from __future__ import annotations

import json
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.db import IntegrityError
from django.test import Client
from django.utils import timezone

from compass.accounts.models import (
    Designation,
    Role,
    StudentLifecycleStatus,
    User,
    UserDesignation,
)
from compass.appointments.models import Appointment
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.authentication.sessions import create_auth_session
from compass.counseling.models import CounselingEncounter
from compass.counseling.services import create_encounter
from compass.institutional_forms.models import FormFamily, FormRevision
from compass.institutional_forms.services import (
    SUPPORTED_SCHEMA_VERSIONS,
    activate_form_revision,
    register_form_revision,
)
from compass.inventory.services import (
    ensure_current_inventory,
    replace_current_inventory,
    submit_current_inventory,
)
from compass.organization.academic_years import create_academic_year, set_current_academic_year
from compass.organization.models import (
    Campus,
    College,
    CounselorResponsibility,
    Program,
    StudentAffiliation,
)
from compass.routine_interviews.models import RoutineInterview
from compass.routine_interviews.services import (
    InvalidRoutineInterviewInput,
    RoutineInterviewCreationConflict,
    RoutineInterviewCurrentStudentRequired,
    RoutineInterviewEncounterMismatch,
    RoutineInterviewEvaluationFinalized,
    RoutineInterviewIntakeRequired,
    RoutineInterviewIntakeSubmitted,
    RoutineInterviewInventoryRequired,
    create_direct,
    ensure_for_appointment,
    finalize_assigned_evaluation,
    get_mine,
    replace_assigned_evaluation,
    replace_my_intake,
    submit_my_intake,
)
from compass.service_catalog.services import create_service, set_service_active
from tests.inventory_test_helpers import minimum_normalized_inventory_values


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


def auth_client(user: User) -> Client:
    issued = create_auth_session(user, now=timezone.now())
    client = Client()
    client.cookies["compass_session"] = issued.token
    return client


def csrf(client: Client) -> dict[str, str]:
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    return {"HTTP_X_CSRFTOKEN": response.json()["csrf_token"]}


def configure_year(actor: User, label: str = "2026-2027"):
    year = create_academic_year(label=label, context=context(actor))
    return set_current_academic_year(academic_year_id=year.pk, context=context(actor))


def configure_program() -> Program:
    campus = Campus.objects.create(code="MAIN", name="Main Campus")
    college = College.objects.create(campus=campus, code="CCMS", name="CCMS")
    return Program.objects.create(
        college=college,
        code="BSIS",
        name="BS Information Systems",
    )


def create_counseling_service(actor: User, *, modes: list[str] | None = None):
    service = create_service(
        code="COUNSELING",
        name="Counseling",
        appointment_policy="OPTIONAL",
        default_duration_minutes=60,
        cancellation_cutoff_minutes=30,
        delivery_modes=modes or ["IN_PERSON", "ONLINE"],
        provider_roles=["COUNSELOR"],
        context=context(actor),
    )
    return set_service_active(service_id=service.pk, is_active=True, context=context(actor))


def submit_inventory(student: User, actor: User, *, course: str = "BSIS", major: str = ""):
    ensure_current_inventory(student=student, context=context(student))
    program = configure_program()
    replace_current_inventory(
        student=student,
        values={
            **minimum_normalized_inventory_values(program_id=program.pk),
            "full_name_snapshot": student.get_full_name(),
            "course_currently_enrolled": course,
            "major": major,
        },
    )
    return submit_current_inventory(student=student, context=context(actor))


def make_appointment(*, student: User, counselor: User, service, mode: str = "IN_PERSON"):
    start = timezone.now() + timedelta(days=1)
    return Appointment.objects.create(
        reference_code=f"APT-2026-{Appointment.objects.count() + 1:06d}",
        student=student,
        provider=counselor,
        service=service,
        delivery_mode=mode,
        starts_at=start,
        ends_at=start + timedelta(hours=1),
        status="SCHEDULED",
        cancellation_cutoff_minutes=30,
        created_by=student,
    )


def direct_routine(*, counselor: User, student: User, mode: str = "WALK_IN", key: str = "key-1"):
    return create_direct(
        counselor=counselor,
        student_id=student.pk,
        entry_mode=mode,
        delivery_mode="IN_PERSON",
        idempotency_key=key,
        request_fingerprint=("a" if key == "key-1" else "b") * 64,
        context=context(counselor),
    )


@pytest.mark.django_db
def test_routine_form_family_and_capabilities_are_explicit_without_fake_qms_revision():
    sync_policy()
    student = make_user("student@example.edu", "STUDENT")
    counselor = make_user("counselor@example.edu", "COUNSELOR")
    gss = make_user("gss@example.edu", "GUIDANCE_SERVICES_STAFF")
    admin = make_user("admin@example.edu", "IT_ADMIN")
    head = make_user("head@example.edu", "COUNSELOR")
    UserDesignation.objects.create(
        user=head,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )

    family = FormFamily.objects.get(key="routine_interview")
    assert family.title == "Routine Interview Form"
    assert not FormRevision.objects.filter(family=family).exists()
    assert SUPPORTED_SCHEMA_VERSIONS["routine_interview"] == frozenset({1})

    assert student.has_capability("routine_interviews.view_self")
    assert student.has_capability("routine_interviews.manage_self")
    assert counselor.has_capability("routine_interviews.view_assigned")
    assert counselor.has_capability("routine_interviews.manage_assigned")
    assert head.has_capability("routine_interviews.view_assigned")
    assert not gss.has_capability("routine_interviews.view_assigned")
    assert not admin.has_capability("routine_interviews.view_assigned")


@pytest.mark.django_db
def test_inventory_prerequisite_applies_to_appointment_and_direct_creation():
    sync_policy()
    admin = make_user("admin@example.edu", "IT_ADMIN")
    student = make_user("student@example.edu", "STUDENT")
    counselor = make_user("counselor@example.edu", "COUNSELOR")
    configure_year(admin)
    service = create_counseling_service(admin)
    appointment = make_appointment(student=student, counselor=counselor, service=service)

    with pytest.raises(RoutineInterviewInventoryRequired):
        ensure_for_appointment(
            student=student,
            appointment_id=appointment.pk,
            context=context(student),
        )
    with pytest.raises(RoutineInterviewInventoryRequired):
        direct_routine(counselor=counselor, student=student)

    ensure_current_inventory(student=student, context=context(student))
    with pytest.raises(RoutineInterviewInventoryRequired):
        ensure_for_appointment(
            student=student,
            appointment_id=appointment.pk,
            context=context(student),
        )

    program = configure_program()
    replace_current_inventory(
        student=student,
        values=minimum_normalized_inventory_values(program_id=program.pk),
    )
    submit_current_inventory(student=student, context=context(student))
    scheduled = ensure_for_appointment(
        student=student,
        appointment_id=appointment.pk,
        context=context(student),
    )
    direct = direct_routine(counselor=counselor, student=student)
    assert scheduled.inventory.submitted_at is not None
    assert direct.inventory_id == scheduled.inventory_id


@pytest.mark.django_db
def test_appointment_ensure_derives_context_is_stable_and_keeps_bound_inventory_after_year_switch():
    sync_policy()
    admin = make_user("admin@example.edu", "IT_ADMIN")
    student = make_user("student@example.edu", "STUDENT")
    counselor = make_user("counselor@example.edu", "COUNSELOR")
    first_year = configure_year(admin)
    first_inventory = submit_inventory(student, student, course="BSIS", major="Information Systems")
    service = create_counseling_service(admin)
    appointment = make_appointment(
        student=student, counselor=counselor, service=service, mode="ONLINE"
    )

    created = ensure_for_appointment(
        student=student,
        appointment_id=appointment.pk,
        context=context(student),
    )
    repeated = ensure_for_appointment(
        student=student,
        appointment_id=appointment.pk,
        context=context(student),
    )
    assert repeated.pk == created.pk
    assert created.entry_mode == "APPOINTMENT"
    assert created.delivery_mode == "ONLINE"
    assert created.counselor_id == counselor.pk
    assert created.inventory_id == first_inventory.pk
    assert created.inventory.academic_year_id == first_year.pk
    assert created.form_revision is None
    assert AuditEvent.objects.filter(action="routine_interview.created").count() == 1

    second_year = create_academic_year(label="2027-2028", context=context(admin))
    set_current_academic_year(academic_year_id=second_year.pk, context=context(admin))
    after_switch = ensure_for_appointment(
        student=student,
        appointment_id=appointment.pk,
        context=context(student),
    )
    assert after_switch.pk == created.pk
    assert after_switch.inventory_id == first_inventory.pk


@pytest.mark.django_db
@pytest.mark.parametrize("entry_mode", ["WALK_IN", "CALLED_IN", "REFERRED"])
def test_direct_creation_has_no_fake_appointment_and_persistent_idempotency(entry_mode):
    sync_policy()
    admin = make_user("admin@example.edu", "IT_ADMIN")
    student = make_user("student@example.edu", "STUDENT")
    counselor = make_user("counselor@example.edu", "COUNSELOR")
    configure_year(admin)
    inventory = submit_inventory(student, student)
    StudentAffiliation.objects.create(student=student, college=inventory.program.college)
    counselor_campus = Campus.objects.create(code="DIRECT-COUNSELOR", name="Direct Counselor Campus")
    counselor_college = College.objects.create(
        campus=counselor_campus,
        code="DIRECT-COUNSELOR-COL",
        name="Direct Counselor College",
    )
    CounselorResponsibility.objects.create(college=counselor_college, counselor=counselor)
    create_counseling_service(admin)

    first = create_direct(
        counselor=counselor,
        student_id=student.pk,
        entry_mode=entry_mode,
        delivery_mode="IN_PERSON",
        idempotency_key="retry-key",
        request_fingerprint="a" * 64,
        context=context(counselor),
    )
    replay = create_direct(
        counselor=counselor,
        student_id=student.pk,
        entry_mode=entry_mode,
        delivery_mode="IN_PERSON",
        idempotency_key="retry-key",
        request_fingerprint="a" * 64,
        context=context(counselor),
    )
    assert replay.pk == first.pk
    assert first.appointment_id is None
    assert first.entry_mode == entry_mode
    assert RoutineInterview.objects.count() == 1
    assert AuditEvent.objects.filter(action="routine_interview.created").count() == 1

    with pytest.raises(RoutineInterviewCreationConflict, match="different"):
        create_direct(
            counselor=counselor,
            student_id=student.pk,
            entry_mode=entry_mode,
            delivery_mode="IN_PERSON",
            idempotency_key="retry-key",
            request_fingerprint="b" * 64,
            context=context(counselor),
        )


@pytest.mark.django_db
def test_direct_creation_integrity_race_recovers_outside_failed_savepoint():
    sync_policy()
    admin = make_user("race-admin@example.edu", "IT_ADMIN")
    student = make_user("race-student@example.edu", "STUDENT")
    counselor = make_user("race-counselor@example.edu", "COUNSELOR")
    configure_year(admin)
    submit_inventory(student, student)
    create_counseling_service(admin)

    with patch(
        "compass.routine_interviews.services.RoutineInterview.objects.create",
        side_effect=IntegrityError("simulated unique race"),
    ):
        with pytest.raises(RoutineInterviewCreationConflict, match="retry"):
            create_direct(
                counselor=counselor,
                student_id=student.pk,
                entry_mode="WALK_IN",
                delivery_mode="IN_PERSON",
                idempotency_key="race-key",
                request_fingerprint="c" * 64,
                context=context(counselor),
            )


@pytest.mark.django_db
def test_intake_other_rule_is_submission_only_and_submitted_intake_locks_without_audit_spam():
    sync_policy()
    admin = make_user("admin@example.edu", "IT_ADMIN")
    student = make_user("student@example.edu", "STUDENT")
    counselor = make_user("counselor@example.edu", "COUNSELOR")
    configure_year(admin)
    submit_inventory(student, student)
    create_counseling_service(admin)
    item = direct_routine(counselor=counselor, student=student)

    draft = replace_my_intake(
        student=student,
        routine_interview_id=item.pk,
        values={"concerns": ["OTHER"], "other_concern_specification": ""},
    )
    assert draft.other_concern_specification == ""
    assert not AuditEvent.objects.filter(action="routine_interview.intake_submitted").exists()
    with pytest.raises(InvalidRoutineInterviewInput, match="other_concern_specification"):
        submit_my_intake(student=student, routine_interview_id=item.pk, context=context(student))

    cleared = replace_my_intake(
        student=student,
        routine_interview_id=item.pk,
        values={
            "concerns": ["ACADEMIC"],
            "other_concern_specification": "stale",
            "academic_goals": "Finish the academic year well.",
        },
    )
    assert cleared.other_concern_specification == ""
    submitted = submit_my_intake(
        student=student,
        routine_interview_id=item.pk,
        context=context(student),
    )
    repeated = submit_my_intake(
        student=student,
        routine_interview_id=item.pk,
        context=context(student),
    )
    assert repeated.pk == submitted.pk
    assert submitted.intake_submitted_at is not None
    assert AuditEvent.objects.filter(action="routine_interview.intake_submitted").count() == 1
    with pytest.raises(RoutineInterviewIntakeSubmitted):
        replace_my_intake(
            student=student,
            routine_interview_id=item.pk,
            values={"academic_goals": "Changed"},
        )


@pytest.mark.django_db
def test_api_keeps_student_draft_private_and_never_returns_counselor_evaluation_to_student():
    sync_policy()
    admin = make_user("admin@example.edu", "IT_ADMIN")
    student = make_user("student@example.edu", "STUDENT")
    counselor = make_user("counselor@example.edu", "COUNSELOR")
    unrelated = make_user("unrelated@example.edu", "COUNSELOR")
    gss = make_user("gss@example.edu", "GUIDANCE_SERVICES_STAFF")
    head = make_user("head@example.edu", "COUNSELOR")
    UserDesignation.objects.create(
        user=head,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )
    configure_year(admin)
    submit_inventory(student, student)
    create_counseling_service(admin)
    item = direct_routine(counselor=counselor, student=student)

    student_client = auth_client(student)
    counselor_client = auth_client(counselor)
    unrelated_client = auth_client(unrelated)
    gss_client = auth_client(gss)
    head_client = auth_client(head)

    student_update = student_client.put(
        f"/api/v1/routine-interviews/me/{item.pk}/intake",
        data=json.dumps(
            {
                "coping_with_college_challenges": "Private draft text",
                "concerns": ["SUICIDAL_THOUGHT_TENDENCY"],
            }
        ),
        content_type="application/json",
        **csrf(student_client),
    )
    assert student_update.status_code == 200

    counselor_draft = counselor_client.get(f"/api/v1/routine-interviews/{item.pk}")
    assert counselor_draft.status_code == 200
    assert counselor_draft.json()["intake_status"] == "DRAFT"
    assert counselor_draft.json()["intake"] is None

    assert unrelated_client.get(f"/api/v1/routine-interviews/{item.pk}").status_code == 404
    assert gss_client.get(f"/api/v1/routine-interviews/{item.pk}").status_code == 403
    assert head_client.get(f"/api/v1/routine-interviews/{item.pk}").status_code == 404

    submitted = student_client.post(
        f"/api/v1/routine-interviews/me/{item.pk}/submit",
        data=json.dumps({}),
        content_type="application/json",
        **csrf(student_client),
    )
    assert submitted.status_code == 200
    counselor_after = counselor_client.get(f"/api/v1/routine-interviews/{item.pk}")
    assert counselor_after.status_code == 200
    assert (
        counselor_after.json()["intake"]["coping_with_college_challenges"] == "Private draft text"
    )

    evaluation = counselor_client.put(
        f"/api/v1/routine-interviews/{item.pk}/evaluation",
        data=json.dumps(
            {
                "academic_adjustment_rating": 10,
                "physical_adjustment_rating": 1,
                "special_concern": "Counselor-only special concern",
                "recommendations": "Counselor-only recommendation",
            }
        ),
        content_type="application/json",
        **csrf(counselor_client),
    )
    assert evaluation.status_code == 200

    student_detail = student_client.get(f"/api/v1/routine-interviews/me/{item.pk}")
    assert student_detail.status_code == 200
    body = student_detail.json()
    assert "evaluation" not in body
    assert "special_concern" not in body
    assert "recommendations" not in body


@pytest.mark.django_db
def test_evaluation_requires_submitted_intake_enforces_rating_range_and_locks_after_finalize():
    sync_policy()
    admin = make_user("admin@example.edu", "IT_ADMIN")
    student = make_user("student@example.edu", "STUDENT")
    counselor = make_user("counselor@example.edu", "COUNSELOR")
    configure_year(admin)
    submit_inventory(student, student)
    service = create_counseling_service(admin)
    item = direct_routine(counselor=counselor, student=student)

    with pytest.raises(RoutineInterviewIntakeRequired):
        replace_assigned_evaluation(
            counselor=counselor,
            routine_interview_id=item.pk,
            values={"academic_adjustment_rating": 5},
        )

    replace_my_intake(
        student=student,
        routine_interview_id=item.pk,
        values={"college_experience": "Submitted response"},
    )
    submit_my_intake(student=student, routine_interview_id=item.pk, context=context(student))
    saved = replace_assigned_evaluation(
        counselor=counselor,
        routine_interview_id=item.pk,
        values={
            "academic_adjustment_rating": 1,
            "emotional_adjustment_rating": 10,
            "other_adjustment": "Optional source textual addition",
        },
    )
    assert saved.academic_adjustment_rating == 1
    assert saved.emotional_adjustment_rating == 10
    with pytest.raises(InvalidRoutineInterviewInput):
        replace_assigned_evaluation(
            counselor=counselor,
            routine_interview_id=item.pk,
            values={"academic_adjustment_rating": 11},
        )

    end = timezone.now() - timedelta(minutes=5)
    encounter = CounselingEncounter.objects.create(
        student=student,
        counselor=counselor,
        service=service,
        appointment=None,
        entry_mode="WALK_IN",
        delivery_mode="IN_PERSON",
        started_at=end - timedelta(minutes=45),
        ended_at=end,
        created_by=counselor,
    )
    final = finalize_assigned_evaluation(
        counselor=counselor,
        routine_interview_id=item.pk,
        encounter_id=encounter.pk,
        context=context(counselor),
    )
    assert final.counseling_encounter_id == encounter.pk
    assert final.evaluation_finalized_at is not None
    assert AuditEvent.objects.filter(action="routine_interview.evaluation_finalized").count() == 1
    with pytest.raises(RoutineInterviewEvaluationFinalized):
        replace_assigned_evaluation(
            counselor=counselor,
            routine_interview_id=item.pk,
            values={"academic_adjustment_rating": 7},
        )


@pytest.mark.django_db
def test_finalization_rejects_direct_entry_mode_mismatch_and_appointment_nonappointment_encounter():
    sync_policy()
    admin = make_user("admin@example.edu", "IT_ADMIN")
    student = make_user("student@example.edu", "STUDENT")
    counselor = make_user("counselor@example.edu", "COUNSELOR")
    configure_year(admin)
    submit_inventory(student, student)
    service = create_counseling_service(admin)

    direct = direct_routine(counselor=counselor, student=student, mode="REFERRED")
    replace_my_intake(
        student=student,
        routine_interview_id=direct.pk,
        values={"family_description": "Submitted family context"},
    )
    submit_my_intake(student=student, routine_interview_id=direct.pk, context=context(student))
    end = timezone.now() - timedelta(minutes=5)
    wrong_direct = CounselingEncounter.objects.create(
        student=student,
        counselor=counselor,
        service=service,
        appointment=None,
        entry_mode="WALK_IN",
        delivery_mode="IN_PERSON",
        started_at=end - timedelta(minutes=30),
        ended_at=end,
        created_by=counselor,
    )
    with pytest.raises(RoutineInterviewEncounterMismatch, match="entry mode"):
        finalize_assigned_evaluation(
            counselor=counselor,
            routine_interview_id=direct.pk,
            encounter_id=wrong_direct.pk,
            context=context(counselor),
        )

    appointment = make_appointment(student=student, counselor=counselor, service=service)
    scheduled = ensure_for_appointment(
        student=student,
        appointment_id=appointment.pk,
        context=context(student),
    )
    replace_my_intake(
        student=student,
        routine_interview_id=scheduled.pk,
        values={"career_goals": "Submitted career goal"},
    )
    submit_my_intake(student=student, routine_interview_id=scheduled.pk, context=context(student))
    CounselingEncounter.objects.create(
        student=student,
        counselor=counselor,
        service=service,
        appointment=appointment,
        entry_mode="WALK_IN",
        delivery_mode="IN_PERSON",
        started_at=end - timedelta(minutes=30),
        ended_at=end,
        created_by=counselor,
    )
    with pytest.raises(RoutineInterviewEncounterMismatch, match="APPOINTMENT Encounter"):
        finalize_assigned_evaluation(
            counselor=counselor,
            routine_interview_id=scheduled.pk,
            encounter_id=None,
            context=context(counselor),
        )


@pytest.mark.django_db
def test_active_compatible_form_revision_is_snapshotted_without_rewriting_existing_routines():
    sync_policy()
    admin = make_user("admin@example.edu", "IT_ADMIN")
    student = make_user("student@example.edu", "STUDENT")
    counselor = make_user("counselor@example.edu", "COUNSELOR")
    configure_year(admin)
    submit_inventory(student, student)
    create_counseling_service(admin)

    family = FormFamily.objects.get(key="routine_interview")
    first_revision = register_form_revision(
        family_key=family.key,
        official_code="TEST-QMS-ROUTINE",
        official_revision="A",
        internal_schema_version=1,
        context=context(admin),
    )
    activate_form_revision(revision_id=first_revision.pk, context=context(admin))
    first = direct_routine(counselor=counselor, student=student, key="key-1")
    assert first.form_revision_id == first_revision.pk

    first_revision.status = "INACTIVE"
    first_revision.save(update_fields=["status", "updated_at"])
    second_revision = FormRevision.objects.create(
        family=family,
        official_code="TEST-QMS-ROUTINE-B",
        official_revision="B",
        internal_schema_version=1,
        status="ACTIVE",
    )
    first.refresh_from_db()
    assert first.form_revision_id == first_revision.pk
    assert second_revision.status == "ACTIVE"


@pytest.mark.django_db
def test_sensitive_intake_and_counselor_text_never_enter_routine_audit_metadata():
    sync_policy()
    admin = make_user("admin@example.edu", "IT_ADMIN")
    student = make_user("student@example.edu", "STUDENT")
    counselor = make_user("counselor@example.edu", "COUNSELOR")
    configure_year(admin)
    submit_inventory(student, student)
    service = create_counseling_service(admin)
    item = direct_routine(counselor=counselor, student=student)
    replace_my_intake(
        student=student,
        routine_interview_id=item.pk,
        values={
            "coping_with_college_challenges": "Highly private response",
            "concerns": ["SUICIDAL_THOUGHT_TENDENCY"],
        },
    )
    submit_my_intake(student=student, routine_interview_id=item.pk, context=context(student))
    replace_assigned_evaluation(
        counselor=counselor,
        routine_interview_id=item.pk,
        values={
            "special_concern": "Highly private counselor concern",
            "recommendations": "Highly private recommendation",
        },
    )
    end = timezone.now() - timedelta(minutes=5)
    encounter = CounselingEncounter.objects.create(
        student=student,
        counselor=counselor,
        service=service,
        appointment=None,
        entry_mode="WALK_IN",
        delivery_mode="IN_PERSON",
        started_at=end - timedelta(minutes=30),
        ended_at=end,
        created_by=counselor,
    )
    finalize_assigned_evaluation(
        counselor=counselor,
        routine_interview_id=item.pk,
        encounter_id=encounter.pk,
        context=context(counselor),
    )

    serialized = json.dumps(
        list(
            AuditEvent.objects.filter(action__startswith="routine_interview.").values_list(
                "metadata", flat=True
            )
        )
    )
    assert "Highly private" not in serialized
    assert "SUICIDAL" not in serialized


@pytest.mark.django_db
def test_counseling_occurrence_remains_recordable_without_inventory_or_routine_interview():
    sync_policy()
    admin = make_user("admin@example.edu", "IT_ADMIN")
    student = make_user("student@example.edu", "STUDENT")
    counselor = make_user("counselor@example.edu", "COUNSELOR")
    create_counseling_service(admin)
    ended_at = timezone.now() - timedelta(minutes=5)
    encounter = create_encounter(
        counselor=counselor,
        student_id=student.pk,
        entry_mode="WALK_IN",
        delivery_mode="IN_PERSON",
        started_at=ended_at - timedelta(minutes=20),
        ended_at=ended_at,
        appointment_id=None,
        context=context(counselor),
    )
    assert encounter.pk is not None
    assert RoutineInterview.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize(
    "status",
    [StudentLifecycleStatus.GRADUATED, StudentLifecycleStatus.FORMER],
)
def test_non_current_student_routine_is_read_only_while_counselor_can_finish_existing(status):
    sync_policy()
    admin = make_user(f"routine-admin-{status.lower()}@example.edu", "IT_ADMIN")
    student = make_user(f"routine-student-{status.lower()}@example.edu", "STUDENT")
    counselor = make_user(f"routine-counselor-{status.lower()}@example.edu", "COUNSELOR")
    configure_year(admin)
    submit_inventory(student, student)
    service = create_counseling_service(admin)
    item = direct_routine(
        counselor=counselor,
        student=student,
        key=f"existing-{status.lower()}",
    )
    replace_my_intake(
        student=student,
        routine_interview_id=item.pk,
        values={"college_experience": "Submitted before lifecycle change."},
    )
    submit_my_intake(
        student=student,
        routine_interview_id=item.pk,
        context=context(student),
    )

    student.student_lifecycle_status = status
    student.save(update_fields=["student_lifecycle_status", "updated_at"])

    assert get_mine(student=student, routine_interview_id=item.pk).pk == item.pk
    with pytest.raises(RoutineInterviewCurrentStudentRequired):
        replace_my_intake(
            student=student,
            routine_interview_id=item.pk,
            values={"college_experience": "Blocked edit"},
        )
    with pytest.raises(RoutineInterviewCurrentStudentRequired):
        submit_my_intake(
            student=student,
            routine_interview_id=item.pk,
            context=context(student),
        )
    with pytest.raises(RoutineInterviewCurrentStudentRequired):
        direct_routine(
            counselor=counselor,
            student=student,
            key=f"new-{status.lower()}",
        )

    appointment = make_appointment(
        student=student,
        counselor=counselor,
        service=service,
    )
    with pytest.raises(RoutineInterviewCurrentStudentRequired):
        ensure_for_appointment(
            student=student,
            appointment_id=appointment.pk,
            context=context(student),
        )

    saved = replace_assigned_evaluation(
        counselor=counselor,
        routine_interview_id=item.pk,
        values={"academic_adjustment_rating": 7},
    )
    assert saved.academic_adjustment_rating == 7

    end = timezone.now() - timedelta(minutes=5)
    encounter = CounselingEncounter.objects.create(
        student=student,
        counselor=counselor,
        service=service,
        appointment=None,
        entry_mode="WALK_IN",
        delivery_mode="IN_PERSON",
        started_at=end - timedelta(minutes=45),
        ended_at=end,
        created_by=counselor,
    )
    finalized = finalize_assigned_evaluation(
        counselor=counselor,
        routine_interview_id=item.pk,
        encounter_id=encounter.pk,
        context=context(counselor),
    )
    assert finalized.evaluation_finalized_at is not None


@pytest.mark.django_db
def test_counselor_routine_queue_is_assigned_paginated_filtered_and_identity_search_only():
    sync_policy()
    admin = make_user("queue-admin@example.edu", "IT_ADMIN")
    student = make_user("queue.student@example.edu", "STUDENT")
    student.institutional_id = "RI-2026-001"
    student.save(update_fields=["institutional_id", "updated_at"])
    counselor = make_user("queue.counselor@example.edu", "COUNSELOR")
    other = make_user("queue.other@example.edu", "COUNSELOR")
    gss = make_user("queue.gss@example.edu", "GUIDANCE_SERVICES_STAFF")
    year = configure_year(admin)
    submit_inventory(student, student)
    create_counseling_service(admin)

    mine = direct_routine(counselor=counselor, student=student, key="queue-mine")
    direct_routine(counselor=other, student=student, key="queue-other")

    client = auth_client(counselor)
    listing = client.get("/api/v1/routine-interviews")
    assert listing.status_code == 200
    assert [row["id"] for row in listing.json()["items"]] == [str(mine.pk)]
    row = listing.json()["items"][0]
    assert "intake" not in row
    assert "evaluation" not in row

    searched = client.get("/api/v1/routine-interviews", {"search": "RI-2026-001"})
    assert searched.status_code == 200
    assert [row["id"] for row in searched.json()["items"]] == [str(mine.pk)]

    filtered = client.get(
        "/api/v1/routine-interviews",
        {
            "academic_year_id": str(year.pk),
            "delivery_mode": "IN_PERSON",
            "intake_status": "DRAFT",
            "evaluation_status": "DRAFT",
            "student_id": str(student.pk),
        },
    )
    assert filtered.status_code == 200
    assert [row["id"] for row in filtered.json()["items"]] == [str(mine.pk)]

    assert (
        client.get(
            "/api/v1/routine-interviews",
            {"page_size": 51},
        ).status_code
        == 422
    )
    assert auth_client(other).get("/api/v1/routine-interviews").status_code == 200
    assert auth_client(gss).get("/api/v1/routine-interviews").status_code == 403
