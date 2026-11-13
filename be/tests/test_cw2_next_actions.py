"""CW-2 task authority, encrypted labels, predecessor and bounded case projections."""

import json
from datetime import timedelta
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from django.utils import timezone

from compass.audit.models import AuditEvent
from compass.counseling.case_models import CounselingCase
from compass.counseling.case_services import get_case
from compass.guidance_followups import services, workspace
from compass.guidance_followups.content import decrypt_text
from compass.guidance_followups.errors import (
    FollowUpConflict,
    FollowUpContentUnavailable,
    FollowUpInvalid,
    FollowUpNotFound,
)
from compass.guidance_followups.models import GuidanceFollowUp
from compass.guidance_followups.recovery import recoverable_queryset
from compass.notifications.models import Notification
from compass.routine_interviews.models import RoutineInterview
from tests.test_appointment_management_scope import auth_client, csrf
from tests.test_counseling import context
from tests.test_counseling_cases import intake, link, record, world

pytestmark = pytest.mark.django_db
FUP = "/api/v1/guidance-followups"
TITLE = "Review the student's agreed support exercise"


@pytest.fixture
def cw2(settings):
    settings.GUIDANCE_FOLLOWUP_ENCRYPTION_KEYS = (Fernet.generate_key().decode(),)
    w = world("cw2")
    w.case = intake(w.a, w.student)
    return w


def create(w, **changes):
    values = {
        "actor": w.a,
        "student_id": w.student.pk,
        "assigned_to_id": w.a.pk,
        "category": "COUNSELING",
        "due_at": timezone.now() + timedelta(days=2),
        "source_kind": None,
        "source_id": None,
        "description": "Protected action instructions",
        "visibility": None,
        "case_id": w.case.pk,
        "title": TITLE,
        "idempotency_key": str(uuid4()),
        "request_fingerprint": "a" * 64,
        "context": context(w.a),
    }
    values.update(changes)
    return services.create_followup(**values)


def write(client, method, path, data):
    return getattr(client, method)(
        path,
        data=json.dumps(data),
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY=str(uuid4()),
        **csrf(client),
    )


def test_case_only_lifecycle_and_http_history_keep_case_and_appointment_lifecycles_separate(cw2):
    w = cw2
    client = auth_client(w.a, recent_mfa=True)
    result = write(
        client,
        "post",
        FUP,
        {
            "student_id": str(w.student.pk),
            "assigned_to_id": str(w.a.pk),
            "category": "COUNSELING",
            "case_id": str(w.case.pk),
            "title": TITLE,
            "due_at": (timezone.now() + timedelta(days=2)).isoformat(),
        },
    )
    assert result.status_code == 201, result.content
    item = result.json()
    assert item["title"] == TITLE and item["source"] is None
    assert item["visibility"] == "COUNSELOR_CONFIDENTIAL"
    assert item["case"]["id"] == str(w.case.pk)
    assert client.get(FUP).json()["items"][0]["title"] == TITLE
    updated = write(
        client,
        "patch",
        f"{FUP}/{item['id']}",
        {
            "expected_version": 1,
            "title": "Check the recorded progress",
        },
    )
    assert updated.status_code == 200, updated.content
    assert updated.json()["title"] == "Check the recorded progress"
    stale = write(
        client,
        "patch",
        f"{FUP}/{item['id']}",
        {
            "expected_version": 1,
            "title": "Never overwrite a newer action",
        },
    )
    assert stale.status_code == 409
    completed = write(
        client,
        "post",
        f"{FUP}/{item['id']}/complete",
        {
            "expected_version": 2,
            "outcome": "Reviewed the recorded exercise",
        },
    )
    assert completed.status_code == 200, completed.content
    assert completed.json()["status"] == "COMPLETED"
    history = client.get(f"{FUP}/{item['id']}/history")
    assert history.status_code == 200
    assert [event["kind"] for event in history.json()["items"]] == [
        "CREATED",
        "UPDATED",
        "COMPLETED",
    ]
    cancelled = create(w)
    response = write(
        client,
        "post",
        f"{FUP}/{cancelled.pk}/cancel",
        {
            "expected_version": 1,
            "reason": "The action is no longer needed",
        },
    )
    assert response.status_code == 200 and response.json()["status"] == "CANCELLED"
    w.case.refresh_from_db()
    assert (w.case.status, w.case.version) == ("ACTIVE", 1)
    assert not w.case.appointment_links.exists()
    assert not w.student.student_appointments.exists()


