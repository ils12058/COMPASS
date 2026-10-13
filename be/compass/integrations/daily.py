"""Narrow Daily.co REST and webhook-signature integration boundary."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import math
import time
from enum import StrEnum
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from django.conf import settings

logger = logging.getLogger("compass.daily")


class DailyFailureCode(StrEnum):
    NOT_CONFIGURED = "NOT_CONFIGURED"
    NO_ACTIVE_RECORDING = "NO_ACTIVE_RECORDING"
    INVALID_REQUEST = "INVALID_REQUEST"
    AUTHORIZATION_REJECTED = "AUTHORIZATION_REJECTED"
    RATE_LIMITED = "RATE_LIMITED"
    SERVER_FAILURE = "SERVER_FAILURE"
    TRANSPORT_FAILURE = "TRANSPORT_FAILURE"
    TIMEOUT = "TIMEOUT"
    INVALID_RESPONSE = "INVALID_RESPONSE"
    INVALID_ACKNOWLEDGMENT = "INVALID_ACKNOWLEDGMENT"
    UNCLASSIFIED = "UNCLASSIFIED"


def _http_failure_code(status_code, raw=b"", *, recording_stop=False):
    if status_code == 400:
        # Daily documents error/info, but not a stable no-active machine code. Match only these
        # short exact reason hints at recording Stop. Other prose/variants fall back to HTTP 400;
        # never retain the body/info or infer recording cessation from this rejection.
        if recording_stop and len(raw) <= 4096:
            try:
                payload = json.loads(raw)
            except (ValueError, TypeError, UnicodeDecodeError):
                payload = None
            if isinstance(payload, dict) and payload.get("error") == "invalid-request-error":
                info = payload.get("info")
                if isinstance(info, str) and info.casefold().strip().removesuffix(".") in {
                    "no active recording",
                    "no active recording found",
                    "no active recording to stop",
                    "no recording is active",
                }:
                    return DailyFailureCode.NO_ACTIVE_RECORDING
        return DailyFailureCode.INVALID_REQUEST
    if status_code in {401, 403}:
        return DailyFailureCode.AUTHORIZATION_REJECTED
    if status_code == 429:
        return DailyFailureCode.RATE_LIMITED
    if 500 <= status_code <= 599:
        return DailyFailureCode.SERVER_FAILURE
    return DailyFailureCode.UNCLASSIFIED


class DailyError(RuntimeError):
    """Base error for sanitized Daily integration failures."""

    diagnostic_code = DailyFailureCode.UNCLASSIFIED


class DailyConfigurationError(DailyError):
    diagnostic_code = DailyFailureCode.NOT_CONFIGURED


class DailyUnavailable(DailyError):
    diagnostic_code = DailyFailureCode.TRANSPORT_FAILURE


class DailyTimeout(DailyUnavailable):
    diagnostic_code = DailyFailureCode.TIMEOUT


class DailyHTTPError(DailyError):
    def __init__(self, status_code: int, *, diagnostic_code=None) -> None:
        self.status_code = (
            status_code if isinstance(status_code, int) and 100 <= status_code <= 599 else 0
        )
        super().__init__(f"Daily returned HTTP {self.status_code}.")
        try:
            self.diagnostic_code = (
                _http_failure_code(self.status_code)
                if diagnostic_code is None
                else DailyFailureCode(diagnostic_code)
            )
        except (ValueError, TypeError):
            self.diagnostic_code = DailyFailureCode.UNCLASSIFIED


class DailyInvalidResponse(DailyError):
    diagnostic_code = DailyFailureCode.INVALID_RESPONSE


class DailyInvalidAcknowledgment(DailyInvalidResponse):
    diagnostic_code = DailyFailureCode.INVALID_ACKNOWLEDGMENT


def safe_daily_failure_code(error: Exception) -> DailyFailureCode:
    """Only closed codes cross the diagnostic boundary, including injected adapter errors."""
    if isinstance(error, DailyError):
        try:
            return DailyFailureCode(error.diagnostic_code)
        except (ValueError, TypeError):
            pass
    return DailyFailureCode.UNCLASSIFIED


def _log_request_failure(method, code, status_code=None):
    logger.warning(
        "Daily request failed",
        extra={
            "event": "daily_request_failed",
            "operation": method if method in {"GET", "POST", "DELETE"} else "UNKNOWN",
            "failure_code": code.value,
            "status_code": status_code,
        },
    )


class DailyWebhookSignatureInvalid(DailyError):
    pass


class DailyClient:
    def __init__(self, api_key: str, *, base_url: str, timeout_seconds: float) -> None:
        if not api_key:
            raise DailyConfigurationError("Daily API key is required.")
        if not base_url:
            raise DailyConfigurationError("Daily API base URL is required.")
        if timeout_seconds <= 0:
            raise DailyConfigurationError("Daily HTTP timeout must be positive.")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    @classmethod
    def from_settings(cls) -> DailyClient:
        if not settings.DAILY_ENABLED:
            raise DailyConfigurationError("Daily is disabled.")
        return cls(
            settings.DAILY_API_KEY,
            base_url=settings.DAILY_API_BASE_URL,
            timeout_seconds=settings.DAILY_HTTP_TIMEOUT_SECONDS,
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, object] | None = None,
    ) -> dict[str, object]:
        body = (
            None if payload is None else json.dumps(payload, separators=(",", ":")).encode("utf-8")
        )
        request = Request(
            f"{self.base_url}{path}",
            data=body,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method=method,
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read()
        except HTTPError as exc:
            raw = b""
            recording_stop = method == "POST" and path.endswith("/recordings/stop")
            try:
                if exc.code == 400 and recording_stop:
                    raw = exc.read(4097)
            except Exception:
                # Failure to inspect a bounded reason does not erase the received HTTP status.
                pass
            finally:
                try:
                    exc.close()
                except Exception:
                    pass
            error = DailyHTTPError(
                exc.code,
                diagnostic_code=_http_failure_code(exc.code, raw, recording_stop=recording_stop),
            )
            _log_request_failure(method, safe_daily_failure_code(error), error.status_code)
            raise error from None
        except (URLError, TimeoutError, OSError) as exc:
            reason = exc.reason if isinstance(exc, URLError) else exc
            error = (
                DailyTimeout("Daily request timed out; the operation outcome is unknown.")
                if isinstance(reason, TimeoutError)
                else DailyUnavailable("Daily is temporarily unavailable.")
            )
            _log_request_failure(method, safe_daily_failure_code(error))
            raise error from None

        try:
            decoded = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
            _log_request_failure(method, DailyFailureCode.INVALID_RESPONSE)
            raise DailyInvalidResponse("Daily returned an invalid JSON response.") from None
        if not isinstance(decoded, dict):
            _log_request_failure(method, DailyFailureCode.INVALID_RESPONSE)
            raise DailyInvalidResponse("Daily returned an unexpected response shape.")
        return decoded

    def create_room(self, *, room_name: str, expires_at_epoch: int) -> dict[str, object]:
        return self._request(
            "POST",
            "/rooms",
            payload={
                "name": room_name,
                "privacy": "private",
                "properties": {
                    "exp": expires_at_epoch,
                    "eject_at_room_exp": False,
                    "max_participants": 2,
                    "enable_chat": False,
                    "enable_screenshare": False,
                    "enable_live_captions_ui": False,
                    "enable_transcription_storage": False,
                    "enforce_unique_user_ids": True,
                },
            },
        )

    def get_room(self, *, room_name: str) -> dict[str, object]:
        return self._request("GET", f"/rooms/{quote(room_name, safe='')}")

    def update_room(
        self,
        *,
        room_name: str,
        properties: dict[str, object],
    ) -> dict[str, object]:
        return self._request(
            "POST",
            f"/rooms/{quote(room_name, safe='')}",
            payload={"properties": properties},
        )

    def start_recording(self, *, room_name: str, instance_id: str) -> dict[str, object]:
        return self._request(
            "POST",
            f"/rooms/{quote(room_name, safe='')}/recordings/start",
            payload={"instanceId": instance_id, "type": "cloud"},
        )

    def stop_recording(self, *, room_name: str) -> dict[str, object]:
        # Current Daily REST semantics stop the active room recording and accept no instanceId body.
        return self._request(
            "POST",
            f"/rooms/{quote(room_name, safe='')}/recordings/stop",
        )

    def start_transcription(self, *, room_name: str, instance_id: str) -> dict[str, object]:
        return self._request(
            "POST",
            f"/rooms/{quote(room_name, safe='')}/transcription/start",
            payload={"instanceId": instance_id},
        )

    def stop_transcription(self, *, room_name: str, instance_id: str) -> dict[str, object]:
        return self._request(
            "POST",
            f"/rooms/{quote(room_name, safe='')}/transcription/stop",
            payload={"instanceId": instance_id},
        )

    def create_meeting_token(
        self,
        *,
        room_name: str,
        user_id: str,
        user_name: str,
        expires_at_epoch: int,
    ) -> str:
        payload = self._request(
            "POST",
            "/meeting-tokens",
            payload={
                "properties": {
                    "room_name": room_name,
                    "exp": expires_at_epoch,
                    "eject_at_token_exp": False,
                    "user_id": user_id,
                    "user_name": user_name,
                    "is_owner": False,
                    "enable_screenshare": False,
                    "enable_live_captions_ui": False,
                    "enable_recording_ui": False,
                    "start_cloud_recording": False,
                    "auto_start_transcription": False,
                    "permissions": {"canAdmin": False},
                }
            },
        )
        token = payload.get("token")
        if not isinstance(token, str) or not token:
            raise DailyInvalidResponse("Daily did not return a meeting token.")
        return token

    def get_recording(self, *, artifact_id: str) -> dict[str, object]:
        return self._request("GET", f"/recordings/{quote(artifact_id, safe='')}")

    def recording_access_link(self, *, artifact_id: str) -> dict[str, object]:
        return self._request(
            "GET", f"/recordings/{quote(artifact_id, safe='')}/access-link?valid_for_secs=900"
        )

    def transcript_access_link(self, *, artifact_id: str) -> dict[str, object]:
        return self._request("GET", f"/transcript/{quote(artifact_id, safe='')}/access-link")

    def delete_recording(self, *, artifact_id: str) -> dict[str, object]:
        return self._request("DELETE", f"/recordings/{quote(artifact_id, safe='')}")

    def get_transcript(self, *, artifact_id: str) -> dict[str, object]:
        return self._request("GET", f"/transcript/{quote(artifact_id, safe='')}")

    def delete_transcript(self, *, artifact_id: str) -> dict[str, object]:
        return self._request("DELETE", f"/transcript/{quote(artifact_id, safe='')}")


def verify_daily_webhook(
    *,
    raw_body: bytes,
    signature: str | None,
    timestamp: str | None,
    secret_b64: str,
    max_age_seconds: int,
    now_epoch: float | None = None,
) -> None:
    """Verify Daily's base64 HMAC-SHA256 signature and bounded timestamp freshness."""

    if not signature or not timestamp or not secret_b64:
        raise DailyWebhookSignatureInvalid("Daily webhook signature is invalid.")
    try:
        secret = base64.b64decode(secret_b64, validate=True)
        timestamp_value = float(timestamp)
    except (ValueError, TypeError) as exc:
        raise DailyWebhookSignatureInvalid("Daily webhook signature is invalid.") from exc
    if not secret or max_age_seconds <= 0 or not math.isfinite(timestamp_value):
        raise DailyWebhookSignatureInvalid("Daily webhook signature is invalid.")
    current = time.time() if now_epoch is None else float(now_epoch)
    if abs(current - timestamp_value) > max_age_seconds:
        # Daily currently sends X-Webhook-Timestamp in Unix milliseconds. Keep signing
        # the exact header string below, but normalize milliseconds for replay-age checks.
        timestamp_seconds = timestamp_value / 1000
        if abs(current - timestamp_seconds) > max_age_seconds:
            raise DailyWebhookSignatureInvalid("Daily webhook timestamp is stale.")

    signed = timestamp.encode("utf-8") + b"." + raw_body
    expected = base64.b64encode(hmac.new(secret, signed, hashlib.sha256).digest()).decode("ascii")
    if not hmac.compare_digest(expected, signature):
        raise DailyWebhookSignatureInvalid("Daily webhook signature is invalid.")
