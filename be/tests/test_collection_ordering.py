"""Collection ordering contract (ADR-090).

Every sortable collection orders in SQL before it pages, ends each ordering in a unique
tie-breaker, defaults by what the filtered population means (a schedule, a queue, history, a
directory, a catalog, or a curated feed), and reports the ordering it applied.
"""

from __future__ import annotations

from datetime import date, timedelta
from enum import StrEnum

import pytest
from django.core.management import call_command
from django.test import Client
from django.utils import timezone

from compass.accounts.models import Role, User
from compass.announcements.models import Announcement
from compass.announcements.services import create_announcement, publish_announcement
from compass.audit.context import AuditContext
from compass.call_slips.models import CallSlip
from compass.common.ordering import parse_ordering
from compass.counseling.models import CounselingEncounter
from compass.counseling.services import CounselingEncounterOrdering, list_my_encounters
from compass.exit_interviews.models import ExitInterview, ExitInterviewStatus
from compass.feedback.models import ClientSatisfactionResponse
from compass.good_moral.models import GoodMoralRequest, GoodMoralStatus, GoodMoralVariant
from compass.good_moral.services import GoodMoralOrdering, InvalidGoodMoralInput, list_requests
from compass.institutional_forms.models import FormRevision
from compass.inventory.models import StudentInventory
from compass.notifications.models import EmailDelivery, EmailDeliveryStatus
from compass.publications import PublicationAudience
from compass.referrals.models import Referral
from compass.resources.models import Resource, ResourceCategory, ResourceKind
from compass.resources.services import create_resource, publish_resource
from compass.routine_interviews.models import RoutineInterview
from compass.routine_interviews.services import RoutineInterviewOrdering, list_assigned
from compass.service_catalog.services import create_service
from tests.test_call_slips import create_for as create_call_slip_for
from tests.test_call_slips import setup_scope as call_slip_scope
from tests.test_exit_interviews import make_exit_interview, make_year
from tests.test_exit_interviews import make_inventory as make_exit_inventory
from tests.test_feedback import auth_client as feedback_client
from tests.test_feedback import post_json as post_feedback
from tests.test_feedback import valid_csm_payload
from tests.test_graduate_tracer_reports import make_response as make_graduate_response
from tests.test_inventory_counselor_review import (
    affiliate,
    configure_year,
    make_org,
    submit_inventory,
)
from tests.test_platform_email_operations import make_delivery
from tests.test_referrals import create_for as create_referral_for
from tests.test_referrals import setup_scope as referral_scope
from tests.test_service_provider_qualification import counseling, record_direct

pytestmark = pytest.mark.django_db


def sync_policy() -> None:
    call_command("sync_identity_policy", verbosity=0)


def person(
    email: str,
    role: str = "STUDENT",
    *,
    first: str = "Test",
    last: str = "User",
    head: bool = False,
    lifecycle: str | None = None,
) -> User:
    user = User.objects.create_user(
        email=email,
        password="a-long-ordering-test-password",
        role=Role.objects.get(code=role),
        first_name=first,
        last_name=last,
    )
    if lifecycle is not None:
        User.objects.filter(pk=user.pk).update(student_lifecycle_status=lifecycle)
        user.refresh_from_db()
    if head:
        from compass.accounts.models import Designation, UserDesignation

        UserDesignation.objects.create(
            user=user, designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR")
        )
    return user


def client_for(user: User, *, recent_mfa: bool = False) -> Client:
    from compass.authentication.sessions import create_auth_session

    now = timezone.now()
    issued = create_auth_session(user, now=now, mfa_verified_at=now if recent_mfa else None)
    client = Client()
    client.cookies["compass_session"] = issued.token
    return client


def context(actor: User) -> AuditContext:
    return AuditContext.user(actor)


def walk(fetch, *, page_size: int = 2) -> list:
    """Collect every row through page_size-sized pages; rows must never repeat across pages."""

    rows: list = []
    page = 1
    while True:
        result = fetch(page=page, page_size=page_size)
        items = list(result["items"] if isinstance(result, dict) else result.items)
        has_next = result["has_next"] if isinstance(result, dict) else result.has_next
        rows.extend(items)
        if not has_next:
            break
        page += 1
    keys = [row["id"] if isinstance(row, dict) else row.pk for row in rows]
    assert len(keys) == len(set(keys)), "a row appeared on two pages"
    return rows


