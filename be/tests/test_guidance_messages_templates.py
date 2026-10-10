"""Message templates (ADR-104): reusable editable text that never sends, links or signals."""

from __future__ import annotations

import json
from datetime import timedelta
from uuid import uuid4

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from compass.accounts.models import Capability, UserCapabilityOverride
from compass.accounts.policy import (
    CAPABILITY_DEPENDENCIES,
    DESIGNATION_CAPABILITY_GRANTS,
    ROLE_CAPABILITY_GRANTS,
)
from compass.audit.models import AuditEvent
from compass.guidance_messages import content, templates
from compass.guidance_messages.errors import (
    InvalidMessageInput,
    MessagesConflict,
    MessagesPermissionDenied,
    TemplateNameTaken,
    TemplateNotFound,
)
from compass.guidance_messages.models import (
    GuidanceMessage,
    GuidanceMessageTemplate,
    GuidanceThread,
)
from compass.realtime import publish
from tests.test_guidance_messages import BASE, deny, office, post, world  # noqa: F401
from tests.test_notifications import auth_client

# Imported fixture names are intentionally consumed by pytest injection.
# ruff: noqa: F811
pytestmark = pytest.mark.django_db
TEXT = "Good day. Please visit the Guidance Office during office hours.\n\nThank you.  "
MANAGE = "guidance_messages.templates.manage"


def create(world, *, actor=None, name="Office follow-up", body=TEXT):
    return templates.create_template(actor=actor or world.counselor, name=name, body=body)


def patch(client, path, payload):
    # Existing mutation scenarios carry a version; omission is tested with raw PATCH below.
    if "expected_updated_at" not in payload:
        row = GuidanceMessageTemplate.objects.filter(pk=path.rsplit("/", 1)[-1]).first()
        payload = {
            **payload,
            "expected_updated_at": (row.updated_at if row else timezone.now()).isoformat(),
        }
    return client.patch(BASE + path, data=json.dumps(payload), content_type="application/json")


def names(world, *, actor=None, **query):
    rows, _ = templates.list_templates(actor=actor or world.counselor, **query)
    return [row.name for row in rows]


# Authority.
def test_capability_policy_is_staff_only_and_depends_on_messages_manage():
    assert CAPABILITY_DEPENDENCIES[MANAGE] == {"guidance_messages.manage"}
    assert MANAGE in ROLE_CAPABILITY_GRANTS["COUNSELOR"]
    assert MANAGE in ROLE_CAPABILITY_GRANTS["GUIDANCE_SERVICES_STAFF"]
    for role in ["STUDENT", "IT_ADMIN", "INSTITUTIONAL_OFFICER"]:
        assert MANAGE not in ROLE_CAPABILITY_GRANTS[role]
    for grants in DESIGNATION_CAPABILITY_GRANTS.values():
        assert MANAGE not in grants


@pytest.mark.parametrize("manager", ["counselor", "gss", "head", "head_gss"])
def test_baseline_staff_create_edit_archive_and_restore(world, manager):
    actor = getattr(world, manager)
    template = create(world, actor=actor)
    template = templates.update_template(
        expected_updated_at=template.updated_at,
        actor=actor,
        template_id=template.pk,
        name="Office reply",
        body="Edited text.",
    )
    assert (template.name, template.body, template.updated_by_id) == (
        "Office reply",
        "Edited text.",
        actor.pk,
    )
    archived = templates.set_template_status(actor=actor, template_id=template.pk, archived=True)
    assert (archived.status, archived.archived_by_id) == ("ARCHIVED", actor.pk)
    assert archived.archived_at is not None
    restored = templates.set_template_status(actor=actor, template_id=template.pk, archived=False)
    assert (restored.status, restored.archived_by_id, restored.archived_at) == (
        "ACTIVE",
        None,
        None,
    )


def test_override_removing_template_management_keeps_use_but_blocks_management(world):
    template = create(world)
    deny(world.gss, MANAGE)
    assert names(world, actor=world.gss) == ["Office follow-up"]
    client = auth_client(world.gss)
    assert post(client, "/templates", {"name": "New", "body": TEXT}).status_code == 403
    assert patch(client, f"/templates/{template.pk}", {"body": "x"}).status_code == 403
    assert post(client, f"/templates/{template.pk}/archive", {}).status_code == 403
    assert post(client, f"/templates/{template.pk}/restore", {}).status_code == 403
    assert client.get(BASE + "/templates?status=ARCHIVED").status_code == 403
    assert client.get(BASE + "/templates").status_code == 200


@pytest.mark.parametrize("code", ["guidance_messages.manage", "guidance_messages.view"])
def test_without_messages_manage_templates_are_unavailable(world, code):
    create(world)
    deny(world.counselor, code)
    with pytest.raises(MessagesPermissionDenied):
        templates.list_templates(actor=world.counselor)
    with pytest.raises(MessagesPermissionDenied):
        create(world, name="Another")