def test_every_other_audience_and_guessed_ids_are_denied_on_all_task_routes(cw2):
    w = cw2
    item = create(w)
    for actor in (w.b, w.head, w.goa, w.faculty, w.student, w.admin, w.officer):
        client = auth_client(actor, recent_mfa=True)
        listing = client.get(FUP)
        if actor.role.code in ("COUNSELOR", "GUIDANCE_OFFICE_ASSISTANT"):
            assert listing.status_code == 200 and listing.json()["items"] == []
        else:
            assert listing.status_code == 403
        for suffix in ("", "/history"):
            result = client.get(f"{FUP}/{item.pk}{suffix}")
            assert result.status_code in (403, 404), result.content
            assert TITLE not in result.content.decode()
        for method, suffix, data in [
            ("patch", "", {"title": "Forbidden edit"}),
            ("post", "/complete", {"outcome": "Forbidden outcome"}),
            ("post", "/cancel", {"reason": "Forbidden cancellation"}),
        ]:
            result = write(
                client,
                method,
                f"{FUP}/{item.pk}{suffix}",
                {
                    "expected_version": 1,
                    **data,
                },
            )
            assert result.status_code in (403, 404), result.content
    own = auth_client(w.a)
    assert own.get(f"{FUP}/{uuid4()}").status_code == 404
    item.refresh_from_db()
    assert item.version == 1 and item.events.count() == 1