def pks(rows) -> list:
    return [row["id"] if isinstance(row, dict) else str(row.pk) for row in rows]


def as_ids(rows) -> list[str]:
    return [str(row.pk) for row in rows]


# Shared contract ---------------------------------------------------------------------------------


class _Sample(StrEnum):
    FIRST = "FIRST"
    SECOND = "SECOND"


class _SampleError(ValueError):
    pass


def test_parse_ordering_accepts_closed_values_and_names_them_on_rejection():
    assert parse_ordering(None, _Sample, default=_Sample.SECOND, error=_SampleError) == "SECOND"
    assert parse_ordering("FIRST", _Sample, default=_Sample.SECOND, error=_SampleError) == "FIRST"
    assert parse_ordering(_Sample.FIRST, _Sample, default=_Sample.SECOND, error=_SampleError) == (
        _Sample.FIRST
    )
    for invalid in ("first", "created_at", "-id", 1, ""):
        with pytest.raises(_SampleError, match="ordering must be one of FIRST, SECOND"):
            parse_ordering(invalid, _Sample, default=_Sample.SECOND, error=_SampleError)


# Good Moral: queues wait longest first, history is newest first ----------------------------------


def _good_moral(student: User, *, name: str, status: str = GoodMoralStatus.REQUESTED, **times):
    staff = User.objects.filter(email="gm-staff@example.edu").first() or person(
        "gm-staff@example.edu", "GUIDANCE_SERVICES_STAFF"
    )
    values: dict[str, object] = {
        "student": student,
        "variant": GoodMoralVariant.GRADUATE,
        "status": status,
        "applicant_name_snapshot": name,
        "degree_snapshot": "BS Information Systems",
    }
    if status in (GoodMoralStatus.READY_FOR_ISSUANCE, GoodMoralStatus.ISSUED):
        values |= {"prepared_at": times.get("prepared_at", timezone.now()), "prepared_by": staff}
    if status == GoodMoralStatus.ISSUED:
        values |= {
            "form_revision": FormRevision.objects.filter(family__key="good_moral_graduate").first(),
            "issued_at": times["issued_at"],
            "issued_by": staff,
            "issued_by_name_snapshot": "Staff Member",
            "document_template_key": "good_moral_graduate",
            "document_template_version": 1,
        }
    if status == GoodMoralStatus.CANCELLED:
        values |= {"cancelled_at": times["cancelled_at"], "cancellation_reason": "Duplicate"}
    item = GoodMoralRequest.objects.create(**values)
    GoodMoralRequest.objects.filter(pk=item.pk).update(created_at=times["created_at"])
    return item