@pytest.mark.parametrize("actor", ["student", "admin", "dpo"])
def test_students_it_admin_and_dpo_are_denied(world, actor):
    template = create(world)
    client = auth_client(getattr(world, actor))
    assert client.get(BASE + "/templates").status_code == 403
    assert client.get(BASE + "/templates?status=ARCHIVED").status_code == 403
    assert post(client, "/templates", {"name": "New", "body": TEXT}).status_code == 403
    assert patch(client, f"/templates/{template.pk}", {"body": "x"}).status_code == 403
    assert post(client, f"/templates/{template.pk}/archive", {}).status_code == 403
    assert TEXT not in client.get(BASE + "/templates").content.decode()


def test_granted_overrides_never_make_a_non_staff_role_a_template_user(world):
    for code in ["guidance_messages.view", "guidance_messages.manage", MANAGE]:
        UserCapabilityOverride.objects.create(
            user=world.admin,
            capability=Capability.objects.get(code=code),
            effect="GRANT",
            reason="Synthetic authorization proof",
        )
    assert world.admin.has_capability(MANAGE)
    with pytest.raises(MessagesPermissionDenied):
        create(world, actor=world.admin)
    with pytest.raises(MessagesPermissionDenied):
        templates.list_templates(actor=world.admin)


def test_unauthenticated_requests_are_refused():
    from django.test import Client

    assert Client().get(BASE + "/templates").status_code == 401


# HTTP contract, validation and content handling.
def test_create_over_http_keeps_text_exact_and_audits_structure_only(world):
    client = auth_client(world.counselor)
    response = post(client, "/templates", {"name": "  Office follow-up  ", "body": TEXT})
    assert response.status_code == 201
    assert response["Cache-Control"] == "no-store, private"
    data = response.json()
    assert set(data) == {"id", "name", "body", "status", "created_at", "updated_at", "archived_at"}
    assert (data["name"], data["body"], data["status"]) == ("Office follow-up", TEXT, "ACTIVE")
    stored = GuidanceMessageTemplate.objects.get(pk=data["id"])
    assert stored.body == TEXT
    event = AuditEvent.objects.get(action="guidance_messages.template.created")
    assert event.metadata == {"template_id": data["id"], "status": "ACTIVE"}
    assert event.target_type == "guidance.messages.template"
    assert "Guidance Office" not in json.dumps(event.metadata)


def test_exact_limit_and_astral_characters_are_accepted(world):
    body = "🙂" * content.BODY_LIMIT
    assert create(world, body=body).body == body
    with pytest.raises(InvalidMessageInput):
        create(world, name="Too long", body=body + "a")


@pytest.mark.parametrize(
    ("payload", "status"),
    [
        ({"name": "   ", "body": TEXT}, 422),
        ({"name": "Blank body", "body": " \n\t "}, 422),
        ({"name": "Long body", "body": "a" * 4001}, 422),
        ({"name": "x" * 121, "body": TEXT}, 422),
        ({"name": "NUL body", "body": "a\u0000b"}, 422),
        ({"name": "NUL\u0000name", "body": TEXT}, 422),
        ({"name": "Two\nlines", "body": TEXT}, 422),
        ({"name": "Number", "body": 5}, 422),
        ({"name": "Extra", "body": TEXT, "template_id": str(uuid4())}, 422),
    ],
)
def test_invalid_template_input_is_rejected(world, payload, status):
    response = post(auth_client(world.counselor), "/templates", payload)
    assert response.status_code == status
    assert not GuidanceMessageTemplate.objects.exists()
    assert not AuditEvent.objects.filter(action__startswith="guidance_messages.template").exists()


def test_invalid_unicode_is_rejected(world):
    response = auth_client(world.counselor).post(
        BASE + "/templates",
        data='{"name": "Surrogate", "body": "a\\ud800b"}',
        content_type="application/json",
    )
    assert response.status_code == 422
    with pytest.raises(InvalidMessageInput):
        create(world, name="Surrogate \ud800")


def test_duplicate_names_are_refused_case_insensitively(world):
    template = create(world)
    other = create(world, name="Appointment reminder")
    client = auth_client(world.counselor)
    response = post(client, "/templates", {"name": "OFFICE FOLLOW-UP", "body": TEXT})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "guidance_message_template_name_taken"
    assert patch(client, f"/templates/{other.pk}", {"name": "office follow-up"}).status_code == 409
    renamed = patch(client, f"/templates/{template.pk}", {"name": "Office Follow-Up"})
    assert renamed.status_code == 200
    templates.set_template_status(actor=world.counselor, template_id=template.pk, archived=True)
    with pytest.raises(TemplateNameTaken):
        create(world, name="office follow-up")