@pytest.mark.parametrize(
    "change,error",
    [
        ({"category": "ADMINISTRATIVE"}, FollowUpInvalid),
        ({"student": "other"}, FollowUpInvalid),
        ({"actor": "b"}, FollowUpNotFound),
        ({"assignee": "b"}, FollowUpInvalid),
        ({"assignee": "head"}, FollowUpInvalid),
        ({"assignee": "goa"}, FollowUpInvalid),
        ({"closed": True}, FollowUpConflict),
        ({"title": "x" * 121}, FollowUpInvalid),
        ({"title": "unsupported\x00text"}, FollowUpInvalid),
    ],
)
def test_creation_validation(cw2, change, error):
    w = cw2
    values = dict(change)
    if "student" in values:
        values["student_id"] = getattr(w, values.pop("student")).pk
    if "actor" in values:
        values["actor"] = getattr(w, values["actor"])
    if "assignee" in values:
        values["assigned_to_id"] = getattr(w, values.pop("assignee")).pk
    closed = values.pop("closed", False)
    if closed:
        CounselingCase.objects.filter(pk=w.case.pk).update(status="CLOSED")
    with pytest.raises(error):
        create(w, **values)
    if closed:
        response = write(
            auth_client(w.a, recent_mfa=True),
            "post",
            FUP,
            {
                "student_id": str(w.student.pk),
                "case_id": str(w.case.pk),
                "category": "COUNSELING",
                "assigned_to_id": str(w.a.pk),
                "due_at": (timezone.now() + timedelta(days=2)).isoformat(),
                "title": "Refused Closed case action",
            },
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "followup_conflict"
    assert not GuidanceFollowUp.objects.exists()


def test_title_has_its_own_envelope_and_never_enters_broad_projections_or_logs(cw2, caplog):
    w = cw2
    item = create(w)
    assert item.title_ciphertext and TITLE not in item.title_ciphertext
    assert decrypt_text(item.pk, "title", item.title_ciphertext) == TITLE
    with pytest.raises(FollowUpContentUnavailable):
        decrypt_text(item.pk, "description", item.title_ciphertext)
    with pytest.raises(FollowUpContentUnavailable):
        decrypt_text(uuid4(), "title", item.title_ciphertext)
    assert Notification.objects.filter(recipient=w.a).exists()
    for payload in (
        list(Notification.objects.values()),
        list(AuditEvent.objects.values("metadata")),
        workspace.reporting(actor=w.a),
        auth_client(w.a).get("/api/v1/work-queue").json(),
    ):
        assert TITLE not in json.dumps(payload, default=str)
    assert TITLE not in caplog.text
    legacy = create(w, title=None)
    response = auth_client(w.a).get(f"{FUP}/{legacy.pk}")
    assert response.status_code == 200 and response.json()["title"] is None
    assert legacy.title_ciphertext is None


@pytest.mark.parametrize("source_kind", ["COUNSELING_ENCOUNTER", "ROUTINE_INTERVIEW"])
def test_case_relationship_never_widens_source_authority_even_after_direct_ownership_drift(
    cw2, source_kind
):
    w = cw2
    source = (
        record(w.a, w.student)
        if source_kind == "COUNSELING_ENCOUNTER"
        else RoutineInterview.objects.create(
            student=w.student,
            counselor=w.a,
            entry_mode="WALK_IN",
            delivery_mode="IN_PERSON",
            student_intake_ciphertext="not read",
            counselor_evaluation_ciphertext="not read",
        )
    )
    task = create(w, source_kind=source_kind, source_id=source.pk)
    CounselingCase.objects.filter(pk=w.case.pk).update(primary_counselor=w.b)
    assert services.get_followup(actor=w.a, followup_id=task.pk).pk == task.pk
    assert auth_client(w.a).get(f"{FUP}/{task.pk}").json()["case"] is None
    assert services.list_followups(actor=w.b).items == ()
    assert get_case(actor=w.b, case_id=w.case.pk).next_actions.items == ()
    with pytest.raises(FollowUpNotFound):
        services.get_followup(actor=w.b, followup_id=task.pk)
    GuidanceFollowUp.objects.filter(pk=task.pk).update(assigned_to=w.b)
    assert services.list_followups(actor=w.b).items == ()
    with pytest.raises(FollowUpNotFound):
        services.get_followup(actor=w.b, followup_id=task.pk)


def test_source_owned_by_another_counselor_cannot_be_used_for_case_task_creation(cw2):
    w = cw2
    other_source = record(w.b, w.student)
    with pytest.raises(FollowUpNotFound):
        create(w, source_kind="COUNSELING_ENCOUNTER", source_id=other_source.pk)


def test_case_only_authority_tracks_primary_counselor_without_delegation_or_recovery(cw2):
    w = cw2
    item = create(w)
    assert workspace.eligible_assignees(
        actor=w.a,
        student_id=w.student.pk,
        category="COUNSELING",
        case_id=w.case.pk,
    ).items == (w.a,)
    CounselingCase.objects.filter(pk=w.case.pk).update(primary_counselor=w.b)
    assert services.list_followups(actor=w.a).items == ()
    assert services.list_followups(actor=w.b).items == ()  # Assignment is not silently transferred.
    assert not recoverable_queryset(actor=w.head).filter(pk=item.pk).exists()
    with pytest.raises(FollowUpNotFound):
        services.reassign_followup(
            actor=w.head,
            followup_id=item.pk,
            expected_version=1,
            assigned_to_id=w.b.pk,
            context=context(w.head),
        )


def test_source_context_offers_only_its_explicit_owned_case(cw2):
    w = cw2
    source = record(w.a, w.student)
    assert (
        workspace.source_context(
            actor=w.a,
            source_kind="COUNSELING_ENCOUNTER",
            source_id=source.pk,
        )["case"]
        is None
    )
    link(w.a, w.case, source)
    assert (
        workspace.source_context(
            actor=w.a,
            source_kind="COUNSELING_ENCOUNTER",
            source_id=source.pk,
        )["case"]["id"]
        == w.case.pk
    )
    unrelated = record(w.a, w.student, hours_ago=8)
    assert (
        workspace.source_context(
            actor=w.a,
            source_kind="COUNSELING_ENCOUNTER",
            source_id=unrelated.pk,
        )["case"]
        is None
    )


def test_predecessor_requires_authority_and_matching_student_and_case_allows_several_successors(
    cw2,
):
    w = cw2
    preceding = create(w)
    first = create(w, predecessor_id=preceding.pk)
    second = create(w, predecessor_id=preceding.pk)
    assert set(preceding.successors.values_list("pk", flat=True)) == {first.pk, second.pk}
    detail = auth_client(w.a).get(f"{FUP}/{first.pk}").json()
    assert detail["predecessor_id"] == str(preceding.pk)
    other_case = intake(w.a, w.student, known=[w.case.pk])
    with pytest.raises(FollowUpInvalid):
        create(w, case_id=other_case.pk, predecessor_id=preceding.pk)
    other_student_case = intake(w.a, w.other)
    with pytest.raises(FollowUpInvalid):
        create(w, case_id=other_student_case.pk, student_id=w.other.pk, predecessor_id=preceding.pk)
    with pytest.raises(FollowUpNotFound):
        create(w, predecessor_id=uuid4())
    inaccessible = create(
        w,
        actor=w.b,
        assigned_to_id=w.b.pk,
        case_id=None,
        source_kind="COUNSELING_ENCOUNTER",
        source_id=record(w.b, w.student).pk,
    )
    with pytest.raises(FollowUpNotFound):
        create(w, predecessor_id=inaccessible.pk)


def test_completion_and_cancellation_require_text_and_never_create_successors(cw2):
    w = cw2
    item = create(w)
    for function, field in (
        (services.complete_followup, "outcome"),
        (services.cancel_followup, "reason"),
    ):
        with pytest.raises(FollowUpInvalid):
            function(
                actor=w.a,
                followup_id=item.pk,
                expected_version=1,
                context=context(w.a),
                **{field: " "},
            )
    assert GuidanceFollowUp.objects.count() == 1 and item.events.count() == 1


def test_next_action_is_earliest_authorized_pending_and_terminal_work_is_recent(cw2):
    w = cw2
    later = create(w, due_at=timezone.now() + timedelta(days=4))
    earliest = create(w, due_at=timezone.now() + timedelta(days=1))
    terminal = create(w)
    services.complete_followup(
        actor=w.a,
        followup_id=terminal.pk,
        expected_version=1,
        outcome="Recorded outcome",
        context=context(w.a),
    )
    hidden = create(
        w,
        actor=w.b,
        assigned_to_id=w.b.pk,
        case_id=None,
        source_kind="COUNSELING_ENCOUNTER",
        source_id=record(w.b, w.student).pk,
    )
    GuidanceFollowUp.objects.filter(pk=hidden.pk).update(case=w.case, assigned_to=w.a)
    response = auth_client(w.a).get(f"/api/v1/counseling/cases/{w.case.pk}")
    assert response.status_code == 200, response.content
    detail = response.json()
    assert detail["next_action"]["id"] == str(earliest.pk)
    assert detail["next_action"]["title"] == TITLE
    assert [item["id"] for item in detail["next_actions"]] == [
        str(earliest.pk),
        str(later.pk),
        str(terminal.pk),
    ]
    assert services.list_followups(actor=w.a, case_id=w.case.pk).items[0].pk == earliest.pk
    with pytest.raises(FollowUpNotFound):
        services.list_followups(actor=w.b, case_id=w.case.pk)


def test_sql_scope_authorizes_a_whole_page_before_offset(cw2):
    w = cw2
    own = create(w)
    other_source = record(w.b, w.student)
    hidden = []
    for number in range(45):
        hidden.append(
            GuidanceFollowUp(
                student=w.student,
                assigned_to=w.a,
                created_by=w.a,
                category="COUNSELING",
                visibility="COUNSELOR_CONFIDENTIAL",
                case=w.case,
                source_kind="COUNSELING_ENCOUNTER",
                source_id=other_source.pk,
                due_at=own.due_at - timedelta(minutes=number + 1),
                creation_key_digest=f"{number:064x}",
                creation_request_fingerprint="b" * 64,
            )
        )
    GuidanceFollowUp.objects.bulk_create(hidden)
    page = services.list_followups(actor=w.a, page_size=1)
    assert [row.pk for row in page.items] == [own.pk]
    assert page.has_next is False
    assert services.list_followups(actor=w.a, page=2, page_size=1).items == ()


def test_title_update_keeps_optimistic_version_check(cw2):
    item = create(cw2)
    services.update_followup(
        actor=cw2.a,
        followup_id=item.pk,
        expected_version=1,
        title="Updated action",
        context=context(cw2.a),
    )
    with pytest.raises(FollowUpConflict):
        services.update_followup(
            actor=cw2.a,
            followup_id=item.pk,
            expected_version=1,
            title="Stale action",
            context=context(cw2.a),
        )
    item.refresh_from_db()
    assert decrypt_text(item.pk, "title", item.title_ciphertext) == "Updated action"
