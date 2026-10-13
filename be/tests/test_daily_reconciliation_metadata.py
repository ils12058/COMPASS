"""Only the documented bound-ID GET seam, with fake HTTP and bounded metadata bodies."""

import json
from io import BytesIO
from urllib.error import HTTPError

import pytest

from compass.integrations.daily import (
    DailyClient,
    DailyHTTPError,
    DailyInvalidResponse,
    DailyTimeout,
)
from tests.test_daily_diagnostics import PRIVATE_TEXT, assert_private_absent


class Response:
    def __init__(self, body):
        self.body = BytesIO(body)
        self.read_sizes = []
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.closed = True

    def read(self, size):
        self.read_sizes.append(size)
        return self.body.read(size)


def client():
    return DailyClient("synthetic-key", base_url="https://api.daily.co/v1", timeout_seconds=9)


@pytest.mark.parametrize(
    ("kind", "collection"), [("RECORDING", "recordings"), ("TRANSCRIPTION", "transcript")]
)
def test_capture_metadata_uses_get_encoded_bound_id_and_bounded_timeout_and_body(
    kind, collection, monkeypatch
):
    response = Response(
        json.dumps({"status": "finished" if kind == "RECORDING" else "t_finished"}).encode()
    )
    calls = []

    def open_fake(request, *, timeout):
        calls.append((request.get_method(), request.full_url, request.data, timeout))
        return response

    monkeypatch.setattr("compass.integrations.daily.urlopen", open_fake)
    item = client().get_capture_metadata(kind=kind, artifact_id="synthetic/id?x", timeout_seconds=5)
    assert item["status"] in ("finished", "t_finished")
    assert calls == [("GET", f"https://api.daily.co/v1/{collection}/synthetic%2Fid%3Fx", None, 5)]
    assert response.read_sizes == [65537] and response.closed


def test_metadata_timeout_cannot_exceed_the_existing_daily_timeout(monkeypatch):
    response = Response(b"{}")
    timeouts = []

    def open_fake(_request, *, timeout):
        timeouts.append(timeout)
        return response

    monkeypatch.setattr("compass.integrations.daily.urlopen", open_fake)
    smaller = DailyClient("synthetic-key", base_url="https://api.daily.co/v1", timeout_seconds=1)
    smaller.get_capture_metadata(kind="RECORDING", artifact_id="synthetic", timeout_seconds=5)
    assert timeouts == [1]


@pytest.mark.parametrize("body", [b"x" * 65537, b"not json", b"[]", b"null"])
def test_oversize_or_nonobject_metadata_is_sanitized_and_response_closed(body, monkeypatch):
    response = Response(body)
    monkeypatch.setattr("compass.integrations.daily.urlopen", lambda *_args, **_kwargs: response)
    with pytest.raises(DailyInvalidResponse) as exc:
        client().get_capture_metadata(
            kind="TRANSCRIPTION", artifact_id="synthetic", timeout_seconds=5
        )
    assert response.closed and response.read_sizes == [65537]
    assert_private_absent(str(exc.value))


@pytest.mark.parametrize("status", [400, 404, 429, 500, 503])
def test_metadata_http_failures_do_not_inspect_raw_body_or_classify_no_active_as_completion(
    status, monkeypatch
):
    body = BytesIO(PRIVATE_TEXT.encode())
    error = HTTPError(
        "https://api.daily.co/v1/recordings/synthetic", status, PRIVATE_TEXT, {}, body
    )

    def reject(*_args, **_kwargs):
        raise error

    monkeypatch.setattr("compass.integrations.daily.urlopen", reject)
    with pytest.raises(DailyHTTPError) as exc:
        client().get_capture_metadata(kind="RECORDING", artifact_id="synthetic", timeout_seconds=5)
    assert exc.value.status_code == status and body.closed
    assert exc.value.diagnostic_code != "NO_ACTIVE_RECORDING"
    assert_private_absent(str(exc.value))


def test_metadata_transport_timeout_remains_a_closed_failure(monkeypatch):
    def reject(*_args, **_kwargs):
        raise TimeoutError(PRIVATE_TEXT)

    monkeypatch.setattr("compass.integrations.daily.urlopen", reject)
    with pytest.raises(DailyTimeout) as exc:
        client().get_capture_metadata(kind="RECORDING", artifact_id="synthetic", timeout_seconds=5)
    assert exc.value.diagnostic_code == "TIMEOUT"
    assert_private_absent(str(exc.value))


@pytest.mark.parametrize(
    ("kind", "artifact", "timeout"),
    [
        ("unknown", "synthetic", 5),
        (["RECORDING"], "synthetic", 5),
        ("RECORDING", None, 5),
        ("RECORDING", "", 5),
        ("RECORDING", "x" * 161, 5),
        ("RECORDING", "synthetic", 0),
        ("RECORDING", "synthetic", 6),
        ("RECORDING", "synthetic", True),
        ("RECORDING", "synthetic", "raw"),
    ],
)
def test_invalid_capture_metadata_request_fails_before_external_io(
    kind, artifact, timeout, monkeypatch
):
    def forbidden(*_args, **_kwargs):
        pytest.fail("Invalid metadata request reached HTTP.", pytrace=False)

    monkeypatch.setattr("compass.integrations.daily.urlopen", forbidden)
    with pytest.raises(DailyInvalidResponse):
        client().get_capture_metadata(kind=kind, artifact_id=artifact, timeout_seconds=timeout)