def test_good_moral_queues_serve_the_longest_waiting_and_history_reads_newest_first():
    sync_policy()
    staff = person("gm-reader@example.edu", "GUIDANCE_SERVICES_STAFF")
    students = [person(f"gm-student-{index}@example.edu") for index in range(6)]
    base = timezone.now() - timedelta(days=30)
    day = timedelta(days=1)

    # Two requests share a request time: the id breaks the tie, and pages never overlap.
    requested = [
        _good_moral(students[0], name="Carla", created_at=base + 3 * day),
        _good_moral(students[1], name="Ana", created_at=base + day),
        _good_moral(students[2], name="Bea", created_at=base + day),
    ]
    # Ready requests wait from preparation, not from the original request.
    ready = [
        _good_moral(
            students[3],
            name="Dina",
            status=GoodMoralStatus.READY_FOR_ISSUANCE,
            created_at=base,
            prepared_at=base + 9 * day,
        ),
        _good_moral(
            students[4],
            name="Ella",
            status=GoodMoralStatus.READY_FOR_ISSUANCE,
            created_at=base + 5 * day,
            prepared_at=base + 6 * day,
        ),
    ]
    issued = _good_moral(
        students[5],
        name="Fe",
        status=GoodMoralStatus.ISSUED,
        created_at=base,
        prepared_at=base + day,
        issued_at=base + 20 * day,
    )

    def fetch(**options):
        return list_requests(actor=staff, **options)

    # The two requests made at the same moment keep one global order by id.
    tied = sorted((requested[1], requested[2]), key=lambda item: item.pk)
    page = fetch(status=GoodMoralStatus.REQUESTED)
    assert page.ordering == GoodMoralOrdering.OLDEST_FIRST
    assert as_ids(page.items) == as_ids([*tied, requested[0]])
    assert pks(walk(lambda **kw: fetch(status=GoodMoralStatus.REQUESTED, **kw))) == as_ids(
        page.items
    )

    newest = fetch(status=GoodMoralStatus.REQUESTED, ordering=GoodMoralOrdering.NEWEST_FIRST)
    assert as_ids(newest.items) == list(reversed(as_ids(page.items)))

    ready_page = fetch(status=GoodMoralStatus.READY_FOR_ISSUANCE)
    assert ready_page.ordering == GoodMoralOrdering.OLDEST_FIRST
    assert as_ids(ready_page.items) == [str(ready[1].pk), str(ready[0].pk)]

    history = fetch(status=GoodMoralStatus.ISSUED)
    assert history.ordering == GoodMoralOrdering.NEWEST_FIRST
    assert as_ids(history.items) == [str(issued.pk)]

    # All statuses read as history, by when each request reached its current status.
    everything = fetch()
    assert everything.ordering == GoodMoralOrdering.NEWEST_FIRST
    assert as_ids(everything.items)[:2] == [str(issued.pk), str(ready[0].pk)]

    by_name = fetch(ordering=GoodMoralOrdering.APPLICANT_ASC)
    assert [item.applicant_name_snapshot for item in by_name.items] == [
        "Ana",
        "Bea",
        "Carla",
        "Dina",
        "Ella",
        "Fe",
    ]
    by_name_desc = fetch(ordering=GoodMoralOrdering.APPLICANT_DESC)
    assert as_ids(by_name_desc.items) == list(reversed(as_ids(by_name.items)))

    # Search narrows; the chosen ordering still applies within the matches.
    searched = fetch(search="a", ordering=GoodMoralOrdering.APPLICANT_ASC)
    assert [item.applicant_name_snapshot for item in searched.items] == [
        "Ana",
        "Bea",
        "Carla",
        "Dina",
        "Ella",
    ]

    with pytest.raises(InvalidGoodMoralInput):
        fetch(ordering="created_at")
    client = client_for(staff)
    api = client.get("/api/v1/good-moral/requests", {"status": "REQUESTED"}).json()
    assert api["ordering"] == "OLDEST_FIRST"
    assert pks(api["items"]) == as_ids(page.items)
    assert client.get("/api/v1/good-moral/requests", {"ordering": "-created_at"}).status_code == 422


# Routine Interviews: pending evaluations are a fair queue -----------------------------------------


