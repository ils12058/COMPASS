"""Synthetic HTTP/transport and persisted capture diagnostics; no provider traffic."""

import json
import traceback
from io import BytesIO
from urllib.error import HTTPError, URLError

import pytest
from django.test import override_settings

from compass.common.json_logging import JsonFormatter
from compass.ecounseling.media import _provider_ack, start_recording, stop_media_capture
from compass.ecounseling.models import ECounselingMediaCapture
from compass.ecounseling.services import ECounselingError, create_join_credential
from compass.integrations.daily import (
    DailyClient,
    DailyFailureCode,
    DailyHTTPError,
    DailyInvalidAcknowledgment,
    DailyInvalidResponse,
    DailyTimeout,
    DailyUnavailable,
    safe_daily_failure_code,
)
from tests.test_ecounseling_media import (
    FakeMediaDailyClient,
    approve_scope,
    context,
    setup_session,
)
from tests.test_privacy_governance import auth_client

PRIVATE_VALUES = (
    "synthetic-private-bearer",
    "https://private.invalid/media?signed=synthetic-secret",
    "synthetic-student-identifier",
    "WEBVTT confidential synthetic transcript",
    "private-bucket/private-object-key",
)
PRIVATE_TEXT = " | ".join(PRIVATE_VALUES)


def assert_private_absent(text, values=PRIVATE_VALUES):
    if any(value in text for value in values):
        pytest.fail("Diagnostic privacy invariant failed", pytrace=False)


def visible_errors(error, caplog):
    return (
        str(error)
        + "".join(traceback.format_exception(error))
        + "".join(JsonFormatter().format(record) for record in caplog.records)
    )


def daily_client():
    return DailyClient("synthetic-key", base_url="https://provider.invalid/v1", timeout_seconds=1)


class Response:
    def __init__(self, raw):
        self.raw = raw

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return self.raw


@pytest.mark.parametrize(
    ("status", "body", "expected"),
    [
        (
            400,
            {"error": "invalid-request-error", "info": "No active recording."},
            "NO_ACTIVE_RECORDING",
        ),
        (
            400,
            {"error": "invalid-request-error", "info": "missing required field"},
            "INVALID_REQUEST",
        ),
        (401, {"error": PRIVATE_TEXT}, "AUTHORIZATION_REJECTED"),
        (403, {"error": PRIVATE_TEXT}, "AUTHORIZATION_REJECTED"),
        (429, {"error": PRIVATE_TEXT}, "RATE_LIMITED"),
        (500, {"error": PRIVATE_TEXT}, "SERVER_FAILURE"),
        (503, {"error": PRIVATE_TEXT}, "SERVER_FAILURE"),
        (422, {"unknown": PRIVATE_TEXT}, "UNCLASSIFIED"),
        (400, {"error": {"unknown": PRIVATE_TEXT}}, "INVALID_REQUEST"),
        (400, {"error": "invalid-request-error", "info": PRIVATE_TEXT}, "INVALID_REQUEST"),
    ],
    ids=[
        "no_active",
        "request",
        "unauthorized",
        "forbidden",
        "rate_limit",
        "server",
        "outage",
        "unknown_status",
        "unknown_shape",
        "private_reason",
    ],
)
def test_http_errors_have_closed_codes_and_safe_tracebacks(
    status, body, expected, monkeypatch, caplog
):
    body["ignored_private_fields"] = PRIVATE_TEXT

    def reject(*_args, **_kwargs):
        raise HTTPError(
            PRIVATE_VALUES[1], status, PRIVATE_TEXT, {}, BytesIO(json.dumps(body).encode())
        )

    monkeypatch.setattr("compass.integrations.daily.urlopen", reject)
    with pytest.raises(DailyHTTPError) as caught:
        daily_client().stop_recording(room_name="opaque-room", instance_id="opaque-instance")
    assert caught.value.status_code == status
    assert safe_daily_failure_code(caught.value).value == expected
    assert_private_absent(visible_errors(caught.value, caplog))


