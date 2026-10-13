"""Official event shapes and bounded numerical evidence, without provider/DB operations."""

from copy import deepcopy

import pytest

from compass.ecounseling.webhook_events import InvalidEvent, validate_event


def payload(kind="recording", phase="started"):
    if kind == "recording":
        result = {"recording_id": "artifact-a", "instance_id": "instance-a", "start_ts": 1700000000}
        if phase != "started":
            result["room_name"] = "room-a"
        if phase == "ready-to-download":
            result.update(status="finished", duration=5)
        if phase == "error":
            result["timestamp"] = "1700000005"
        return result
    return {
        "id": "artifact-a",
        "info": {"instanceId": "instance-a"},
        "room_name": "room-a",
        "room_id": "room-id-a",
        "mtg_session_id": "session-a",
        "status": {
            "started": "t_in_progress",
            "ready-to-download": "t_finished",
            "error": "t_error",
        }[phase],
        "duration": 0 if phase == "started" else 5.5,
    }


def parse(data=None, *, kind="recording", phase="started", **kwargs):
    return validate_event(
        event_type=f"{kind}.{phase}",
        event_id=kwargs.get("event_id", "event-a"),
        event_ts=kwargs.get("event_ts", 1700000010.5),
        payload=payload(kind, phase) if data is None else data,
    )


@pytest.mark.parametrize("kind", ["recording", "transcript"])
@pytest.mark.parametrize("phase", ["started", "ready-to-download", "error"])
def test_documented_media_shapes_normalize_only_allowlisted_evidence(kind, phase):
    data = payload(kind, phase)
    data.update(
        error="private prose",
        out_params={"s3": {"key": "private location"}},
        share_token="private token",
    )
    event = parse(data, kind=kind, phase=phase)
    assert event.identity.artifact_id == "artifact-a"
    assert event.started == (phase == "started")
    assert event.completion == (phase == "ready-to-download")
    assert "private" not in repr(event) and not hasattr(event, "raw_payload")


@pytest.mark.parametrize(
    "value",
    [
        float("nan"),
        float("inf"),
        -float("inf"),
        -1,
        True,
        False,
        "5",
        "NaN",
        "infinity",
        None,
        [],
        {},
        10**1000,
        604801,
    ],
)
@pytest.mark.parametrize("kind", ["recording", "transcript"])
def test_invalid_duration_never_enters_normalized_evidence(kind, value):
    data = payload(kind, "ready-to-download")
    data["duration"] = value
    with pytest.raises(InvalidEvent):
        parse(data, kind=kind, phase="ready-to-download")


@pytest.mark.parametrize(
    "value",
    [
        float("nan"),
        float("inf"),
        -float("inf"),
        -1,
        True,
        "1700000000",
        None,
        {},
        [],
        10**1000,
        253402300800,
    ],
)
def test_dispatch_time_is_bounded_numeric_and_never_falls_back(value):
    with pytest.raises(InvalidEvent):
        parse(event_ts=value)


@pytest.mark.parametrize(
    "value", [None, False, -1, float("nan"), float("inf"), 1700000000.5, "1700000000", 10**1000]
)
def test_recording_start_time_rejects_invalid_integer_epoch(value):
    data = payload()
    data["start_ts"] = value
    with pytest.raises(InvalidEvent):
        parse(data)


@pytest.mark.parametrize(
    "kind,key",
    [
        ("recording", "recording_id"),
        ("recording", "instance_id"),
        ("transcript", "id"),
        ("transcript", "room_name"),
        ("transcript", "mtg_session_id"),
    ],
)
@pytest.mark.parametrize("value", [None, "", True, 12, [], {}, "x" * 161])
def test_required_identity_rejects_null_empty_wrong_type_or_oversize(kind, key, value):
    data = payload(kind)
    data[key] = value
    with pytest.raises(InvalidEvent):
        parse(data, kind=kind)


@pytest.mark.parametrize(
    "info", [None, [], "instance-a", 1, {"instanceId": None}, {"instanceId": {}}, {}]
)
def test_transcript_start_needs_documented_nested_instance(info):
    data = payload("transcript")
    data["info"] = info
    with pytest.raises(InvalidEvent):
        parse(data, kind="transcript")


@pytest.mark.parametrize("kind", ["recording", "transcript"])
@pytest.mark.parametrize("status", [None, "unknown", "t_error", 12, True, {}])
def test_supplied_completion_status_must_match_documented_event(kind, status):
    data = payload(kind, "ready-to-download")
    data["status"] = status
    with pytest.raises(InvalidEvent):
        parse(data, kind=kind, phase="ready-to-download")


def test_recording_error_accepts_only_documented_decimal_integer_text_exception():
    event = parse(kind="recording", phase="error")
    assert event.occurred_at.timestamp() == 1700000005
    for value in ("1.5", "NaN", "-1", "١٢٣", "1" * 100):
        data = payload("recording", "error")
        data["timestamp"] = value
        with pytest.raises(InvalidEvent):
            parse(data, phase="error")


def test_missing_optional_media_times_are_unknown_and_dispatch_is_separate():
    data = payload()
    data.pop("start_ts")
    event = parse(data)
    assert event.started_at is None and event.occurred_at is None
    assert parse(kind="transcript").started_at is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("instanceId", "other"),
        ("roomName", "other"),
        ("kind", "TRANSCRIPTION"),
        ("startTs", -1),
        ("endTs", float("inf")),
    ],
)
def test_contradictory_aliases_or_invalid_nested_observations_are_rejected(field, value):
    data = deepcopy(payload())
    if field in ("startTs", "endTs"):
        data["info"] = {field: value}
    else:
        data[field] = value
        if field == "roomName":
            data["room_name"] = "room-a"
    with pytest.raises(InvalidEvent):
        parse(data)


@pytest.mark.parametrize("phase", ["started", "ended"])
def test_meeting_events_describe_meeting_times_without_capture_evidence(phase):
    event = validate_event(
        event_type=f"meeting.{phase}",
        event_id="meeting-event",
        event_ts=1700000020,
        payload={
            "room": "room-a",
            "meeting_id": "session-a",
            "start_ts": 1700000000.5,
            "end_ts": 1700000010.5,
        },
    )
    assert event.identity.kind == "MEETING" and not event.completion