def test_routine_pending_evaluations_serve_the_oldest_submitted_intake_first():
    sync_policy()
    from compass.routine_interviews.services import create_direct

    counseling(online=False)
    counselor = person("routine-queue-counselor@example.edu", "COUNSELOR")
    other = person("routine-queue-other@example.edu", "COUNSELOR")
    names = [("Zamora", "Ana"), ("Abad", "Ben"), ("Lim", "Cy"), ("Abad", "Ben")]
    students = [
        person(f"routine-queue-{index}@example.edu", first=first, last=last)
        for index, (last, first) in enumerate(names)
    ]
    routines = [
        create_direct(
            counselor=counselor,
            student_id=student.pk,
            entry_mode="WALK_IN",
            delivery_mode="IN_PERSON",
            idempotency_key=f"routine-queue-{index}",
            request_fingerprint=f"{index:x}" * 64,
            context=context(counselor),
        )
        for index, student in enumerate(students)
    ]
    hidden = create_direct(
        counselor=other,
        student_id=students[0].pk,
        entry_mode="WALK_IN",
        delivery_mode="IN_PERSON",
        idempotency_key="routine-queue-hidden",
        request_fingerprint="e" * 64,
        context=context(other),
    )
    now = timezone.now()
    # Created newest-first, submitted oldest-first: waiting age follows the submission.
    submissions = [now - timedelta(days=1), now - timedelta(days=9), now - timedelta(days=4)]
    for routine, submitted_at in zip(routines, submissions, strict=False):
        RoutineInterview.objects.filter(pk=routine.pk).update(
            intake_submitted_at=submitted_at, created_at=now - timedelta(hours=1)
        )
    RoutineInterview.objects.filter(pk=hidden.pk).update(
        intake_submitted_at=now - timedelta(days=30)
    )

    def fetch(**options):
        return list_assigned(
            counselor=counselor, intake_status="SUBMITTED", evaluation_status="DRAFT", **options
        )

    queue = fetch()
    assert queue.ordering == RoutineInterviewOrdering.OLDEST_WAITING
    assert as_ids(queue.items) == [str(routines[1].pk), str(routines[2].pk), str(routines[0].pk)]
    assert str(hidden.pk) not in as_ids(queue.items)  # Ordering never widens scope.
    assert pks(walk(fetch)) == as_ids(queue.items)

    newest = fetch(ordering=RoutineInterviewOrdering.NEWEST_SUBMITTED)
    assert as_ids(newest.items) == list(reversed(as_ids(queue.items)))

    everyone = list_assigned(counselor=counselor, ordering=RoutineInterviewOrdering.STUDENT_ASC)
    assert [(item.student.last_name, item.student.first_name) for item in everyone.items] == [
        ("Abad", "Ben"),
        ("Abad", "Ben"),
        ("Lim", "Cy"),
        ("Zamora", "Ana"),
    ]
    # Identical names still page deterministically by id.
    assert pks(
        walk(
            lambda **kw: list_assigned(
                counselor=counselor, ordering=RoutineInterviewOrdering.STUDENT_ASC, **kw
            )
        )
    ) == as_ids(everyone.items)

    # Unsubmitted intakes are not waiting for evaluation; they read newest first by default.
    assert list_assigned(counselor=counselor).ordering == RoutineInterviewOrdering.NEWEST_CREATED
    assert (
        list_assigned(counselor=counselor, evaluation_status="FINALIZED").ordering
        == RoutineInterviewOrdering.RECENTLY_FINALIZED
    )

    api = client_for(counselor).get(
        "/api/v1/routine-interviews",
        {"intake_status": "SUBMITTED", "evaluation_status": "DRAFT", "page_size": 1},
    )
    assert api.status_code == 200
    assert api.json()["ordering"] == "OLDEST_WAITING"
    assert pks(api.json()["items"]) == [str(routines[1].pk)]


# Call Slips: active reporting times are a schedule ------------------------------------------------


def test_active_call_slips_follow_the_report_schedule_and_history_reads_latest_first():
    sync_policy()
    counselor, _other_counselor, _gss, student, outside = call_slip_scope()
    start = timezone.now() + timedelta(days=2)
    slips = [
        create_call_slip_for(
            counselor,
            student,
            key=f"call-slip-order-{index}",
            fingerprint=f"{index:x}" * 64,
            report_at=start + timedelta(hours=offset),
        )
        for index, offset in enumerate((5, 1, 3))
    ]
    completed = slips[2]
    CallSlip.objects.filter(pk=completed.pk).update(interview_ended_at=timezone.now())

    def fetch(**options):
        from compass.call_slips.services import list_call_slips

        return list_call_slips(actor=counselor, **options)

    active = fetch(state="ACTIVE")
    assert active.ordering == "EARLIEST_REPORT"
    assert as_ids(active.items) == [str(slips[1].pk), str(slips[0].pk)]
    history = fetch()
    assert history.ordering == "LATEST_REPORT"
    assert as_ids(history.items) == [str(slips[0].pk), str(completed.pk), str(slips[1].pk)]
    assert as_ids(fetch(ordering="EARLIEST_REPORT").items) == list(reversed(as_ids(history.items)))
    assert pks(walk(lambda **kw: fetch(**kw))) == as_ids(history.items)
    assert outside.pk not in {item.student_id for item in history.items}

    response = client_for(counselor).get("/api/v1/call-slips", {"state": "ACTIVE"})
    assert response.json()["ordering"] == "EARLIEST_REPORT"
    assert client_for(counselor).get("/api/v1/call-slips", {"ordering": "x"}).status_code == 422


# Referrals: the referred-on date is the canonical chronology --------------------------------------