def test_no_active_hint_is_stop_specific_exact_and_bounded(monkeypatch):
    for method, body, expected in [
        (
            "start_recording",
            {"error": "invalid-request-error", "info": "no active recording"},
            "INVALID_REQUEST",
        ),
        (
            "stop_recording",
            {"error": "invalid-request-error", "info": "no active recording " + PRIVATE_TEXT},
            "INVALID_REQUEST",
        ),
        (
            "stop_recording",
            {
                "error": "invalid-request-error",
                "info": "no active recording",
                "padding": "x" * 5000,
            },
            "INVALID_REQUEST",
        ),
    ]:
        reads = []

        class Body(BytesIO):
            def read(self, size=-1, _reads=reads):
                _reads.append(size)
                return super().read(size)

        def reject(*_args, _body=body, _body_type=Body, **_kwargs):
            raise HTTPError(
                PRIVATE_VALUES[1], 400, PRIVATE_TEXT, {}, _body_type(json.dumps(_body).encode())
            )

        monkeypatch.setattr("compass.integrations.daily.urlopen", reject)
        args = {"room_name": "opaque-room", "instance_id": "opaque-instance"}
        with pytest.raises(DailyHTTPError) as caught:
            getattr(daily_client(), method)(**args)
        assert safe_daily_failure_code(caught.value).value == expected
        assert reads == ([] if method == "start_recording" else [4097])


@pytest.mark.parametrize(
    "method,info,error,expected",
    [
        (
            "stop_recording",
            "room does not have an active recording",
            "invalid-request-error",
            "NO_ACTIVE_RECORDING",
        ),
        (
            "stop_recording",
            "  ROOM DOES NOT HAVE AN ACTIVE RECORDING.  ",
            "invalid-request-error",
            "NO_ACTIVE_RECORDING",
        ),
        ("stop_recording", "no active recording", "invalid-request-error", "NO_ACTIVE_RECORDING"),
        (
            "stop_recording",
            "no active recording found",
            "invalid-request-error",
            "NO_ACTIVE_RECORDING",
        ),
        (
            "stop_recording",
            "no active recording to stop",
            "invalid-request-error",
            "NO_ACTIVE_RECORDING",
        ),
        (
            "stop_recording",
            "no recording is active",
            "invalid-request-error",
            "NO_ACTIVE_RECORDING",
        ),
        (
            "start_recording",
            "room does not have an active recording",
            "invalid-request-error",
            "INVALID_REQUEST",
        ),
        (
            "stop_transcription",
            "room does not have an active recording",
            "invalid-request-error",
            "INVALID_REQUEST",
        ),
        (
            "stop_recording",
            "room does not have an active recording",
            "different-error",
            "INVALID_REQUEST",
        ),
        (
            "stop_recording",
            "room does not have an active recording yet",
            "invalid-request-error",
            "INVALID_REQUEST",
        ),
        (
            "stop_recording",
            "prefix room does not have an active recording",
            "invalid-request-error",
            "INVALID_REQUEST",
        ),
        (
            "stop_recording",
            "room does not have an active recording..",
            "invalid-request-error",
            "INVALID_REQUEST",
        ),
    ],
)
def test_confirmed_no_active_phrase_and_existing_hints_remain_exact_and_private(
    method, info, error, expected, monkeypatch, caplog
):
    raw = json.dumps({"error": error, "info": info, "private": PRIVATE_TEXT}).encode()

    def reject(*_args, **_kwargs):
        raise HTTPError(PRIVATE_VALUES[1], 400, PRIVATE_TEXT, {}, BytesIO(raw))

    monkeypatch.setattr("compass.integrations.daily.urlopen", reject)
    args = {"room_name": "opaque-room", "instance_id": "opaque-instance"}
    with pytest.raises(DailyHTTPError) as caught:
        getattr(daily_client(), method)(**args)
    assert safe_daily_failure_code(caught.value).value == expected
    assert_private_absent(visible_errors(caught.value, caplog), (*PRIVATE_VALUES, info))


@pytest.mark.parametrize(
    "raw", [b"{broken", b"[]", b'{"error":"invalid-request-error","info":null}']
)
def test_malformed_no_active_envelopes_fail_closed(raw, monkeypatch):
    def reject(*_args, **_kwargs):
        raise HTTPError("https://provider.invalid", 400, "synthetic", {}, BytesIO(raw))

    monkeypatch.setattr("compass.integrations.daily.urlopen", reject)
    with pytest.raises(DailyHTTPError) as caught:
        daily_client().stop_recording(room_name="opaque-room", instance_id="opaque-instance")
    assert caught.value.diagnostic_code == DailyFailureCode.INVALID_REQUEST


