from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

import pytest
from django.test import override_settings

from compass.integrations.daily import (
    DailyClient,
    DailyConfigurationError,
    DailyWebhookSignatureInvalid,
    verify_daily_webhook,
)


class CapturingDailyClient(DailyClient):
    def __init__(self) -> None:
        super().__init__("test-key", base_url="https://api.daily.co/v1", timeout_seconds=2.5)
        self.calls: list[tuple[str, str, dict[str, object] | None]] = []

    def _request(self, method: str, path: str, *, payload=None):
        self.calls.append((method, path, payload))
        if path == "/meeting-tokens":
            return {"token": "ephemeral-token"}
        if path.endswith(
            ("/recordings/start", "/recordings/stop", "/transcription/start", "/transcription/stop")
        ):
            return {"status": "sent"}
        return {
            "id": "provider-room-id",
            "name": "ec-opaque",
            "url": "https://example.daily.co/ec-opaque",
            "privacy": "private",
            "config": {},
        }


def _signature(secret: bytes, timestamp: str, body: bytes) -> str:
    digest = hmac.new(secret, timestamp.encode() + b"." + body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("ascii")


def test_daily_room_payload_is_private_bounded_and_media_capture_safe():
    client = CapturingDailyClient()
    client.create_room(room_name="ec-opaque", expires_at_epoch=2_000_000_000)

    method, path, payload = client.calls[-1]
    assert (method, path) == ("POST", "/rooms")
    assert payload["name"] == "ec-opaque"
    assert payload["privacy"] == "private"
    properties = payload["properties"]
    assert properties == {
        "exp": 2_000_000_000,
        "eject_at_room_exp": False,
        "max_participants": 2,
        "enable_chat": False,
        "enable_screenshare": False,
        "enable_live_captions_ui": False,
        "enable_transcription_storage": False,
        "enforce_unique_user_ids": True,
    }


def test_daily_token_payload_is_room_scoped_least_privilege_and_ephemeral():
    client = CapturingDailyClient()
    token = client.create_meeting_token(
        room_name="ec-opaque",
        user_id="6ae30a72-6456-4a1c-a944-f4f736752f0c",
        user_name="Test Student",
        expires_at_epoch=2_000_000_100,
    )
    assert token == "ephemeral-token"

    _, path, payload = client.calls[-1]
    assert path == "/meeting-tokens"
    properties = payload["properties"]
    assert properties["room_name"] == "ec-opaque"
    assert properties["user_id"] == "6ae30a72-6456-4a1c-a944-f4f736752f0c"
    assert properties["is_owner"] is False
    assert properties["permissions"] == {"canAdmin": False}
    assert properties["enable_recording_ui"] is False
    assert properties["start_cloud_recording"] is False
    assert properties["auto_start_transcription"] is False
    assert properties["enable_screenshare"] is False
    assert properties["enable_live_captions_ui"] is False
    assert "api_key" not in json.dumps(payload).lower()


def test_daily_media_control_payloads_match_documented_rest_boundary():
    client = CapturingDailyClient()

    client.update_room(
        room_name="ec-opaque",
        properties={"enable_recording": "cloud"},
    )
    assert client.calls[-1] == (
        "POST",
        "/rooms/ec-opaque",
        {"properties": {"enable_recording": "cloud"}},
    )

    client.start_recording(room_name="ec-opaque", instance_id="recording-instance")
    assert client.calls[-1] == (
        "POST",
        "/rooms/ec-opaque/recordings/start",
        {"instanceId": "recording-instance", "type": "cloud"},
    )

    client.stop_recording(room_name="ec-opaque")
    assert client.calls[-1] == (
        "POST",
        "/rooms/ec-opaque/recordings/stop",
        None,
    )

    client.update_room(
        room_name="ec-opaque",
        properties={"enable_transcription_storage": True},
    )
    assert client.calls[-1] == (
        "POST",
        "/rooms/ec-opaque",
        {"properties": {"enable_transcription_storage": True}},
    )

    client.start_transcription(room_name="ec-opaque", instance_id="transcription-instance")
    assert client.calls[-1] == (
        "POST",
        "/rooms/ec-opaque/transcription/start",
        {"instanceId": "transcription-instance"},
    )

    client.stop_transcription(room_name="ec-opaque", instance_id="transcription-instance")
    assert client.calls[-1] == (
        "POST",
        "/rooms/ec-opaque/transcription/stop",
        {"instanceId": "transcription-instance"},
    )


def test_daily_from_settings_refuses_disabled_or_missing_key():
    with override_settings(DAILY_ENABLED=False):
        with pytest.raises(DailyConfigurationError, match="disabled"):
            DailyClient.from_settings()
    with override_settings(
        DAILY_ENABLED=True,
        DAILY_API_KEY="",
        DAILY_API_BASE_URL="https://api.daily.co/v1",
        DAILY_HTTP_TIMEOUT_SECONDS=5.0,
    ):
        with pytest.raises(DailyConfigurationError, match="API key"):
            DailyClient.from_settings()


def test_daily_client_rejects_nonpositive_timeout():
    with pytest.raises(DailyConfigurationError, match="timeout"):
        DailyClient("key", base_url="https://api.daily.co/v1", timeout_seconds=0)


def test_daily_webhook_hmac_verification_accepts_valid_and_rejects_invalid_or_stale():
    secret = b"webhook-test-secret"
    secret_b64 = base64.b64encode(secret).decode("ascii")
    body = b'{"type":"meeting.started"}'
    now = time.time()
    timestamp = str(now)
    signature = _signature(secret, timestamp, body)

    verify_daily_webhook(
        raw_body=body,
        signature=signature,
        timestamp=timestamp,
        secret_b64=secret_b64,
        max_age_seconds=300,
        now_epoch=now,
    )

    with pytest.raises(DailyWebhookSignatureInvalid):
        verify_daily_webhook(
            raw_body=body,
            signature="not-valid",
            timestamp=timestamp,
            secret_b64=secret_b64,
            max_age_seconds=300,
            now_epoch=now,
        )
    with pytest.raises(DailyWebhookSignatureInvalid, match="stale"):
        verify_daily_webhook(
            raw_body=body,
            signature=signature,
            timestamp=timestamp,
            secret_b64=secret_b64,
            max_age_seconds=30,
            now_epoch=now + 31,
        )