def test_referrals_order_by_referred_on_with_entry_time_breaking_ties():
    sync_policy()
    counselor, *_rest, student, _student_b, _none = referral_scope()
    referrals = [
        create_referral_for(counselor, student, key=f"ref-order-{i}", fingerprint=f"{i:x}" * 64)
        for i in range(3)
    ]
    Referral.objects.filter(pk=referrals[0].pk).update(referred_on=date(2026, 1, 5))
    Referral.objects.filter(pk=referrals[1].pk).update(referred_on=date(2026, 3, 5))
    Referral.objects.filter(pk=referrals[2].pk).update(referred_on=date(2026, 3, 5))

    from compass.referrals.services import ReferralOrdering, list_referrals

    newest = list_referrals(actor=counselor)
    assert newest.ordering == ReferralOrdering.NEWEST_REFERRED
    # Same referred_on: the later entry comes first.
    assert as_ids(newest.items) == [
        str(referrals[2].pk),
        str(referrals[1].pk),
        str(referrals[0].pk),
    ]
    oldest = list_referrals(actor=counselor, ordering=ReferralOrdering.OLDEST_REFERRED)
    assert as_ids(oldest.items) == list(reversed(as_ids(newest.items)))
    assert pks(walk(lambda **kw: list_referrals(actor=counselor, **kw))) == as_ids(newest.items)


# Counseling Encounters: history, latest first ----------------------------------------------------


def test_counseling_encounters_read_latest_first_with_name_and_oldest_alternatives():
    sync_policy()
    counseling(online=False)
    counselor = person("encounter-order-counselor@example.edu", "COUNSELOR")
    students = [
        person("encounter-order-a@example.edu", first="Ana", last="Cruz"),
        person("encounter-order-b@example.edu", first="Ben", last="Abad"),
        person("encounter-order-c@example.edu", first="Cy", last="Mora"),
    ]
    encounters = [record_direct(counselor, student) for student in students]
    base = timezone.now() - timedelta(days=10)
    for index, encounter in enumerate(encounters):
        CounselingEncounter.objects.filter(pk=encounter.pk).update(
            started_at=base + timedelta(days=(index * 2) % 3)
        )
    started = {
        item.pk: item.started_at for item in CounselingEncounter.objects.filter(counselor=counselor)
    }

    latest = list_my_encounters(counselor=counselor)
    assert latest.ordering == CounselingEncounterOrdering.LATEST_ENCOUNTER
    assert [started[item.pk] for item in latest.items] == sorted(started.values(), reverse=True)
    oldest = list_my_encounters(
        counselor=counselor, ordering=CounselingEncounterOrdering.OLDEST_ENCOUNTER
    )
    assert as_ids(oldest.items) == list(reversed(as_ids(latest.items)))
    by_student = list_my_encounters(
        counselor=counselor, ordering=CounselingEncounterOrdering.STUDENT_ASC
    )
    assert [item.student.last_name for item in by_student.items] == ["Abad", "Cruz", "Mora"]


# Exit Interviews: submitted chronology for submissions, update chronology otherwise --------------


def test_exit_interviews_order_submissions_by_submission_and_drafts_by_update():
    sync_policy()
    head = person("exit-order-head@example.edu", "COUNSELOR", head=True)
    year = make_year("2097-2098")
    now = timezone.now()
    rows = []
    for index, (status, submitted_days, updated_days) in enumerate(
        [
            (ExitInterviewStatus.SUBMITTED, 8, 1),
            (ExitInterviewStatus.SUBMITTED, 2, 7),
            (ExitInterviewStatus.DRAFT, None, 3),
        ]
    ):
        student = person(f"exit-order-{index}@example.edu", first=f"S{index}", last=f"L{2 - index}")
        inventory = make_exit_inventory(student, year)
        submitted = now - timedelta(days=submitted_days) if submitted_days else None
        item = make_exit_interview(
            student=student,
            academic_year=year,
            inventory=inventory,
            status=status,
            first_submitted_at=submitted,
            last_submitted_at=submitted,
        )
        ExitInterview.objects.filter(pk=item.pk).update(
            updated_at=now - timedelta(days=updated_days)
        )
        rows.append(item)

    from compass.exit_interviews.services import ExitInterviewOrdering, list_for_head

    submitted = list_for_head(actor=head, status=ExitInterviewStatus.SUBMITTED)
    assert submitted.ordering == ExitInterviewOrdering.NEWEST_SUBMITTED
    assert as_ids(submitted.items) == [str(rows[1].pk), str(rows[0].pk)]
    oldest = list_for_head(
        actor=head,
        status=ExitInterviewStatus.SUBMITTED,
        ordering=ExitInterviewOrdering.OLDEST_SUBMITTED,
    )
    assert as_ids(oldest.items) == [str(rows[0].pk), str(rows[1].pk)]
    everything = list_for_head(actor=head)
    assert everything.ordering == ExitInterviewOrdering.RECENTLY_UPDATED
    assert as_ids(everything.items) == [str(rows[0].pk), str(rows[2].pk), str(rows[1].pk)]
    by_student = list_for_head(actor=head, ordering=ExitInterviewOrdering.STUDENT_ASC)
    assert as_ids(by_student.items) == [str(rows[2].pk), str(rows[1].pk), str(rows[0].pk)]