@pytest.mark.django_db
def test_observed_no_active_http_rejection_retains_stop_intent_and_safe_audit(monkeypatch, caplog):
    from compass.audit.models import AuditEvent

    with override_settings(DAILY_ENABLED=True):
        counselor, appointment, fake = provision_recording()
        capture = start_recording(
            counselor=counselor,
            appointment_id=appointment.pk,
            context=context(counselor),
            daily_client=fake,
        )

        def reject(*_args, **_kwargs):
            raw = json.dumps(
                {
                    "error": "invalid-request-error",
                    "info": "room does not have an active recording",
                    "private": PRIVATE_TEXT,
                }
            ).encode()
            raise HTTPError(PRIVATE_VALUES[1], 400, PRIVATE_TEXT, {}, BytesIO(raw))

        monkeypatch.setattr("compass.integrations.daily.urlopen", reject)
        with pytest.raises(ECounselingError) as caught:
            stop_media_capture(
                counselor=counselor,
                appointment_id=appointment.pk,
                kind="RECORDING",
                context=context(counselor),
                daily_client=daily_client(),
            )
    capture.refresh_from_db()
    assert capture.status == "STOP_REQUESTED" and capture.stop_requested_at
    assert capture.error_code == "STOP_PROVIDER_NO_ACTIVE_RECORDING"
    assert capture.ended_at is None and capture.ready_at is None and len(fake.recording_starts) == 1
    assert_private_absent(visible_errors(caught.value, caplog))
    for event in AuditEvent.objects.filter(target_id=str(capture.pk)):
        assert_private_absent(json.dumps(event.metadata))


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (URLError(PRIVATE_TEXT), "TRANSPORT_FAILURE"),
        (ConnectionError(PRIVATE_TEXT), "TRANSPORT_FAILURE"),
        (TimeoutError(PRIVATE_TEXT), "TIMEOUT"),
        (URLError(TimeoutError(PRIVATE_TEXT)), "TIMEOUT"),
    ],
    ids=["url_connection", "connection", "timeout", "wrapped_timeout"],
)
def test_transport_failure_and_timeout_are_safe_distinct_unknown_outcomes(
    error, expected, monkeypatch, caplog
):
    def unavailable(*_args, **_kwargs):
        raise error

    monkeypatch.setattr("compass.integrations.daily.urlopen", unavailable)
    with pytest.raises(DailyUnavailable) as caught:
        daily_client().stop_recording(room_name="opaque-room", instance_id="opaque-instance")
    assert safe_daily_failure_code(caught.value).value == expected
    assert_private_absent(visible_errors(caught.value, caplog))


@pytest.mark.parametrize(
    "raw", [b"not-json", b"[]", b"null", b"\xff"], ids=["malformed", "array", "null", "encoding"]
)
def test_invalid_json_and_response_shapes_are_classified(raw, monkeypatch, caplog):
    monkeypatch.setattr(
        "compass.integrations.daily.urlopen", lambda *_args, **_kwargs: Response(raw)
    )
    with pytest.raises(DailyInvalidResponse) as caught:
        daily_client().stop_recording(room_name="opaque-room", instance_id="opaque-instance")
    assert safe_daily_failure_code(caught.value) == DailyFailureCode.INVALID_RESPONSE
    assert_private_absent(visible_errors(caught.value, caplog))


@pytest.mark.parametrize(
    "payload",
    [{"status": "sent"}, {"sent": "true"}, {"sent": True}],
    ids=["recording", "transcription", "legacy_boolean"],
)
def test_documented_acknowledgments_still_work(payload, monkeypatch):
    monkeypatch.setattr(
        "compass.integrations.daily.urlopen",
        lambda *_args, **_kwargs: Response(json.dumps(payload).encode()),
    )
    _provider_ack(
        daily_client().stop_recording(room_name="opaque-room", instance_id="opaque-instance")
    )


@pytest.mark.parametrize(
    "payload",
    [
        {},
        None,
        [],
        {"status": "stopped"},
        {"sent": []},
        {"sent": {}},
        {"sent": 1},
        {"status": "sent", "sent": False},
        {"status": "sent", "error": PRIVATE_TEXT},
    ],
    ids=[
        "missing",
        "null",
        "array",
        "wrong_status",
        "list_field",
        "object_field",
        "numeric_field",
        "conflict",
        "private_error",
    ],
)
def test_missing_invalid_and_contradictory_acknowledgments_remain_unconfirmed(payload):
    with pytest.raises(DailyInvalidAcknowledgment) as caught:
        _provider_ack(payload)
    assert safe_daily_failure_code(caught.value) == DailyFailureCode.INVALID_ACKNOWLEDGMENT
    assert_private_absent(str(caught.value))


