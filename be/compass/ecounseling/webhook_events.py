"""Bounded allowlisted event evidence. Never keep raw payload, error prose or media locations."""

import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime

from .provider_identity import ProviderIdentity

MEDIA_WEBHOOK_TYPES = frozenset(
    f"{kind}.{phase}"
    for kind in ("recording", "transcript")
    for phase in ("started", "ready-to-download", "error")
)
MEETING_WEBHOOK_TYPES = frozenset({"meeting.started", "meeting.ended"})
MAX_DURATION_SECONDS = 7 * 86400  # Defensive COMPASS bound, not a claimed Daily limit.
MAX_EPOCH_SECONDS = 253402300799
MAX_WEBHOOK_BYTES = 64 * 1024
_IDENTIFIER = re.compile(r"[A-Za-z0-9_.:/-]+\Z")


class InvalidEvent(ValueError):
    def __init__(self):
        super().__init__("Daily webhook event evidence is invalid.")


def identifier(value, *, maximum=160):
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= maximum
        or not _IDENTIFIER.fullmatch(value)
    ):
        raise InvalidEvent()
    return value


def finite_number(value, *, maximum, integer=False):
    if type(value) not in (int, float) or value < 0 or value > maximum:
        raise InvalidEvent()
    if not math.isfinite(value) or (integer and type(value) is not int):
        raise InvalidEvent()
    return value


def event_time(value, *, integer=False, decimal_text=False):
    if (
        decimal_text
        and isinstance(value, str)
        and 1 <= len(value) <= 12
        and value.isascii()
        and value.isdecimal()
    ):
        value = int(value)
    value = finite_number(value, maximum=MAX_EPOCH_SECONDS, integer=integer)
    try:
        return datetime.fromtimestamp(value, UTC)
    except (OverflowError, ValueError, OSError):
        raise InvalidEvent() from None


def _optional_id(payload, key, *, maximum=160):
    return identifier(payload[key], maximum=maximum) if key in payload else None


def _aliases(payload, keys, *, maximum=160):
    values = [_optional_id(payload, key, maximum=maximum) for key in keys if key in payload]
    if values and any(value != values[0] for value in values):
        raise InvalidEvent()
    return values[0] if values else None


@dataclass(frozen=True, repr=False)
class ValidatedEvent:
    event_type: str
    event_id: str
    dispatch_at: datetime
    identity: ProviderIdentity
    status: str | None = None
    started_at: datetime | None = None
    occurred_at: datetime | None = None
    duration: float | None = None

    @property
    def completion(self):
        return self.event_type.endswith(".ready-to-download")

    @property
    def started(self):
        return self.event_type.endswith(".started")


def validate_event(*, event_type, event_id, event_ts, payload):
    event_id = identifier(event_id)
    dispatch_at = event_time(event_ts)
    if not isinstance(payload, dict):
        raise InvalidEvent()
    if event_type in MEETING_WEBHOOK_TYPES:
        room = identifier(payload.get("room"), maximum=128)
        session = identifier(payload.get("meeting_id"))
        started_at = event_time(payload.get("start_ts"))
        occurred_at = (
            event_time(payload.get("end_ts")) if event_type.endswith(".ended") else started_at
        )
        if occurred_at < started_at:
            raise InvalidEvent()
        return ValidatedEvent(
            event_type,
            event_id,
            dispatch_at,
            ProviderIdentity("MEETING", room_name=room, session_id=session),
            started_at=started_at,
            occurred_at=occurred_at,
        )
    if event_type not in MEDIA_WEBHOOK_TYPES:
        raise InvalidEvent()
    recording = event_type.startswith("recording.")
    kind = "RECORDING" if recording else "TRANSCRIPTION"
    phase = event_type.rsplit(".", 1)[1]
    info = payload.get("info", {})
    if not isinstance(info, dict):
        raise InvalidEvent()
    instance = _aliases(payload, ("instance_id", "instanceId"))
    nested_instance = _optional_id(info, "instanceId")
    if instance and nested_instance and instance != nested_instance:
        raise InvalidEvent()
    instance = instance or nested_instance
    if phase in ("started", "error") and not instance:
        raise InvalidEvent()
    if not recording and phase in ("started", "error") and not nested_instance:
        raise InvalidEvent()
    artifact = _optional_id(payload, "recording_id" if recording else "id")
    if (phase != "error" or not recording) and not artifact:
        raise InvalidEvent()
    room_name = _aliases(payload, ("room_name", "roomName", "room"), maximum=128)
    room_id = _aliases(payload, ("room_id", "roomId"), maximum=128)
    session = _aliases(payload, ("mtg_session_id", "mtgSessionId"))
    if not (recording and phase == "started") and not room_name:
        raise InvalidEvent()
    if not recording and not session:
        raise InvalidEvent()
    if "kind" in payload and payload["kind"] != kind:
        raise InvalidEvent()
    expected_status = (
        (
            "finished"
            if phase == "ready-to-download"
            else "in-progress"
            if phase == "started"
            else None
        )
        if recording
        else {"started": "t_in_progress", "ready-to-download": "t_finished", "error": "t_error"}[
            phase
        ]
    )
    status = payload.get("status")
    if "status" in payload and (not isinstance(status, str) or status != expected_status):
        raise InvalidEvent()
    started_at = event_time(payload["start_ts"], integer=True) if "start_ts" in payload else None
    nested_start = event_time(info["startTs"], integer=True) if "startTs" in info else None
    nested_end = event_time(info["endTs"], integer=True) if "endTs" in info else None
    if started_at and nested_start and started_at != nested_start:
        raise InvalidEvent()
    # Validate supplied observations, but trust media timing only where documented for this event.
    started_at = (
        started_at
        if recording and phase in ("started", "ready-to-download")
        else nested_start
        if not recording and phase == "error"
        else None
    )
    if started_at and started_at > dispatch_at:
        raise InvalidEvent()
    if nested_start and nested_end and nested_end < nested_start:
        raise InvalidEvent()
    duration = (
        finite_number(
            payload["duration"],
            maximum=MAX_DURATION_SECONDS,
            integer=recording or phase == "started",
        )
        if "duration" in payload
        else None
    )
    if recording and phase == "ready-to-download" and duration == 0:
        raise InvalidEvent()
    if (
        started_at
        and duration is not None
        and started_at.timestamp() + duration > MAX_EPOCH_SECONDS
    ):
        raise InvalidEvent()
    occurred_at = (
        event_time(payload["timestamp"], integer=True, decimal_text=True)
        if recording and "timestamp" in payload
        else None
    )
    if occurred_at and occurred_at > dispatch_at:
        raise InvalidEvent()
    if not (recording and phase == "error"):
        occurred_at = None
    if phase == "started":
        occurred_at = started_at
    return ValidatedEvent(
        event_type,
        event_id,
        dispatch_at,
        ProviderIdentity(kind, artifact, instance, room_name, room_id, session),
        status,
        started_at,
        occurred_at,
        duration,
    )
