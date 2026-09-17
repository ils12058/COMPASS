from __future__ import annotations

from compass.integrations.daily import DailyClient


class CapturingMediaClient(DailyClient):
    def __init__(self) -> None:
        super().__init__("testing-key", base_url="https://api.daily.co/v1", timeout_seconds=2.5)
        self.calls: list[tuple[str, str, dict[str, object] | None]] = []

    def _request(self, method: str, path: str, *, payload=None):
        self.calls.append((method, path, payload))
        if path.endswith(("/recordings/start", "/recordings/stop")):
            return {"status": "sent"}
        if path.endswith(("/transcription/start", "/transcription/stop")):
            return {"sent": "true"}
        return {"name": "ec-opaque", "config": payload or {}}


def test_media_rest_methods_match_current_daily_contract():
    client = CapturingMediaClient()

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
    assert client.calls[-1] == ("POST", "/rooms/ec-opaque/recordings/stop", None)

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
