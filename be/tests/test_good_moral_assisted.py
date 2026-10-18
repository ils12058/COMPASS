"""Synthetic assisted creation: authoritative sources, provenance, delivery and isolation."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from threading import Barrier, Event
from unittest.mock import Mock
from uuid import uuid4

import pytest
from django.db import close_old_connections, connection, transaction
from django.utils import timezone

from compass.accounts.models import Designation, Role, User, UserDesignation
from compass.accounts.services import set_user_capability_override
from compass.activity.projections import get_my_activity, get_security_activity
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.common.institutional_time import institution_today
from compass.exit_interviews.confidential_content import write_opportunity_note
from compass.exit_interviews.models import ExitInterviewOpportunity
from compass.good_moral import services
from compass.good_moral.models import GoodMoralRequest, GoodMoralVariant
from compass.notifications.delivery import deliver_email_delivery, render_notification_email
from compass.notifications.models import EmailDelivery, Notification, NotificationPreference
from compass.notifications.policy import NotificationEvent, get_event_definition
from compass.organization.models import Program
from tests.test_good_moral import (
    auth_client,
    good_moral_create_headers,
    make_academic_year,
    make_affiliation,
    make_inventory,
    sync_policy,
)

pytestmark = pytest.mark.django_db
CURRENT = {"year_level": "4th Year", "semester": "First Semester"}
GRADUATE = {"degree": "Bachelor of Science", "major": "Computing", "graduation_date": "2020-06-01"}
EVENT = NotificationEvent.GOOD_MORAL_REQUEST_INITIATED


@pytest.fixture(autouse=True)
def synthetic_delivery(monkeypatch):
    monkeypatch.setattr("compass.notifications.tasks.deliver_notification_email.delay", Mock())


@pytest.fixture
def world():
    sync_policy()
    roles = {
        "staff": "COUNSELOR",
        "gss": "GUIDANCE_SERVICES_STAFF",
        "student": "STUDENT",
        "graduate": "STUDENT",
        "other": "STUDENT",
        "unrelated": "COUNSELOR",
        "it": "IT_ADMIN",
        "dpo": "INSTITUTIONAL_OFFICER",
    }
    people = {
        key: User.objects.create_user(
            email=f"assist-{key}@example.test",
            password=None,
            role=Role.objects.get(code=role),
            first_name=key.title(),
            last_name="Synthetic",
            institutional_id=f"ASSIST-{key.upper()}",
        )
        for key, role in roles.items()
    }
    people["graduate"].student_lifecycle_status = "GRADUATED"
    people["graduate"].save(update_fields=["student_lifecycle_status"])
    UserDesignation.objects.create(
        user=people["dpo"], designation=Designation.objects.get(code="DPO")
    )
    year = make_academic_year()
    make_affiliation(people["student"])
    people["inventory"] = make_inventory(people["student"], year)
    people["year"] = year
    return people


def post(actor, student, *, variant="current-student", payload=None, key=None):
    client = auth_client(actor)
    return client.post(
        f"/api/v1/good-moral/requests/{variant}",
        data=json.dumps(
            {"student_id": str(student.pk), **(payload if payload is not None else CURRENT)}
        ),
        content_type="application/json",
        **good_moral_create_headers(client, key),
    )


def create(
    world,
    *,
    actor="staff",
    student="student",
    key="assist-test",
    variant="CURRENT_STUDENT",
    details=None,
    fingerprint="0" * 64,
):
    return services.create_assisted_request(
        actor=world[actor],
        student_id=world[student].pk,
        variant=variant,
        details=CURRENT if details is None else details,
        idempotency_key=key,
        request_fingerprint=fingerprint,
        context=AuditContext.user(world[actor]),
    )


@pytest.mark.parametrize("actor", ["staff", "gss"])
def test_operational_creation_and_student_ownership(world, actor):
    response = post(world[actor], world["student"])
    assert response.status_code == 201, response.content
    data = response.json()
    item = GoodMoralRequest.objects.get(pk=data["id"])
    assert item.student == world["student"]
    assert item.initiated_by == world[actor]
    assert item.initiation_origin == "GCO_ASSISTED"
    assert data["status"] == "REQUESTED" and data["prepared_at"] is None
    assert data["issued_at"] is None and data["form_revision"] is None
    assert data["initiated_by"]["id"] == str(world[actor].pk)
    assert not data["actions"]["can_issue"]
    event = AuditEvent.objects.get(action="good_moral.request_created", target_id=str(item.pk))
    assert event.actor_user == world[actor]
    assert set(event.metadata) == {"variant", "transition", "initiation_origin"}
    client = auth_client(world["student"])
    detail = client.get(f"/api/v1/good-moral/me/{item.pk}")
    assert detail.status_code == 200
    assert "initiated_by" not in detail.json()  # office provenance only, no staff identity
    assert detail.json()["initiation_origin"] == "GCO_ASSISTED"
    assert client.get("/api/v1/good-moral/me").json()["items"][0]["id"] == str(item.pk)
    assert auth_client(world["other"]).get(f"/api/v1/good-moral/me/{item.pk}").status_code == 404


@pytest.mark.parametrize("actor", ["student", "graduate", "it", "dpo"])
@pytest.mark.parametrize("override", [False, True])
def test_non_operational_roles_cannot_initiate_even_with_override(world, actor, override):
    if override:
        for capability in ("good_moral.view", "good_moral.initiate"):
            set_user_capability_override(
                user=world[actor], capability=capability, effect="GRANT", reason="Synthetic test"
            )
    response = post(world[actor], world["student"])
    assert response.status_code == 403
    assert auth_client(world[actor]).get("/api/v1/good-moral/student-options").status_code == 403
    assert not GoodMoralRequest.objects.exists()


@pytest.mark.parametrize("capability", ["good_moral.initiate", "good_moral.view"])
def test_capability_and_dependency_revocation(world, capability):
    set_user_capability_override(
        user=world["staff"], capability=capability, effect="REVOKE", reason="Synthetic revoke"
    )
    assert post(world["staff"], world["student"]).status_code == 403
    with pytest.raises(services.GoodMoralNotPermitted):
        create(world)


def test_inactive_actor_rejected(world):
    client = auth_client(world["staff"])
    headers = good_moral_create_headers(client)
    world["staff"].is_active = False
    world["staff"].save(update_fields=["is_active"])
    with pytest.raises(services.GoodMoralNotPermitted):
        create(world)
    response = client.post(
        "/api/v1/good-moral/requests/current-student",
        data=json.dumps({"student_id": str(world["student"].pk), **CURRENT}),
        content_type="application/json",
        **headers,
    )
    assert response.status_code in {401, 403}


def test_graduate_creation_and_current_lifecycle_claim(world):
    response = post(world["gss"], world["graduate"], variant="graduate", payload=GRADUATE)
    assert response.status_code == 201, response.content
    data = response.json()
    assert data["degree"] == GRADUATE["degree"]
    assert data["inventory_id"] is None and data["graduation_date"] == "2020-06-01"
    current_claim = post(world["staff"], world["student"], variant="graduate", payload=GRADUATE)
    assert current_claim.status_code == 201, current_claim.content
    assert current_claim.json()["degree"] == GRADUATE["degree"]


def test_assisted_f6_is_available_for_a_current_student_reenrolled_in_local_postgraduate_program(
    world,
):
    mit, _ = Program.objects.get_or_create(
        college=world["inventory"].program.college,
        code="MIT",
        defaults={"name": "Master in Information Technology"},
    )
    world["inventory"].program = mit
    world["inventory"].year_level = None
    world["inventory"].save(update_fields=["program", "year_level", "updated_at"])

    options = auth_client(world["staff"]).get("/api/v1/good-moral/student-options")
    assert options.status_code == 200
    current = next(
        item for item in options.json()["items"] if item["id"] == str(world["student"].pk)
    )
    assert current["f4_eligibility"]["status"] == "POSTGRADUATE_PROGRAM"
    assert set(current["f4_eligibility"]) == {"status", "academic_classification", "year_level"}

    f4 = post(world["staff"], world["student"])
    assert f4.status_code == 409
    assert f4.json()["error"]["code"] == "good_moral_f4_academic_eligibility_required"

    f6 = post(world["gss"], world["student"], variant="graduate", payload=GRADUATE)
    assert f6.status_code == 201
    item = GoodMoralRequest.objects.get(pk=f6.json()["id"])
    assert item.variant == GoodMoralVariant.GRADUATE
    assert item.status == "REQUESTED"
    assert item.inventory_id is None
    assert item.degree_snapshot == GRADUATE["degree"]


@pytest.mark.parametrize("state", ["inactive", "former", "graduate", "not_student"])
def test_target_source_eligibility(world, state):
    student = world["student"]
    if state == "inactive":
        student.is_active = False
    elif state == "not_student":
        student.role = world["it"].role
        student.student_lifecycle_status = None
    else:
        student.student_lifecycle_status = "FORMER" if state == "former" else "GRADUATED"
    student.save()
    assert post(world["staff"], student).status_code in {404, 409}
    assert not Notification.objects.filter(event_code=EVENT).exists()


@pytest.mark.parametrize("case", ["inventory", "college", "exit_interview"])
def test_prerequisites_cannot_be_overridden(world, case):
    if case == "inventory":
        world["inventory"].submitted_at = None
        world["inventory"].save(update_fields=["submitted_at"])
    elif case == "college":
        college = world["student"].organization_student_affiliation.college
        college.is_active = False
        college.save(update_fields=["is_active"])
    else:
        opportunity = ExitInterviewOpportunity(
            student=world["student"],
            academic_year=world["year"],
            source="GRADUATION",
            opened_by=world["staff"],
            opened_at=timezone.now(),
        )
        write_opportunity_note(opportunity, "Synthetic private note")
        opportunity.save()
    response = post(world["staff"], world["student"])
    assert response.status_code == 409
    expected = {
        "inventory": "good_moral_inventory_required",
        "college": "good_moral_affiliation_required",
        "exit_interview": "good_moral_exit_interview_required",
    }[case]
    assert response.json()["error"]["code"] == expected
    assert not GoodMoralRequest.objects.exists()
    assert not Notification.objects.filter(event_code=EVENT).exists()


@pytest.mark.parametrize(
    "payload", [{**CURRENT, "year_level": "Eleventh"}, {**CURRENT, "semester": "Summer"}]
)
def test_canonical_current_inputs(world, payload):
    assert post(world["staff"], world["student"], payload=payload).status_code == 422


def test_future_graduation_and_unknown_student(world):
    payload = {**GRADUATE, "graduation_date": str(institution_today() + timedelta(days=1))}
    assert (
        post(world["staff"], world["graduate"], variant="graduate", payload=payload).status_code
        == 422
    )
    assert post(world["staff"], Mock(pk=uuid4())).status_code == 404


@pytest.mark.parametrize(
    "field,value",
    [
        ("initiated_by", str(uuid4())),
        ("status", "ISSUED"),
        ("issued_by", str(uuid4())),
        ("trusted_eligible", True),
    ],
)
def test_strict_payload_rejects_server_owned_fields(world, field, value):
    assert (
        post(world["staff"], world["student"], payload={**CURRENT, field: value}).status_code == 422
    )
    assert not GoodMoralRequest.objects.exists()


def test_idempotency_replay_payload_target_variant_and_actor_binding(world):
    item = create(world)
    assert create(world).pk == item.pk
    for kwargs in (
        {"details": {**CURRENT, "year_level": "3rd Year"}},
        {"student": "other"},
        {"variant": "GRADUATE", "details": {**GRADUATE, "graduation_date": date(2020, 6, 1)}},
    ):
        with pytest.raises(services.GoodMoralCreationConflict):
            create(world, **kwargs)
    with pytest.raises(services.GoodMoralConflict, match="pending"):
        create(world, actor="gss")  # a second actor cannot reuse this pending request
    with pytest.raises(services.GoodMoralConflict, match="pending"):
        create(world, key="different")
    assert GoodMoralRequest.objects.count() == 1
    assert Notification.objects.filter(event_code=EVENT).count() == 1
    assert AuditEvent.objects.filter(action="good_moral.request_created").count() == 1


def test_assisted_duplicate_against_existing_self_service_and_future_request(world):
    student = world["student"]
    kwargs = dict(
        student=student,
        **CURRENT,
        context=AuditContext.user(student),
        idempotency_key="self",
        request_fingerprint="1" * 64,
    )
    existing = services.create_my_current_student(**kwargs)
    with pytest.raises(services.GoodMoralConflict, match="pending"):
        create(world)
    services.cancel_request(
        actor=student,
        request_id=existing.pk,
        reason="Synthetic cancellation",
        self_service=True,
        context=AuditContext.user(student),
    )
    item = create(world)
    assert item.pk != existing.pk
    assert existing.initiated_by_id == student.pk and existing.initiation_origin == "STUDENT_SELF"
    assert Notification.objects.filter(event_code=EVENT).count() == 1


@pytest.mark.parametrize("transition", ["prepare", "issue", "cancel", "correct"])
def test_provenance_survives_existing_workflows(world, transition):
    item = create(world)
    if transition in {"prepare", "issue"}:
        services.prepare_request(
            actor=world["gss"], request_id=item.pk, context=AuditContext.user(world["gss"])
        )
    if transition == "issue":
        with pytest.raises(services.GoodMoralNotPermitted):
            services.issue_request(
                actor=world["gss"], request_id=item.pk, context=AuditContext.user(world["gss"])
            )
        services.issue_request(
            actor=world["staff"], request_id=item.pk, context=AuditContext.user(world["staff"])
        )
        assert Notification.objects.filter(
            event_code="good_moral.issued", source_id=item.pk
        ).exists()
    elif transition == "cancel":
        services.cancel_request(
            actor=world["student"],
            request_id=item.pk,
            reason="Synthetic reason",
            self_service=True,
            context=AuditContext.user(world["student"]),
        )
    elif transition == "correct":
        services.update_request(
            actor=world["gss"],
            request_id=item.pk,
            changes={"semester_snapshot": "Second Semester"},
            context=AuditContext.user(world["gss"]),
        )
    item.refresh_from_db()
    assert item.initiated_by == world["staff"] and item.initiation_origin == "GCO_ASSISTED"


def test_notification_mandatory_safe_unique_and_transactional(
    world, django_capture_on_commit_callbacks, monkeypatch
):
    NotificationPreference.objects.create(user=world["student"], optional_email_enabled=False)
    kick = Mock(side_effect=RuntimeError("Synthetic broker unavailable"))
    monkeypatch.setattr("compass.notifications.tasks.deliver_notification_email.delay", kick)
    with django_capture_on_commit_callbacks(execute=True):
        item = create(world)
    notification = Notification.objects.get(event_code=EVENT)
    delivery = EmailDelivery.objects.get(notification=notification)
    assert notification.recipient == world["student"]
    assert notification.policy == "MANDATORY_OPERATIONAL"
    assert notification.target_type == "GOOD_MORAL" and notification.target_id == item.pk
    assert delivery.status == "PENDING" and delivery.sent_at is None
    assert kick.call_count == 1
    assert create(world).pk == item.pk
    assert EmailDelivery.objects.filter(notification=notification).count() == 1
    definition = get_event_definition(EVENT)
    assert definition.channels == {"IN_APP", "EMAIL"}
    mail = render_notification_email(EVENT)
    assert "Sign in to review the request status" in mail.text_body and "<p>" in mail.html_body
    for text in [notification.title, notification.message, mail.text_body, mail.html_body]:
        for private in [
            str(item.pk),
            str(world["student"].pk),
            "ASSIST-STUDENT",
            "assist-student@",
            "Inventory",
            "Exit Interview",
            "official_receipt",
            "Synthetic private",
        ]:
            assert private not in text


def test_notification_failure_rolls_back_creation_and_audit(world, monkeypatch):
    real = services.create_notification_for_event

    def fail(**kwargs):
        real(**kwargs)
        raise RuntimeError("Synthetic intent failure")

    monkeypatch.setattr(services, "create_notification_for_event", fail)
    with pytest.raises(RuntimeError):
        create(world)
    assert not GoodMoralRequest.objects.exists()
    assert not Notification.objects.filter(event_code=EVENT).exists()
    assert not AuditEvent.objects.filter(action="good_moral.request_created").exists()


def test_email_retry_uses_durable_delivery_without_creating_a_request(world, monkeypatch):
    item = create(world)
    delivery = EmailDelivery.objects.get(notification__source_id=item.pk)
    mailer = Mock()
    mailer.send.side_effect = RuntimeError("Synthetic transport unavailable")
    monkeypatch.setattr("compass.notifications.delivery.Mailer", lambda: mailer)
    assert deliver_email_delivery(delivery.pk) == "retry_or_failed"
    delivery.refresh_from_db()
    delivery.next_attempt_at = timezone.now() - timedelta(seconds=1)
    delivery.save(update_fields=["next_attempt_at"])
    mailer.send.side_effect = None
    mailer.send.return_value = 1
    assert deliver_email_delivery(delivery.pk) == "SENT"
    assert GoodMoralRequest.objects.count() == 1
    assert Notification.objects.filter(event_code=EVENT).count() == 1


@pytest.mark.parametrize("actor", ["staff", "gss"])
def test_activity_relationships_and_current_authority(world, actor):
    item = create(world, actor=actor)

    def descriptions(user):
        return [row.description for row in get_my_activity(user).items]

    assert (
        "The Guidance and Counseling Office started a Good Moral request for you."
        in descriptions(world["student"])
    )
    assert "You started a Good Moral request for a Student." in descriptions(world[actor])
    for key in ["other", "unrelated", "it", "dpo"]:
        assert not any("Good Moral" in row for row in descriptions(world[key]))
    assert not get_security_activity(world["student"]).items
    assert not get_security_activity(world[actor]).items
    event = AuditEvent.objects.get(action="good_moral.request_created", target_id=str(item.pk))
    assert event.actor_user == world[actor]
    set_user_capability_override(
        user=world["student"],
        capability="good_moral.view_self",
        effect="REVOKE",
        reason="Synthetic revocation",
    )
    assert not any("Good Moral" in row for row in descriptions(world["student"]))


def test_options_bound_minimized_office_wide_and_revalidated(world):
    client = auth_client(world["gss"])
    url = "/api/v1/good-moral/student-options"
    response = client.get(url, {"search": "ASSIST", "page_size": 1})
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1 and data["has_next"]
    assert set(data["items"][0]) == {
        "id",
        "display_name",
        "institutional_id",
        "college",
        "variant",
        "f4_eligibility",
    }
    assert "email" not in response.content.decode()
    assert client.get(url, {"page_size": 51}).status_code == 422
    assert client.get(url, {"page": 0}).status_code == 422
    assert client.get(url, {"search": "x" * 161}).status_code == 422
    data = client.get(url, {"search": "ASSIST-GRADUATE"}).json()
    assert data["items"][0]["variant"] == "GRADUATE"
    # Selecting a valid source never grants lasting eligibility.
    world["graduate"].is_active = False
    world["graduate"].save(update_fields=["is_active"])
    assert not client.get(url, {"search": "ASSIST-GRADUATE"}).json()["items"]
    assert (
        post(world["gss"], world["graduate"], variant="graduate", payload=GRADUATE).status_code
        == 404
    )


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("same_actor", [True, False])
def test_concurrent_creation_uses_student_fence(world, same_actor):
    barrier = Barrier(2)

    def run(actor):
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            try:
                return str(create(world, actor=actor).pk)
            except services.GoodMoralConflict:
                return "pending"
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, ["staff", "staff" if same_actor else "gss"]))
    assert GoodMoralRequest.objects.count() == 1
    assert Notification.objects.filter(event_code=EVENT).count() == 1
    assert AuditEvent.objects.filter(action="good_moral.request_created").count() == 1
    assert results[0] == results[1] if same_actor else "pending" in results


@pytest.mark.django_db(transaction=True)
def test_target_change_committed_while_waiting_for_student_fence(world):
    started = Event()

    def run():
        close_old_connections()
        started.set()
        try:
            return create(world)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic():
            student = User.objects.select_for_update().get(pk=world["student"].pk)
            future = pool.submit(run)
            assert started.wait(timeout=10)
            student.is_active = False
            student.save(update_fields=["is_active"])
        with pytest.raises(services.GoodMoralNotFound):
            future.result(timeout=20)
    assert not GoodMoralRequest.objects.exists()


def test_legacy_defaults_allow_old_writer_insert_and_read(world):
    # Simulate an older backend inserting without either new column.
    legacy = GoodMoralRequest.objects.create(student=world["graduate"], variant="GRADUATE")
    assert legacy.initiation_origin == "LEGACY_UNSPECIFIED" and legacy.initiated_by_id is None
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT column_default FROM information_schema.columns "
            "WHERE table_name = 'good_moral_goodmoralrequest' "
            "AND column_name = 'initiation_origin'"
        )
        assert "LEGACY_UNSPECIFIED" in cursor.fetchone()[0]
    response = auth_client(world["graduate"]).get(f"/api/v1/good-moral/me/{legacy.pk}")
    assert (
        response.status_code == 200 and response.json()["initiation_origin"] == "LEGACY_UNSPECIFIED"
    )


def test_stale_staff_source_and_mismatched_audit_actor_fail_closed(world):
    with pytest.raises(services.GoodMoralNotPermitted):
        services.create_assisted_request(
            actor=world["staff"],
            student_id=world["student"].pk,
            variant=GoodMoralVariant.CURRENT_STUDENT,
            details=CURRENT,
            idempotency_key="source-check",
            request_fingerprint="0" * 64,
            context=AuditContext.user(world["student"]),
        )
    User.objects.filter(pk=world["staff"].pk).update(is_active=False)
    with pytest.raises(services.GoodMoralNotPermitted):
        create(world)
    assert not GoodMoralRequest.objects.exists()
