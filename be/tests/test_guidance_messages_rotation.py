"""Key maintenance preserves business facts and refuses invalid bound envelopes."""

from io import StringIO
from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test.utils import CaptureQueriesContext

from compass.audit.models import AuditEvent
from compass.confidential_data import crypto
from compass.guidance_messages import content
from compass.guidance_messages.models import (
    GuidanceMessage,
    GuidanceThread,
    GuidanceThreadReadState,
)
from compass.notifications.models import Notification
from tests.test_guidance_messages import BODY, office, send, world  # noqa: F401

# ruff: noqa: F811
pytestmark = pytest.mark.django_db


def run(**options):
    out, err = StringIO(), StringIO()
    call_command("rotate_guidance_message_encryption", stdout=out, stderr=err, **options)
    assert BODY not in out.getvalue() + err.getvalue()
    return out.getvalue(), err.getvalue()


def facts():
    return (
        list(GuidanceThread.objects.order_by("pk").values()),
        list(GuidanceThreadReadState.objects.order_by("pk").values()),
        list(
            GuidanceMessage.objects.order_by("pk").values(
                "id",
                "thread_id",
                "sequence",
                "sender_id",
                "client_message_id",
                "body_schema_version",
                "created_at",
            )
        ),
        list(AuditEvent.objects.order_by("pk").values()),
        Notification.objects.count(),
    )


def test_current_is_idempotent_and_keyless_operator_fails(world, settings):
    _, message = office(world)
    old = message.body_ciphertext
    with CaptureQueriesContext(connection) as queries:
        assert "Already under primary key: 1" in run()[0]
    assert all(not q["sql"].startswith("UPDATE") for q in queries)
    assert any("FOR UPDATE" in q["sql"] for q in queries)
    message.refresh_from_db()
    assert message.body_ciphertext == old
    settings.GUIDANCE_MESSAGE_ENCRYPTION_KEYS = ""
    with pytest.raises(CommandError, match="GUIDANCE_MESSAGE_ENCRYPTION_KEYS"):
        run()


def test_old_key_dry_run_batched_rotation_new_only_and_business_immutability(world, settings):
    old, new = Fernet.generate_key().decode(), Fernet.generate_key().decode()
    settings.GUIDANCE_MESSAGE_ENCRYPTION_KEYS = old
    thread, _ = office(world)
    for _ in range(3):
        send(world, thread)
    before = facts()
    tokens = list(GuidanceMessage.objects.order_by("pk").values_list("body_ciphertext", flat=True))
    settings.GUIDANCE_MESSAGE_ENCRYPTION_KEYS = f"{new},{old}"
    with CaptureQueriesContext(connection) as queries:
        assert "to re-encrypt: 4" in run(dry_run=True, batch_size=1)[0]
    assert all(not q["sql"].startswith("UPDATE") for q in queries)
    assert all("FOR UPDATE" not in q["sql"] for q in queries)
    assert (
        list(GuidanceMessage.objects.order_by("pk").values_list("body_ciphertext", flat=True))
        == tokens
    )
    with patch(
        "compass.guidance_messages.services.publish_to_user_on_commit",
        side_effect=AssertionError("hint"),
    ):
        assert "re-encrypted: 4" in run(batch_size=2)[0]
    assert facts() == before
    settings.GUIDANCE_MESSAGE_ENCRYPTION_KEYS = new
    assert all(content.read_body(row) == BODY for row in GuidanceMessage.objects.all())
    rotated = list(GuidanceMessage.objects.order_by("pk").values_list("body_ciphertext", flat=True))
    assert rotated != tokens
    assert "Already under primary key: 4" in run(batch_size=1)[0]
    assert (
        list(GuidanceMessage.objects.order_by("pk").values_list("body_ciphertext", flat=True))
        == rotated
    )


@pytest.mark.parametrize("damage", ["malformed", "swapped", "schema", "binding", "payload", "body"])
def test_invalid_envelope_is_left_unchanged_and_fails_safely(world, damage):
    thread, message = office(world)
    if damage == "malformed":
        message.body_ciphertext = "broken-ciphertext-sentinel"
    elif damage == "swapped":
        other = send(world, thread)
        message.body_ciphertext = other.body_ciphertext
    elif damage == "schema":
        message.body_schema_version = 99
    else:
        binding = content._binding(message)
        if damage == "binding":
            binding["sequence"] = "999"
        payload = (
            {"other": BODY} if damage == "payload" else {"body": "" if damage == "body" else BODY}
        )
        message.body_ciphertext = crypto.encrypt_bound_json(
            keyring=content.encryption_keyring(),
            schema_version=content.SCHEMA_VERSION,
            binding=binding,
            payload=payload,
        )
    message.save(update_fields=["body_ciphertext", "body_schema_version"])
    before = message.body_ciphertext
    out, err = StringIO(), StringIO()
    with pytest.raises(CommandError, match="left unchanged"):
        call_command("rotate_guidance_message_encryption", stdout=out, stderr=err)
    message.refresh_from_db()
    assert message.body_ciphertext == before
    text = out.getvalue() + err.getvalue()
    assert "invalid_envelope" in text
    assert BODY not in text and before not in text


@pytest.mark.parametrize("size", [0, -1, 1001])
def test_invalid_batch_size(size):
    with pytest.raises(CommandError, match="between 1 and 1000"):
        run(batch_size=size)
