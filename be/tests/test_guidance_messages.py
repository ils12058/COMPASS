"""Domain/privacy proof on PostgreSQL, using synthetic text only."""

from __future__ import annotations

import json
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import Client
from django.utils import timezone

from compass.accounts.bootstrap import sync_identity_policy
from compass.accounts.models import Capability, Designation, Role, User, UserCapabilityOverride
from compass.accounts.policy import (
    CAPABILITY_DEPENDENCIES,
    DESIGNATION_CAPABILITY_GRANTS,
    ROLE_CAPABILITY_GRANTS,
)
from compass.appointments.models import Appointment
from compass.audit.models import AuditEvent
from compass.confidential_data import crypto
from compass.guidance_messages import content, policy, services
from compass.guidance_messages.errors import (
    GuidanceMessageContentUnavailable,
    InvalidMessageInput,
    MessagesConflict,
    MessagesPermissionDenied,
    ThreadNotFound,
)
from compass.guidance_messages.models import (
    GuidanceMessage,
    GuidanceThread,
    GuidanceThreadReadState,
)
from compass.organization.models import (
    Campus,
    College,
    CounselorResponsibility,
    StaffSupervision,
    StudentAffiliation,
)
from compass.service_catalog.models import Service
from tests.test_notifications import auth_client

pytestmark = pytest.mark.django_db
BASE = "/api/v1/guidance-messages"
BODY = "Synthetic message.\nLine two stays exactly as typed.  "