# Graduate Tracer and Feedback: history, newest submitted first -----------------------------------


def test_graduate_tracer_and_csm_responses_read_newest_submitted_first():
    sync_policy()
    head = person("history-order-head@example.edu", "COUNSELOR", head=True)
    now = timezone.now()
    tracer = [
        make_graduate_response(f"tracer-order-{index}@example.edu", submitted_at=now - offset)
        for index, offset in enumerate((timedelta(days=2), timedelta(days=9), timedelta(days=2)))
    ]
    client = client_for(head)
    newest = client.get("/api/v1/graduate-tracer/responses").json()
    assert newest["ordering"] == "NEWEST_SUBMITTED"
    tied = sorted((tracer[0], tracer[2]), key=lambda item: str(item.pk), reverse=True)
    assert pks(newest["items"]) == [str(tied[0].pk), str(tied[1].pk), str(tracer[1].pk)]
    oldest = client.get(
        "/api/v1/graduate-tracer/responses", {"ordering": "OLDEST_SUBMITTED"}
    ).json()
    assert pks(oldest["items"]) == list(reversed(pks(newest["items"])))
    paged = walk(
        lambda **kw: client.get("/api/v1/graduate-tracer/responses", kw).json(), page_size=1
    )
    assert pks(paged) == pks(newest["items"])

    for index in range(3):
        respondent = feedback_client(person(f"csm-order-{index}@example.edu"))
        assert (
            post_feedback(respondent, "/api/v1/feedback/csm", valid_csm_payload()).status_code
            == 201
        )
    csm = list(ClientSatisfactionResponse.objects.order_by("submitted_at", "id"))
    for index, row in enumerate(csm):
        ClientSatisfactionResponse.objects.filter(pk=row.pk).update(
            submitted_at=now - timedelta(days=index)
        )
    listed = client.get("/api/v1/feedback/csm/responses").json()
    assert listed["ordering"] == "NEWEST_SUBMITTED"
    assert pks(listed["items"]) == [str(row.pk) for row in csm]
    reverse = client.get("/api/v1/feedback/csm/responses", {"ordering": "OLDEST_SUBMITTED"})
    assert pks(reverse.json()["items"]) == [str(row.pk) for row in reversed(csm)]
    assert client.get("/api/v1/feedback/csm/responses", {"ordering": "NAME"}).status_code == 422


# Inventory roster: a Student directory ------------------------------------------------------------


def test_inventory_roster_is_a_student_directory_with_recent_submission_alternative():
    sync_policy()
    counselor = person("roster-order-counselor@example.edu", "COUNSELOR")
    configure_year(person("roster-order-admin@example.edu", "IT_ADMIN"))
    _campus, college, program = make_org("ROSTER")
    affiliate(person("roster-order-x@example.edu", first="Zed", last="Abad"), college, counselor)
    students = [
        person("roster-order-a@example.edu", first="Ana", last="Mora"),
        person("roster-order-b@example.edu", first="Ben", last="Abad"),
        person("roster-order-c@example.edu", first="Cy", last="Cruz"),
    ]
    for student in students:
        affiliate(student, college)
    submitted = [submit_inventory(student=student, program=program) for student in students[:2]]
    StudentInventory.objects.filter(pk=submitted[0].pk).update(
        submitted_at=timezone.now() - timedelta(days=1)
    )
    StudentInventory.objects.filter(pk=submitted[1].pk).update(
        submitted_at=timezone.now() - timedelta(days=5)
    )
    client = client_for(counselor)

    roster = client.get("/api/v1/inventory/students").json()
    assert roster["ordering"] == "STUDENT_ASC"
    names = [row["student"]["display_name"] for row in roster["items"]]
    assert names == ["Ben Abad", "Zed Abad", "Cy Cruz", "Ana Mora"]
    reverse = client.get("/api/v1/inventory/students", {"ordering": "STUDENT_DESC"}).json()
    assert [row["student"]["display_name"] for row in reverse["items"]] == list(reversed(names))
    recent = client.get("/api/v1/inventory/students", {"ordering": "RECENTLY_SUBMITTED"}).json()
    assert [row["student"]["display_name"] for row in recent["items"]][:2] == [
        "Ana Mora",
        "Ben Abad",
    ]
    filtered = client.get(
        "/api/v1/inventory/students", {"status": "MISSING", "ordering": "STUDENT_DESC"}
    ).json()
    assert [row["student"]["display_name"] for row in filtered["items"]] == ["Cy Cruz", "Zed Abad"]


