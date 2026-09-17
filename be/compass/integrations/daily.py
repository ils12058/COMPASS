"""Narrow Daily.co REST and webhook-signature integration boundary."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from django.conf import settings

logger = logging.getLogger("compass.daily")


class DailyError(RuntimeError):
    """Base error for sanitized Daily integration failures."""


class DailyConfigurationError(DailyError):
    pass


class DailyUnavailable(DailyError):
    pass


class DailyHTTPError(DailyError):
    def __init__(self, status_code: int) -> None:
        super().__init__(f"Daily returned HTTP {status_code}.")
        self.status_code = status_code


class DailyInvalidResponse(DailyError):
    pass


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
        body = None if payload is None else json.dumps(payload, separators=(",", ":")).encode("utf-8")
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
            raise DailyHTTPError(int(exc.code)) from exc
        except (URLError, TimeoutError, OSError) as exc:
            logger.warning(
                "Daily transport failure",
                extra={"event": "daily_transport_failure", "operation": method},
            )
            raise DailyUnavailable("Daily is temporarily unavailable.") from exc

        try:
            decoded = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
            raise DailyInvalidResponse("Daily returned an invalid JSON response.") from exc
        if not isinstance(decoded, dict):
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
    if not secret or max_age_seconds <= 0:
        raise DailyWebhookSignatureInvalid("Daily webhook signature is invalid.")
    current = time.time() if now_epoch is None else float(now_epoch)
    if abs(current - timestamp_value) > max_age_seconds:
        raise DailyWebhookSignatureInvalid("Daily webhook timestamp is stale.")

    signed = timestamp.encode("utf-8") + b"." + raw_body
    expected = base64.b64encode(hmac.new(secret, signed, hashlib.sha256).digest()).decode("ascii")
    if not hmac.compare_digest(expected, signature):
        raise DailyWebhookSignatureInvalid("Daily webhook signature is invalid.")