def test_injected_unknown_diagnostic_values_cannot_escape_allowlist():
    error = DailyHTTPError(400, diagnostic_code=PRIVATE_TEXT)
    assert safe_daily_failure_code(error) == DailyFailureCode.UNCLASSIFIED
    error.diagnostic_code = PRIVATE_TEXT
    assert safe_daily_failure_code(error) == DailyFailureCode.UNCLASSIFIED
    assert safe_daily_failure_code(RuntimeError(PRIVATE_TEXT)) == DailyFailureCode.UNCLASSIFIED


def provision_recording():
    _, student, counselor, appointment = setup_session()
    approve_scope(
        student=student, counselor=counselor, appointment=appointment, scope="AUDIO_VIDEO_RECORDING"
    )
    fake = FakeMediaDailyClient()
    create_join_credential(
        actor=counselor,
        appointment_id=appointment.pk,
        context=context(counselor),
        daily_client=fake,
    )
    return counselor, appointment, fake


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (DailyHTTPError(400), "ERROR", "INVALID_REQUEST"),
        (DailyHTTPError(429), "ERROR", "RATE_LIMITED"),
        (DailyHTTPError(503), "ERROR", "SERVER_FAILURE"),
        (DailyTimeout(PRIVATE_TEXT), "START_REQUESTED", "TIMEOUT"),
        (DailyInvalidAcknowledgment(PRIVATE_TEXT), "START_REQUESTED", "INVALID_ACKNOWLEDGMENT"),
    ],
    ids=["request", "limit", "server", "timeout", "ack"],
)
def test_start_diagnostics_preserve_existing_lifecycle_policy(error, status, code, monkeypatch):
    with override_settings(DAILY_ENABLED=True):
        counselor, appointment, fake = provision_recording()

        def reject(**_kwargs):
            raise error

        monkeypatch.setattr(fake, "start_recording", reject)
        with pytest.raises(ECounselingError) as caught:
            start_recording(
                counselor=counselor,
                appointment_id=appointment.pk,
                context=context(counselor),
                daily_client=fake,
            )
    capture = ECounselingMediaCapture.objects.get(room__appointment=appointment, kind="RECORDING")
    assert capture.status == status
    assert capture.error_code == f"START_PROVIDER_{code}"
    assert capture.ready_at is None and capture.ended_at is None
    assert_private_absent(str(caught.value))


@pytest.mark.django_db
@pytest.mark.parametrize(
    "error",
    [
        DailyHTTPError(400, diagnostic_code=DailyFailureCode.NO_ACTIVE_RECORDING),
        DailyHTTPError(403),
        DailyHTTPError(429),
        DailyHTTPError(503),
        DailyTimeout(PRIVATE_TEXT),
        DailyInvalidAcknowledgment(PRIVATE_TEXT),
    ],
    ids=["no_active", "authorization", "limit", "server", "timeout", "ack"],
)
def test_stop_rejection_never_establishes_cessation_or_replays_commands(error, monkeypatch):
    with override_settings(DAILY_ENABLED=True):
        counselor, appointment, fake = provision_recording()
        capture = start_recording(
            counselor=counselor,
            appointment_id=appointment.pk,
            context=context(counselor),
            daily_client=fake,
        )
        starts = len(fake.recording_starts)
        calls = []

        def reject(**_kwargs):
            calls.append("STOP")
            raise error

        monkeypatch.setattr(fake, "stop_recording", reject)
        with pytest.raises(ECounselingError):
            stop_media_capture(
                counselor=counselor,
                appointment_id=appointment.pk,
                kind="RECORDING",
                context=context(counselor),
                daily_client=fake,
            )
    capture.refresh_from_db()
    assert capture.status == "STOP_REQUESTED"
    assert capture.error_code == f"STOP_PROVIDER_{safe_daily_failure_code(error)}"
    assert capture.ended_at is None and capture.ready_at is None
    assert calls == ["STOP"] and len(fake.recording_starts) == starts


@pytest.mark.django_db
def test_provider_authorization_error_keeps_public_api_sanitized_and_does_not_become_account_denial(
    monkeypatch,
):
    with override_settings(DAILY_ENABLED=True):
        counselor, appointment, fake = provision_recording()

        def reject(**_kwargs):
            raise DailyHTTPError(403)

        monkeypatch.setattr(fake, "start_recording", reject)
        monkeypatch.setattr(DailyClient, "from_settings", classmethod(lambda _cls: fake))
        response = auth_client(counselor).post(
            f"/api/v1/e-counseling/appointments/{appointment.pk}/recording/start",
            data={},
            content_type="application/json",
        )
    assert response.status_code == 503
    assert_private_absent(response.content.decode())
    assert "AUTHORIZATION_REJECTED" not in response.content.decode()