def test_database_constraints_guard_shape_names_and_length(world):
    base = {"created_by": world.counselor, "updated_by": world.counselor}
    cases = [
        {"name": "Archived", "body": TEXT, "status": "ARCHIVED"},
        {"name": "Active", "body": TEXT, "archived_at": timezone.now()},
        {"name": "   ", "body": TEXT},
        {"name": "Blank", "body": "  "},
        {"name": "Long", "body": "a" * 4001},
    ]
    for fields in cases:
        with pytest.raises(IntegrityError), transaction.atomic():
            GuidanceMessageTemplate.objects.create(**base, **fields)
    GuidanceMessageTemplate.objects.create(**base, name="Unique", body=TEXT)
    with pytest.raises(IntegrityError), transaction.atomic():
        GuidanceMessageTemplate.objects.create(**base, name="UNIQUE", body=TEXT)


# Editing, archive and restore.
def test_update_audits_changed_fields_only_and_skips_no_op(world):
    template = create(world)
    templates.update_template(
        expected_updated_at=template.updated_at, actor=world.gss, template_id=template.pk, body=TEXT
    )
    assert not AuditEvent.objects.filter(action="guidance_messages.template.updated").exists()
    templates.update_template(
        expected_updated_at=template.updated_at,
        actor=world.gss,
        template_id=template.pk,
        name="Office reply",
        body="New text",
    )
    event = AuditEvent.objects.get(action="guidance_messages.template.updated")
    assert event.metadata == {
        "template_id": str(template.pk),
        "status": "ACTIVE",
        "changed_fields": ["body", "name"],
    }
    assert "New text" not in json.dumps(event.metadata)
    with pytest.raises(InvalidMessageInput):
        templates.update_template(
            expected_updated_at=template.updated_at, actor=world.gss, template_id=template.pk
        )
    with pytest.raises(TemplateNotFound):
        templates.update_template(
            expected_updated_at=template.updated_at, actor=world.gss, template_id=uuid4(), body="x"
        )


def test_stale_editor_and_archived_template_cannot_be_overwritten(world):
    template = create(world)
    opened = template.updated_at
    templates.update_template(
        expected_updated_at=template.updated_at,
        actor=world.gss,
        template_id=template.pk,
        body="First save",
    )
    client = auth_client(world.counselor)
    stale = patch(
        client,
        f"/templates/{template.pk}",
        {"body": "Second save", "expected_updated_at": opened.isoformat()},
    )
    assert stale.status_code == 409
    template.refresh_from_db()
    assert template.body == "First save"
    current = patch(
        client,
        f"/templates/{template.pk}",
        {"body": "Second save", "expected_updated_at": template.updated_at.isoformat()},
    )
    assert current.status_code == 200
    templates.set_template_status(actor=world.counselor, template_id=template.pk, archived=True)
    with pytest.raises(MessagesConflict):
        templates.update_template(
            expected_updated_at=template.updated_at,
            actor=world.counselor,
            template_id=template.pk,
            body="Hidden",
        )
    assert patch(client, f"/templates/{uuid4()}", {"body": "x"}).status_code == 404


def test_archive_hides_from_picker_and_restore_returns_it(world):
    template = create(world)
    create(world, name="Appointment reminder")
    client = auth_client(world.counselor)
    assert post(client, f"/templates/{template.pk}/archive", {}).json()["status"] == "ARCHIVED"
    assert names(world, actor=world.gss) == ["Appointment reminder"]
    assert names(world, status="ARCHIVED") == ["Office follow-up"]
    # Repeating the current state records nothing.
    assert post(client, f"/templates/{template.pk}/archive", {}).status_code == 200
    assert AuditEvent.objects.filter(action="guidance_messages.template.archived").count() == 1
    assert post(client, f"/templates/{template.pk}/restore", {}).json()["status"] == "ACTIVE"
    assert names(world, actor=world.gss) == ["Appointment reminder", "Office follow-up"]
    assert AuditEvent.objects.filter(action="guidance_messages.template.restored").count() == 1
    assert post(client, f"/templates/{uuid4()}/archive", {}).status_code == 404


def test_list_orders_by_name_searches_names_only_and_pages(world):
    for name in ["beta", "Alpha", "gamma"]:
        create(world, name=name, body=f"Body mentions zeta for {name}")
    assert names(world) == ["Alpha", "beta", "gamma"]
    assert names(world, search=" ALP ") == ["Alpha"]
    assert names(world, search="zeta") == []
    first, more = templates.list_templates(actor=world.counselor, page=1, page_size=2)
    rest, last = templates.list_templates(actor=world.counselor, page=2, page_size=2)
    assert [row.name for row in [*first, *rest]] == ["Alpha", "beta", "gamma"]
    assert more and not last
    client = auth_client(world.counselor)
    for query in ["status=DELETED", "page=0", "page_size=51", "search=" + "x" * 121]:
        assert client.get(f"{BASE}/templates?{query}").status_code == 422