# Accounts and Services: directory and catalog ----------------------------------------------------


def test_accounts_are_a_name_directory_and_services_a_code_catalog():
    sync_policy()
    admin = person("directory-admin@example.edu", "IT_ADMIN", first="Zoe", last="Zulueta")
    for index, (first, last) in enumerate(
        [("Ana", "Reyes"), ("Ben", "Abad"), ("Ana", "Reyes"), ("Cy", "Reyes")]
    ):
        person(f"directory-{index}@example.edu", first=first, last=last)
    client = client_for(admin, recent_mfa=True)
    listed = client.get("/api/v1/accounts", {"page_size": 50}).json()
    assert listed["ordering"] == "NAME_ASC"
    names = [(row["last_name"], row["first_name"]) for row in listed["items"]]
    assert names == sorted(names)
    paged = walk(lambda **kw: client.get("/api/v1/accounts", kw).json())
    assert pks(paged) == pks(listed["items"])
    searched = client.get("/api/v1/accounts", {"search": "Reyes"}).json()
    assert [row["first_name"] for row in searched["items"]] == ["Ana", "Ana", "Cy"]
    newest = client.get("/api/v1/accounts", {"ordering": "NEWEST_CREATED", "page_size": 50})
    created = [row["created_at"] for row in newest.json()["items"]]
    assert created == sorted(created, reverse=True)
    assert client.get("/api/v1/accounts", {"ordering": "last_name"}).status_code == 422

    for code, name in (("ZULU", "Alpha support"), ("ALPHA", "Zebra care"), ("MIKE", "Mid help")):
        create_service(code=code, name=name, context=context(admin))
    services = client.get("/api/v1/services", {"include_inactive": "true"}).json()
    assert services["ordering"] == "CODE_ASC"
    codes = [row["code"] for row in services["items"]]
    assert codes == sorted(codes)
    by_name = client.get(
        "/api/v1/services", {"include_inactive": "true", "ordering": "NAME_ASC"}
    ).json()
    assert [row["name"] for row in by_name["items"]] == sorted(
        (row["name"] for row in by_name["items"]), key=str.lower
    )


# Announcements and Resources: curated feeds keep their editorial order ----------------------------


def _published_announcement(admin, title: str, *, pinned: bool, published_at):
    item = create_announcement(
        actor=admin,
        title=title,
        body_markdown="Body",
        audience=PublicationAudience.PUBLIC,
        is_pinned=pinned,
        expires_at=None,
        context=context(admin),
    )
    publish_announcement(actor=admin, announcement_id=item.pk, context=context(admin))
    Announcement.objects.filter(pk=item.pk).update(published_at=published_at)
    return item


def _published_resource(admin, title: str, *, display_order: int, published_at):
    item = create_resource(
        actor=admin,
        title=title,
        body_markdown="Body",
        category=ResourceCategory.GENERAL,
        kind=ResourceKind.ARTICLE,
        audience=PublicationAudience.PUBLIC,
        external_url=None,
        display_order=display_order,
        context=context(admin),
    )
    publish_resource(actor=admin, resource_id=item.pk, context=context(admin))
    Resource.objects.filter(pk=item.pk).update(published_at=published_at)
    return item


