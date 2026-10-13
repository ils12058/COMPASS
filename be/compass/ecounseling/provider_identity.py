"""Equivalent binding rules for signed events and metadata; no provider discovery."""

from dataclasses import dataclass


@dataclass(frozen=True, repr=False)
class ProviderIdentity:
    kind: str
    artifact_id: str | None = None
    instance_id: str | None = None
    room_name: str | None = None
    room_id: str | None = None
    session_id: str | None = None


def identity_conflict(
    identity,
    *,
    kind,
    room_name,
    room_id,
    instance_id,
    artifact_id,
    session_id,
    require_instance=False,
    require_artifact=False,
    require_room_name=False,
    require_room_id=False,
    require_known_session=False,
):
    """Return a closed reason. Absence never invents or replaces an existing binding."""
    if identity.kind != kind:
        return "KIND_MISMATCH"
    for supplied, expected, code in (
        (identity.room_name, room_name, "ROOM_MISMATCH"),
        (identity.room_id, room_id, "ROOM_MISMATCH"),
        (identity.instance_id, instance_id, "INSTANCE_MISMATCH"),
        (identity.artifact_id, artifact_id, "ARTIFACT_MISMATCH"),
        (identity.session_id, session_id, "SESSION_MISMATCH"),
    ):
        if supplied is not None and expected and supplied != expected:
            return code
    for required, supplied, expected in (
        (require_instance, identity.instance_id, instance_id),
        (require_artifact, identity.artifact_id, artifact_id),
        (require_room_name, identity.room_name, room_name),
        (require_room_id, identity.room_id, room_id),
        (require_known_session and bool(session_id), identity.session_id, session_id),
    ):
        if required and (not expected or supplied != expected):
            return "IDENTITY_INSUFFICIENT"
    return None


def capture_identity_conflict(capture, identity, **requirements):
    return identity_conflict(
        identity,
        kind=capture.kind,
        room_name=capture.room.daily_room_name,
        room_id=capture.room.daily_room_id,
        instance_id=capture.provider_instance_id,
        artifact_id=capture.provider_artifact_id,
        session_id=capture.provider_session_id,
        **requirements,
    )