def test_there_is_no_product_delete(world):
    template = create(world)
    client = auth_client(world.counselor)
    assert client.delete(f"{BASE}/templates/{template.pk}").status_code == 405
    assert GuidanceMessageTemplate.objects.filter(pk=template.pk).exists()
    with pytest.raises(Exception):  # noqa: B017 - PROTECT keeps author provenance.
        world.counselor.delete()


# Templates never send, link or signal.
def test_template_operations_never_send_or_publish(
    world, settings, monkeypatch, django_capture_on_commit_callbacks
):
    office(world)
    settings.REALTIME_ENABLED = True
    frames = []
    monkeypatch.setattr(publish, "_publish", lambda channel, frame: frames.append(frame) or True)
    counts = (GuidanceMessage.objects.count(), GuidanceThread.objects.count())
    client = auth_client(world.counselor)
    with django_capture_on_commit_callbacks(execute=True):
        created = post(client, "/templates", {"name": "Office follow-up", "body": TEXT}).json()
        patch(client, f"/templates/{created['id']}", {"body": "Edited"})
        post(client, f"/templates/{created['id']}/archive", {})
        post(client, f"/templates/{created['id']}/restore", {})
        client.get(BASE + "/templates")
    assert frames == []
    assert (GuidanceMessage.objects.count(), GuidanceThread.objects.count()) == counts
    assert (
        not AuditEvent.objects.filter(action="guidance_messages.message.sent")
        .exclude(actor_user_id=world.student.pk)
        .exists()
    )


def test_message_written_from_a_template_is_an_ordinary_message(world):
    assert not any("template" in field.name for field in GuidanceMessage._meta.get_fields())
    thread, _ = office(world)
    template = create(world)
    staff = auth_client(world.gss)
    chosen = staff.get(BASE + "/templates").json()["items"][0]
    edited = chosen["body"].replace("office hours", "office hours this Friday")
    payload = {"body": edited, "client_message_id": str(uuid4())}
    sent = post(staff, f"/threads/{thread.pk}/messages", payload)
    assert sent.status_code == 200
    # A retry of the same intent is the same Message.
    assert post(staff, f"/threads/{thread.pk}/messages", payload).json()["id"] == sent.json()["id"]
    message = GuidanceMessage.objects.get(pk=sent.json()["id"])
    assert edited not in message.body_ciphertext
    assert template.body not in message.body_ciphertext
    assert content.read_body(message) == edited
    event = AuditEvent.objects.get(
        action="guidance_messages.message.sent", metadata__message_id=str(message.pk)
    )
    assert "template" not in json.dumps(event.metadata)
    received = auth_client(world.student).get(f"{BASE}/threads/{thread.pk}/messages").json()
    latest = received["items"][-1]
    assert set(latest) == {"id", "sequence", "sender", "body", "created_at"}
    assert latest["body"] == edited
    # Archiving or editing the template never touches what was sent.
    templates.update_template(
        expected_updated_at=template.updated_at,
        actor=world.counselor,
        template_id=template.pk,
        body="Changed",
    )
    templates.set_template_status(actor=world.counselor, template_id=template.pk, archived=True)
    assert content.read_body(GuidanceMessage.objects.get(pk=message.pk)) == edited


def test_naive_expected_timestamp_is_rejected(world):
    template = create(world)
    naive = (template.updated_at + timedelta(0)).replace(tzinfo=None)
    with pytest.raises(InvalidMessageInput):
        templates.update_template(
            actor=world.counselor, template_id=template.pk, body="x", expected_updated_at=naive
        )


@pytest.mark.parametrize("version", [None, "invalid", "2026-10-10T01:00:00"])
def test_patch_requires_valid_aware_opened_version(world, version):
    template = create(world)
    client = auth_client(world.counselor)
    payload = {"body": "Must not overwrite"}
    if version is not None:
        payload["expected_updated_at"] = version
    response = client.patch(
        BASE + f"/templates/{template.pk}",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert response.status_code == 422
    template.refresh_from_db()
    assert template.body == TEXT


def test_service_version_cannot_be_omitted_or_null(world):
    template = create(world)
    with pytest.raises(TypeError):
        templates.update_template(actor=world.counselor, template_id=template.pk, body="x")
    with pytest.raises(InvalidMessageInput):
        templates.update_template(
            actor=world.counselor, template_id=template.pk, body="x", expected_updated_at=None
        )