def test_curated_feeds_keep_editorial_order_and_offer_explicit_alternatives():
    sync_policy()
    admin = person("feed-staff@example.edu", "GUIDANCE_SERVICES_STAFF")
    now = timezone.now()
    old_pinned = _published_announcement(
        admin, "Beta pinned", pinned=True, published_at=now - timedelta(days=9)
    )
    newest = _published_announcement(
        admin, "alpha latest", pinned=False, published_at=now - timedelta(days=1)
    )
    middle = _published_announcement(
        admin, "Gamma middle", pinned=False, published_at=now - timedelta(days=4)
    )
    public = Client()
    recommended = public.get("/api/v1/public/announcements").json()
    assert recommended["ordering"] == "RECOMMENDED"
    assert pks(recommended["items"]) == [str(old_pinned.pk), str(newest.pk), str(middle.pk)]
    by_date = public.get("/api/v1/public/announcements", {"ordering": "NEWEST"}).json()
    assert pks(by_date["items"]) == [str(newest.pk), str(middle.pk), str(old_pinned.pk)]
    oldest = public.get("/api/v1/public/announcements", {"ordering": "OLDEST"}).json()
    assert pks(oldest["items"]) == list(reversed(pks(by_date["items"])))
    titles = public.get("/api/v1/public/announcements", {"ordering": "TITLE_ASC"}).json()
    assert [row["title"] for row in titles["items"]] == [
        "alpha latest",
        "Beta pinned",
        "Gamma middle",
    ]
    assert public.get("/api/v1/public/announcements", {"ordering": "PINNED"}).status_code == 422

    first = _published_resource(
        admin, "First", display_order=1, published_at=now - timedelta(days=8)
    )
    tie_new = _published_resource(
        admin, "Tie newer", display_order=2, published_at=now - timedelta(days=1)
    )
    tie_old = _published_resource(
        admin, "Tie older", display_order=2, published_at=now - timedelta(days=5)
    )
    library = public.get("/api/v1/public/resources").json()
    assert library["ordering"] == "RECOMMENDED"
    assert pks(library["items"]) == [str(first.pk), str(tie_new.pk), str(tie_old.pk)]
    by_date = public.get("/api/v1/public/resources", {"ordering": "NEWEST"}).json()
    assert pks(by_date["items"]) == [str(tie_new.pk), str(tie_old.pk), str(first.pk)]
    by_title = public.get("/api/v1/public/resources", {"ordering": "TITLE_DESC"}).json()
    assert [row["title"] for row in by_title["items"]] == ["Tie older", "Tie newer", "First"]

    manager = client_for(admin, recent_mfa=True)
    managed = manager.get("/api/v1/resources/management").json()
    assert managed["ordering"] == "RECENTLY_UPDATED"
    curated = manager.get("/api/v1/resources/management", {"ordering": "DISPLAY_ORDER"}).json()
    assert pks(curated["items"]) == pks(library["items"])
    announcements = manager.get(
        "/api/v1/announcements/management", {"ordering": "NEWEST_PUBLISHED"}
    ).json()
    assert announcements["ordering"] == "NEWEST_PUBLISHED"
    assert pks(announcements["items"]) == [str(newest.pk), str(middle.pk), str(old_pinned.pk)]


# Email deliveries: actionable statuses read oldest first ------------------------------------------


def test_email_delivery_work_reads_oldest_first_and_history_newest_first():
    sync_policy()
    admin = person("email-order-admin@example.edu", "IT_ADMIN")
    recipient = person("email-order-recipient@example.edu")
    now = timezone.now()
    pending = [make_delivery(recipient) for _ in range(3)]
    for index, delivery in enumerate(pending):
        EmailDelivery.objects.filter(pk=delivery.pk).update(
            created_at=now - timedelta(hours=(3 - index))
        )
    sent = make_delivery(recipient, status=EmailDeliveryStatus.SENT)
    client = client_for(admin)
    queue = client.get("/api/v1/platform/email-deliveries", {"status": "PENDING"}).json()
    assert queue["ordering"] == "OLDEST"
    assert pks(queue["items"]) == [str(item.pk) for item in pending]
    history = client.get("/api/v1/platform/email-deliveries").json()
    assert history["ordering"] == "NEWEST"
    assert pks(history["items"])[0] == str(sent.pk)
    explicit = client.get(
        "/api/v1/platform/email-deliveries", {"status": "PENDING", "ordering": "NEWEST"}
    ).json()
    assert pks(explicit["items"]) == list(reversed(pks(queue["items"])))