@pytest.fixture
def world():
    sync_identity_policy()

    def user(name, role="STUDENT"):
        return User.objects.create_user(
            email=f"gm-{name}@example.edu",
            password=None,
            role=Role.objects.get(code=role),
            first_name="Synthetic",
            last_name=name,
        )

    student = user("student")
    other_student = user("other-student")
    counselor = user("counselor", "COUNSELOR")
    other = user("other", "COUNSELOR")
    head = user("head", "COUNSELOR")
    head.designations.add(Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"))
    gss = user("gss", "GUIDANCE_SERVICES_STAFF")
    head_gss = user("head-gss", "GUIDANCE_SERVICES_STAFF")
    admin = user("admin", "IT_ADMIN")
    dpo = user("dpo", "INSTITUTIONAL_OFFICER")
    dpo.designations.add(Designation.objects.get(code="DPO"))
    campus = Campus.objects.create(code="GM", name="Synthetic Campus")
    colleges = [
        College.objects.create(campus=campus, code=f"GM-{i}", name=f"Synthetic College {i}")
        for i in range(4)
    ]
    for college, handler in zip(colleges[:3], [counselor, other, head], strict=True):
        CounselorResponsibility.objects.create(college=college, counselor=handler)
    StudentAffiliation.objects.create(student=student, college=colleges[0])
    StudentAffiliation.objects.create(student=other_student, college=colleges[1])
    StaffSupervision.objects.create(staff=gss, supervisor=counselor)
    StaffSupervision.objects.create(staff=head_gss, supervisor=head)
    service = Service.objects.create(code="COUNSELING", name="Counseling")
    now = timezone.now()
    appointment = Appointment.objects.create(
        reference_code="GM-APPOINTMENT",
        student=student,
        provider=counselor,
        service=service,
        delivery_mode="IN_PERSON",
        starts_at=now + timedelta(hours=1),
        ends_at=now + timedelta(hours=2),
        created_by=student,
    )
    return SimpleNamespace(**locals())


def office(world, **kwargs):
    return services.open_office_thread(
        actor=world.student, client_message_id=uuid4(), body=BODY, **kwargs
    )


def counseling(world, **kwargs):
    return services.open_counseling_thread(
        actor=world.student,
        appointment_id=world.appointment.pk,
        client_message_id=uuid4(),
        body=BODY,
        **kwargs,
    )


def send(world, thread, *, actor=None, client_id=None, body=BODY):
    return services.send_message(
        actor=actor or world.student,
        thread_id=thread.pk,
        client_message_id=client_id or uuid4(),
        body=body,
    )


def deny(user, code):
    return UserCapabilityOverride.objects.create(
        user=user,
        capability=Capability.objects.get(code=code),
        effect="REVOKE",
        reason="Synthetic authorization proof",
    )


def post(client, path, payload):
    return client.post(BASE + path, data=json.dumps(payload), content_type="application/json")


def test_role_grants_dependencies_and_no_designation_content():
    for role, suffix in [("STUDENT", "_self"), ("COUNSELOR", ""), ("GUIDANCE_SERVICES_STAFF", "")]:
        assert {
            "guidance_messages.view" + suffix,
            "guidance_messages.manage" + suffix,
        } <= ROLE_CAPABILITY_GRANTS[role]
    for role in ["IT_ADMIN", "INSTITUTIONAL_OFFICER"]:
        assert not any(
            code.startswith("guidance_messages.") for code in ROLE_CAPABILITY_GRANTS[role]
        )
    for grants in DESIGNATION_CAPABILITY_GRANTS.values():
        assert not any(code.startswith("guidance_messages.") for code in grants)
    assert CAPABILITY_DEPENDENCIES["guidance_messages.manage"] == {"guidance_messages.view"}
    assert CAPABILITY_DEPENDENCIES["guidance_messages.manage_self"] == {
        "guidance_messages.view_self"
    }


@pytest.mark.parametrize("actor", ["student", "counselor", "gss"])
def test_office_current_handled_scope_allows(world, actor):
    thread, _ = office(world)
    assert services.get_thread(actor=getattr(world, actor), thread_id=thread.pk).pk == thread.pk


@pytest.mark.parametrize("actor", ["other_student", "other", "head", "head_gss", "admin", "dpo"])
def test_office_conceals_other_workload_and_role(world, actor):
    thread, _ = office(world)
    with pytest.raises(ThreadNotFound):
        services.get_thread(actor=getattr(world, actor), thread_id=thread.pk)
    response = auth_client(getattr(world, actor)).get(f"{BASE}/threads/{thread.pk}/messages")
    assert response.status_code == 404
    assert BODY not in response.content.decode()


@pytest.mark.parametrize("college_index", [2, 3])
def test_head_and_supervised_gss_only_explicit_or_unique_fallback(world, college_index):
    StudentAffiliation.objects.filter(student=world.student).update(
        college=world.colleges[college_index]
    )
    thread, _ = office(world)
    for actor in [world.student, world.head, world.head_gss]:
        assert services.get_thread(actor=actor, thread_id=thread.pk).pk == thread.pk
    assert set(policy.recipient_ids(thread)) == {world.student.pk, world.head.pk, world.head_gss.pk}
    assert [item.id for item in services.eligible_students(actor=world.head_gss).items] == [
        world.student.pk
    ]


def test_multiple_heads_fail_closed_without_implicit_fallback(world):
    world.other.designations.add(Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"))
    StudentAffiliation.objects.filter(student=world.student).update(college=world.colleges[3])
    with pytest.raises(MessagesConflict, match="routing"):
        office(world)
    assert not GuidanceThread.objects.exists()
    for actor in [world.head, world.head_gss]:
        assert world.student.pk not in [
            item.id for item in services.eligible_students(actor=actor).items
        ]
    # Explicit handled workload remains valid when Head fallback is ambiguous.
    StudentAffiliation.objects.filter(student=world.student).update(college=world.colleges[2])
    assert office(world)[0].assigned_to_id == world.head.pk


@pytest.mark.parametrize(
    "fault", ["supervision", "supervisor", "responsibility", "college", "campus"]
)
def test_current_authorization_revokes_stale_assignment(world, fault):
    thread, _ = office(world)
    services.assign_handler(actor=world.counselor, thread_id=thread.pk, handler_id=world.gss.pk)
    if fault == "supervision":
        StaffSupervision.objects.filter(staff=world.gss).delete()
    elif fault == "supervisor":
        User.objects.filter(pk=world.counselor.pk).update(is_active=False)
    elif fault == "responsibility":
        CounselorResponsibility.objects.filter(counselor=world.counselor).update(
            counselor=world.other
        )
    elif fault == "college":
        College.objects.filter(pk=world.colleges[0].pk).update(is_active=False)
    else:
        Campus.objects.filter(pk=world.campus.pk).update(is_active=False)
    with pytest.raises(ThreadNotFound):
        services.get_thread(actor=world.gss, thread_id=thread.pk)
    thread.refresh_from_db()
    assert thread.assigned_to_id == world.gss.pk
    assert world.gss.pk not in policy.recipient_ids(thread)


def test_dependency_denial_and_overrides_do_not_bypass_resource_policy(world):
    thread, _ = office(world)
    deny(world.counselor, "guidance_messages.view")
    with pytest.raises(ThreadNotFound):
        send(world, thread, actor=world.counselor)
    UserCapabilityOverride.objects.create(
        user=world.admin,
        capability=Capability.objects.get(code="guidance_messages.view"),
        effect="GRANT",
        reason="Synthetic override",
    )
    with pytest.raises(ThreadNotFound):
        services.get_thread(actor=world.admin, thread_id=thread.pk)


@pytest.mark.parametrize("actor", ["student", "counselor"])
def test_counseling_exact_participants_and_canonical_anchor(world, actor):
    result = services.open_counseling_thread(
        actor=getattr(world, actor),
        appointment_id=world.appointment.pk,
        client_message_id=uuid4(),
        body=BODY,
    )
    thread, message = result
    assert thread.student_id == world.student.pk
    assert thread.counselor_id == world.counselor.pk
    assert thread.relationship_appointment_id == world.appointment.pk
    assert thread.routing_college_id is None and thread.assigned_to_id is None
    assert content.read_body(message) == BODY
    same, _ = counseling(world)
    assert same.pk == thread.pk
    assert GuidanceThread.objects.count() == 1
    assert set(policy.recipient_ids(thread)) == {world.student.pk, world.counselor.pk}


@pytest.mark.parametrize(
    "actor", ["gss", "head", "head_gss", "other", "other_student", "admin", "dpo"]
)
def test_counseling_creation_and_content_are_relationship_only(world, actor):
    with pytest.raises((ThreadNotFound, MessagesPermissionDenied)):
        services.open_counseling_thread(
            actor=getattr(world, actor),
            appointment_id=world.appointment.pk,
            client_message_id=uuid4(),
            body=BODY,
        )
    thread, _ = counseling(world)
    with pytest.raises(ThreadNotFound):
        services.get_thread(actor=getattr(world, actor), thread_id=thread.pk)


@pytest.mark.parametrize(
    "fault", ["CANCELLED", "NO_SHOW", "service", "inactive_provider", "provider_role"]
)
def test_invalid_counseling_relationship_rejected_without_orphan(world, fault):
    if fault in ["CANCELLED", "NO_SHOW"]:
        field = "cancelled_at" if fault == "CANCELLED" else "no_show_at"
        Appointment.objects.filter(pk=world.appointment.pk).update(
            status=fault, **{field: timezone.now()}
        )
    elif fault == "service":
        other_service = Service.objects.create(code="GM-OTHER", name="Synthetic Other Service")
        Appointment.objects.filter(pk=world.appointment.pk).update(service=other_service)
    elif fault == "inactive_provider":
        User.objects.filter(pk=world.counselor.pk).update(is_active=False)
    else:
        User.objects.filter(pk=world.counselor.pk).update(role=Role.objects.get(code="IT_ADMIN"))
    with pytest.raises(ThreadNotFound):
        counseling(world)
    assert not GuidanceThread.objects.exists()


def test_completed_creation_and_historical_participation_survive_lifecycle_and_reassignment(world):
    Appointment.objects.filter(pk=world.appointment.pk).update(
        status="COMPLETED", completed_at=timezone.now()
    )
    thread, _ = counseling(world)
    Appointment.objects.filter(pk=world.appointment.pk).update(
        status="CANCELLED", completed_at=None, cancelled_at=timezone.now(), provider=world.other
    )
    for actor in [world.student, world.counselor]:
        assert services.get_thread(actor=actor, thread_id=thread.pk).pk == thread.pk
        assert services.list_messages(actor=actor, thread_id=thread.pk)[0]
    with pytest.raises(ThreadNotFound):
        services.get_thread(actor=world.other, thread_id=thread.pk)
    assert counseling(world)[0].pk == thread.pk


@pytest.mark.parametrize("body", ["", " \n\t", "x" * 4001, "bad\x00text", "bad\ud800text", 123])
def test_invalid_first_body_rolls_back_every_domain_row_and_success_audit(world, body):
    before = AuditEvent.objects.count()
    with pytest.raises(InvalidMessageInput):
        services.open_office_thread(actor=world.student, body=body, client_message_id=uuid4())
    assert not GuidanceThread.objects.exists()
    assert not GuidanceMessage.objects.exists()
    assert not GuidanceThreadReadState.objects.exists()
    assert AuditEvent.objects.count() == before


def test_plaintext_absent_from_rows_audit_logs_and_directory(world, caplog):
    client = auth_client(world.student)
    response = post(client, "/office-thread", {"body": BODY, "client_message_id": str(uuid4())})
    assert response.status_code == 200, response.content
    assert response.json()["message"]["body"] == BODY
    thread_id = response.json()["thread"]["id"]
    rows = json.dumps(list(GuidanceMessage.objects.values()), default=str)
    assert BODY not in rows and "Line two" not in rows
    assert "body_ciphertext" in rows
    audit = json.dumps(
        list(AuditEvent.objects.filter(action__startswith="guidance_messages.").values()),
        default=str,
    )
    assert BODY not in audit and "body_ciphertext" not in audit
    assert BODY not in caplog.text
    for user in [world.student, world.counselor, world.gss]:
        actor_client = auth_client(user)
        page = actor_client.get(BASE + "/threads")
        assert page.status_code == 200
        assert "body" not in page.content.decode() and "ciphertext" not in page.content.decode()
        assert page["Cache-Control"] == "no-store, private"
        messages = actor_client.get(f"{BASE}/threads/{thread_id}/messages")
        assert messages.json()["items"][0]["body"] == BODY
        assert set(messages.json()["items"][0]["sender"]) == {"id", "display_name"}


@pytest.mark.parametrize(
    "fault", ["token", "missing", "schema", "thread", "message", "sequence", "sender", "keyring"]
)
def test_bound_ciphertext_failures_are_closed_and_content_free(world, settings, caplog, fault):
    thread, message = office(world)
    if fault == "token":
        message.body_ciphertext = "malformed"
    elif fault == "missing":
        message.body_ciphertext = ""
    elif fault == "schema":
        message.body_schema_version = 2
    elif fault == "thread":
        message.thread_id = uuid4()
    elif fault == "message":
        message.pk = uuid4()
    elif fault == "sequence":
        message.sequence += 1
    elif fault == "sender":
        message.sender_id = world.other.pk
    else:
        settings.GUIDANCE_MESSAGE_ENCRYPTION_KEYS = ()
    with pytest.raises(GuidanceMessageContentUnavailable) as caught:
        content.read_body(message)
    assert BODY not in repr(caught.value) and "gAAAA" not in repr(caught.value)
    assert BODY not in caplog.text


def test_missing_key_api_failure_and_rotation_compatibility(world, settings):
    old = Fernet.generate_key().decode()
    new = Fernet.generate_key().decode()
    settings.GUIDANCE_MESSAGE_ENCRYPTION_KEYS = (old,)
    thread, historical = office(world)
    settings.GUIDANCE_MESSAGE_ENCRYPTION_KEYS = (new, old)
    current = send(world, thread)
    assert crypto.encrypted_with_primary_key(current.body_ciphertext, keyring=(new,))
    assert content.read_body(historical) == BODY
    settings.GUIDANCE_MESSAGE_ENCRYPTION_KEYS = ()
    response = auth_client(world.student).get(f"{BASE}/threads/{thread.pk}/messages")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "guidance_message_content_unavailable"
    # Thread navigation is structural and requires no decryption.
    assert auth_client(world.student).get(BASE + "/threads").status_code == 200
    thread.refresh_from_db()
    before = thread.last_sequence
    with pytest.raises(GuidanceMessageContentUnavailable):
        send(world, thread)
    thread.refresh_from_db()
    assert thread.last_sequence == before


def test_ciphertext_swap_across_rows_is_unavailable(world):
    thread, first = office(world)
    second = send(world, thread)
    GuidanceMessage.objects.filter(pk=second.pk).update(body_ciphertext=first.body_ciphertext)
    response = auth_client(world.student).get(f"{BASE}/threads/{thread.pk}/messages")
    assert response.status_code == 503
    assert BODY not in response.content.decode()


def test_persistent_retry_cross_thread_reuse_and_no_plaintext_redis_store(world, monkeypatch):
    thread, _ = office(world)
    key = uuid4()
    first = send(world, thread, client_id=key)
    retry = send(world, thread, client_id=key, body="Changed retry body is never stored")
    assert retry.pk == first.pk
    assert GuidanceMessage.objects.count() == 2
    assert content.read_body(retry) == BODY
    other_thread, _ = counseling(world)
    with pytest.raises(MessagesConflict):
        send(world, other_thread, client_id=key)
    # The product routes do not invoke generic Redis replay. A replay also works after resolve.
    services.set_status(actor=world.counselor, thread_id=thread.pk, resolved=True)
    assert send(world, thread, client_id=key).pk == first.pk


def test_private_monotonic_read_state_and_actor_unread_only(world):
    thread, _ = office(world)
    reply = send(world, thread, actor=world.counselor)
    assert services.get_thread(actor=world.student, thread_id=thread.pk).own_unread_count == 1
    assert services.get_thread(actor=world.counselor, thread_id=thread.pk).own_unread_count == 1
    services.mark_read(actor=world.student, thread_id=thread.pk, sequence=reply.sequence)
    services.mark_read(actor=world.student, thread_id=thread.pk, sequence=0)
    assert services.get_thread(actor=world.student, thread_id=thread.pk).own_unread_count == 0
    assert services.get_thread(actor=world.counselor, thread_id=thread.pk).own_unread_count == 1
    with pytest.raises(InvalidMessageInput):
        services.mark_read(actor=world.student, thread_id=thread.pk, sequence=3)
    with pytest.raises(ThreadNotFound):
        services.mark_read(actor=world.other_student, thread_id=thread.pk, sequence=1)
    response = auth_client(world.counselor).get(f"{BASE}/threads/{thread.pk}")
    assert response.json()["own_last_read_sequence"] == 0
    assert not any(
        key in response.json()
        for key in ["read_states", "read_by", "seen", "student_read_sequence"]
    )
    client = auth_client(world.student)
    bad = client.patch(
        f"{BASE}/threads/{thread.pk}/read",
        data=json.dumps({"sequence": 1, "user_id": str(world.counselor.pk)}),
        content_type="application/json",
    )
    assert bad.status_code == 422
    assert GuidanceThreadReadState.objects.count() == 1


@pytest.mark.parametrize("kind", ["OFFICE", "COUNSELING"])
def test_resolve_reopen_provenance_and_message_immutability(world, kind):
    thread, message = office(world) if kind == "OFFICE" else counseling(world)
    with pytest.raises(ThreadNotFound):
        services.set_status(actor=world.student, thread_id=thread.pk, resolved=True)
    services.set_status(actor=world.counselor, thread_id=thread.pk, resolved=True)
    thread.refresh_from_db()
    assert thread.resolved_by_id == world.counselor.pk and thread.resolved_at
    with pytest.raises(MessagesConflict):
        send(world, thread)
    services.set_status(actor=world.counselor, thread_id=thread.pk, resolved=False)
    assert send(world, thread).sequence == 2
    message.refresh_from_db()
    assert content.read_body(message) == BODY
    assert set(
        AuditEvent.objects.filter(action__startswith="guidance_messages.").values_list(
            "action", flat=True
        )
    ) >= {"guidance_messages.thread.resolved", "guidance_messages.thread.reopened"}


def test_resolved_office_new_concern_and_reopen_conflict(world):
    old, _ = office(world)
    services.set_status(actor=world.counselor, thread_id=old.pk, resolved=True)
    new, _ = office(world)
    assert new.pk != old.pk
    with pytest.raises(MessagesConflict):
        services.set_status(actor=world.counselor, thread_id=old.pk, resolved=False)
    assert GuidanceThread.objects.count() == 2


@pytest.mark.parametrize("handler", ["counselor", "gss"])
def test_assignment_transfer_provenance_is_not_ownership(world, handler):
    thread, _ = office(world)
    services.assign_handler(
        actor=world.gss, thread_id=thread.pk, handler_id=getattr(world, handler).pk
    )
    thread.refresh_from_db()
    assert thread.student_id == world.student.pk
    assert thread.assigned_to_id == getattr(world, handler).pk
    assert services.get_thread(actor=world.student, thread_id=thread.pk).pk == thread.pk


@pytest.mark.parametrize(
    "handler", ["student", "other", "head", "head_gss", "admin", "dpo", "inactive"]
)
def test_invalid_handlers_rejected(world, handler):
    thread, _ = office(world)
    candidate = world.other if handler == "inactive" else getattr(world, handler)
    if handler == "inactive":
        User.objects.filter(pk=candidate.pk).update(is_active=False)
    with pytest.raises(InvalidMessageInput):
        services.assign_handler(actor=world.gss, thread_id=thread.pk, handler_id=candidate.pk)


def test_staff_picker_current_only_and_scoped_initiation(world):
    assert [item.id for item in services.eligible_students(actor=world.gss).items] == [
        world.student.pk
    ]
    with pytest.raises(ThreadNotFound):
        services.open_office_thread(
            actor=world.gss, student_id=world.other_student.pk, client_message_id=uuid4(), body=BODY
        )
    assert (
        services.open_office_thread(
            actor=world.gss, student_id=world.student.pk, client_message_id=uuid4(), body=BODY
        )[0].student_id
        == world.student.pk
    )
    User.objects.filter(pk=world.student.pk).update(student_lifecycle_status="GRADUATED")
    assert not services.eligible_students(actor=world.gss).items


def test_options_only_canonical_relationships_and_pagination(world):
    client = auth_client(world.student)
    options = client.get(BASE + "/recipient-options").json()
    assert options["office_label"] == "Guidance Office"
    assert [item["appointment_id"] for item in options["counseling_relationships"]] == [
        str(world.appointment.pk)
    ]
    deny(world.counselor, "guidance_messages.view")
    assert client.get(BASE + "/recipient-options").json()["counseling_relationships"] == []
    assert client.get(BASE + "/recipient-options?page_size=51").status_code == 422


def test_api_strict_schemas_auth_capabilities_and_no_product_edit_delete(world):
    assert Client().get(BASE + "/threads").status_code == 401
    assert auth_client(world.admin).get(BASE + "/threads").status_code == 403
    client = auth_client(world.student)
    for extra in ["student_id", "college_id", "counselor_id", "handler_id", "kind", "attachments"]:
        response = post(
            client,
            "/office-thread",
            {"body": BODY, "client_message_id": str(uuid4()), extra: str(world.other.pk)},
        )
        assert response.status_code == 422
    assert post(client, "/office-thread", {"body": BODY}).status_code == 422
    assert (
        post(
            client, "/office-thread", {"body": "x" * 4001, "client_message_id": str(uuid4())}
        ).status_code
        == 422
    )
    assert not GuidanceThread.objects.exists()
    thread, message = office(world)
    for path in [f"/threads/{thread.pk}/messages/{message.pk}", f"/threads/{thread.pk}/messages"]:
        assert client.delete(BASE + path).status_code in [404, 405]
        assert client.patch(
            BASE + path, data='{"body":"replace"}', content_type="application/json"
        ).status_code in [404, 405]
    for query in ["page=0", "page_size=0", "page_size=51"]:
        assert client.get(BASE + "/threads?" + query).status_code == 422
    assert client.get(f"{BASE}/threads/{thread.pk}/messages?before_sequence=0").status_code == 422
    assert client.get(f"{BASE}/threads/{thread.pk}/messages?page_size=51").status_code == 422


def test_message_history_bounded_chronological_and_directory_no_decrypt(world, monkeypatch):
    thread, _ = office(world)
    for _ in range(4):
        send(world, thread, actor=world.counselor)
    rows, older = services.list_messages(actor=world.student, thread_id=thread.pk, page_size=2)
    assert [row.sequence for row in rows] == [4, 5] and older
    rows, older = services.list_messages(
        actor=world.student, thread_id=thread.pk, page_size=2, before_sequence=4
    )
    assert [row.sequence for row in rows] == [2, 3] and older

    def fail(_message):
        raise AssertionError("Thread directory must not decrypt")

    monkeypatch.setattr(content, "read_body", fail)
    assert auth_client(world.student).get(BASE + "/threads").status_code == 200


@pytest.mark.parametrize(
    "fields",
    [
        {"kind": "OFFICE", "counselor": "counselor"},
        {"kind": "OFFICE", "relationship_appointment": "appointment"},
        {"kind": "OFFICE", "routing_college": None},
        {"kind": "COUNSELING", "routing_college": "college"},
        {"kind": "COUNSELING", "counselor": None},
        {"kind": "COUNSELING", "relationship_appointment": None},
        {"kind": "COUNSELING", "assigned_to": "gss"},
        {"status": "RESOLVED"},
        {"status": "OPEN", "resolved_by": "counselor", "resolved_at": "now"},
        {"last_sequence": -1},
    ],
)
def test_postgresql_shape_constraints(world, fields):
    kind = fields.get("kind", "OFFICE")
    values = dict(kind=kind, student=world.student, created_by=world.student)
    if kind == "OFFICE":
        values["routing_college"] = world.colleges[0]
    else:
        values.update(counselor=world.counselor, relationship_appointment=world.appointment)
    mapping = {
        "counselor": world.counselor,
        "appointment": world.appointment,
        "college": world.colleges[0],
        "gss": world.gss,
        "now": timezone.now(),
    }
    values.update({key: mapping.get(value, value) for key, value in fields.items()})
    with pytest.raises(IntegrityError), transaction.atomic():
        GuidanceThread.objects.create(**values)


def test_postgresql_uniqueness_nonnegative_and_protect(world):
    thread, message = office(world)
    with pytest.raises(IntegrityError), transaction.atomic():
        GuidanceThread.objects.create(
            kind="OFFICE",
            student=world.student,
            created_by=world.student,
            routing_college=world.colleges[0],
        )
    cthread, _ = counseling(world)
    with pytest.raises(IntegrityError), transaction.atomic():
        GuidanceThread.objects.create(
            kind="COUNSELING",
            student=world.student,
            counselor=world.counselor,
            relationship_appointment=world.appointment,
            created_by=world.student,
        )
    base = dict(
        thread=thread,
        sender=world.student,
        client_message_id=uuid4(),
        body_ciphertext="synthetic ciphertext",
    )
    for sequence in [0, -1, 1]:
        with pytest.raises(IntegrityError), transaction.atomic():
            GuidanceMessage.objects.create(sequence=sequence, **base)
    with pytest.raises(IntegrityError), transaction.atomic():
        GuidanceMessage.objects.create(
            thread=cthread,
            sender=world.student,
            client_message_id=message.client_message_id,
            sequence=2,
            body_ciphertext="synthetic",
        )
    GuidanceThreadReadState.objects.create(thread=thread, user=world.student)
    with pytest.raises(IntegrityError), transaction.atomic():
        GuidanceThreadReadState.objects.create(thread=thread, user=world.student)
    with pytest.raises(IntegrityError), transaction.atomic():
        GuidanceThreadReadState.objects.create(
            thread=thread, user=world.counselor, last_read_sequence=-1
        )
    for record in [thread, world.student, world.counselor, world.appointment, world.colleges[0]]:
        with pytest.raises(ProtectedError):
            record.delete()


def test_first_send_accepts_full_limit_without_rewriting_text(world):
    body = "α\n" + "x" * 3998
    _, message = services.open_office_thread(
        actor=world.student, client_message_id=uuid4(), body=body
    )
    assert content.read_body(message) == body


def test_missing_key_cannot_commit_an_empty_new_thread(world, settings):
    settings.GUIDANCE_MESSAGE_ENCRYPTION_KEYS = ()
    with pytest.raises(GuidanceMessageContentUnavailable):
        office(world)
    assert not GuidanceThread.objects.exists()
    assert not AuditEvent.objects.filter(action__startswith="guidance_messages.").exists()


def test_staff_transfer_and_status_http_proof_without_workflow_mutation(world):
    client = auth_client(world.student)
    start = post(client, "/office-thread", {"body": BODY, "client_message_id": str(uuid4())})
    identifier = start.json()["thread"]["id"]
    staff = auth_client(world.gss)
    assign = staff.patch(
        f"{BASE}/threads/{identifier}/handler",
        data=json.dumps({"handler_id": str(world.gss.pk)}),
        content_type="application/json",
    )
    assert assign.status_code == 200
    assert assign.json()["assigned_to"]["id"] == str(world.gss.pk)
    assert post(staff, f"/threads/{identifier}/resolve", {}).status_code == 200
    assert (
        post(
            client,
            f"/threads/{identifier}/messages",
            {"body": BODY, "client_message_id": str(uuid4())},
        ).status_code
        == 409
    )
    assert post(client, f"/threads/{identifier}/reopen", {}).status_code == 404
    assert post(staff, f"/threads/{identifier}/reopen", {}).status_code == 200
    assert (
        post(
            client,
            f"/threads/{identifier}/messages",
            {"body": BODY, "client_message_id": str(uuid4())},
        ).status_code
        == 200
    )
    world.appointment.refresh_from_db()
    assert world.appointment.status == "SCHEDULED"
    record = AuditEvent.objects.get(action="guidance_messages.thread.assigned")
    assert record.metadata["previous_handler_id"] == str(world.counselor.pk)
    assert record.metadata["handler_id"] == str(world.gss.pk)


@pytest.mark.parametrize("configuration", ["absent", "valid", "malformed", "reuse"])
def test_runtime_keyring_configuration_boundary(configuration):
    import os
    import subprocess
    import sys

    environment = os.environ.copy()
    environment.pop("GUIDANCE_MESSAGE_ENCRYPTION_KEYS_FILE", None)
    environment.pop("GUIDANCE_MESSAGE_ENCRYPTION_KEYS", None)
    if configuration == "valid":
        environment["GUIDANCE_MESSAGE_ENCRYPTION_KEYS"] = Fernet.generate_key().decode()
    if configuration == "malformed":
        environment["GUIDANCE_MESSAGE_ENCRYPTION_KEYS"] = "malformed synthetic key"
    if configuration == "reuse":
        environment["GUIDANCE_MESSAGE_ENCRYPTION_KEYS"] = environment[
            "COUNSELING_SHARED_SUMMARY_ENCRYPTION_KEYS"
        ]
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from config import settings; print(len(settings.GUIDANCE_MESSAGE_ENCRYPTION_KEYS))",
        ],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    if configuration in ["absent", "valid"]:
        assert result.returncode == 0
        assert result.stdout.strip() == ("0" if configuration == "absent" else "1")
    else:
        assert result.returncode != 0
        assert "GUIDANCE_MESSAGE_ENCRYPTION_KEYS" in result.stderr
        assert environment["GUIDANCE_MESSAGE_ENCRYPTION_KEYS"] not in result.stderr
