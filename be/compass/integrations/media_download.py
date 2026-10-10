"""Bounded server-only Daily downloads. No redirects, cookies, bearer forwarding or URL errors."""

import hashlib
import re
import time
from contextlib import contextmanager
from tempfile import TemporaryFile
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from django.conf import settings


class MediaDownloadError(RuntimeError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise MediaDownloadError("Provider media redirects are unsupported.")


def validate_daily_link(payload, *, kind, artifact_id):
    if not isinstance(payload, dict):
        raise MediaDownloadError("Provider media link is invalid.")
    candidates = [payload[key] for key in ("download_link", "link") if key in payload]
    if not candidates or any(not isinstance(value, str) for value in candidates):
        raise MediaDownloadError("Provider media link is invalid.")
    if len(set(candidates)) != 1:
        raise MediaDownloadError("Provider media link is ambiguous.")
    url = candidates[0]
    if kind == "TRANSCRIPTION" and payload.get("transcriptId") != artifact_id:
        raise MediaDownloadError("Provider transcript identity is invalid.")
    if kind == "RECORDING":
        expires = payload.get("expires")
        if type(expires) is not int or expires <= time.time():
            raise MediaDownloadError("Provider media link expired.")
    bucket = "daily-meeting-recordings" if kind == "RECORDING" else "daily-meeting-transcripts"
    try:
        parts = urlsplit(url)
        valid = (
            parts.scheme == "https"
            and not parts.username
            and not parts.password
            and parts.port in (None, 443)
            and not parts.fragment
            and re.fullmatch(
                re.escape(bucket) + r"\.s3(?:[.-][a-z0-9-]+)?\.amazonaws\.com", parts.hostname or ""
            )
        )
    except ValueError:
        valid = False
    if not valid:
        raise MediaDownloadError("Provider media storage is unsupported.")
    return url


@contextmanager
def stream_daily_media(url, *, kind):
    """Disk-only spooling, 64 KiB reads, 30s socket timeout and 15 minute total read budget."""
    try:
        opener = build_opener(NoRedirect())
        with opener.open(Request(url, headers={"Accept": "*/*"}), timeout=30) as response:
            if response.status != 200:
                raise MediaDownloadError("Provider media download failed.")
            raw_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            expected = response.headers.get("Content-Length")
            if expected is not None and (
                not expected.isdecimal()
                or not 0 < int(expected) <= settings.ECOUNSELING_MEDIA_MAX_BYTES
            ):
                raise MediaDownloadError("Provider media size is invalid.")
            with TemporaryFile(mode="w+b") as spool:
                digest, size, first = hashlib.sha256(), 0, b""
                deadline = time.monotonic() + 900
                while chunk := response.read(64 * 1024):
                    if time.monotonic() > deadline:
                        raise MediaDownloadError("Provider media download timed out.")
                    size += len(chunk)
                    if size > settings.ECOUNSELING_MEDIA_MAX_BYTES:
                        raise MediaDownloadError("Provider media exceeds the allowed size.")
                    if not first:
                        first = chunk[:32]
                    digest.update(chunk)
                    spool.write(chunk)
                if size == 0 or expected is not None and int(expected) != size:
                    raise MediaDownloadError("Provider media download is incomplete.")
                if kind == "TRANSCRIPTION":
                    if raw_type not in {
                        "text/vtt",
                        "text/plain",
                        "application/octet-stream",
                    } or not first.lstrip(b"\xef\xbb\xbf").startswith(b"WEBVTT"):
                        raise MediaDownloadError("Provider transcript format is invalid.")
                    content_type = "text/vtt"
                elif first[4:8] == b"ftyp" and raw_type in {
                    "video/mp4",
                    "application/octet-stream",
                }:
                    content_type = "video/mp4"
                elif first[:4] == b"\x1a\x45\xdf\xa3" and raw_type in {
                    "video/webm",
                    "application/octet-stream",
                }:
                    content_type = "video/webm"
                else:
                    raise MediaDownloadError("Provider recording format is invalid.")
                spool.seek(0)
                yield spool, content_type, size, digest.hexdigest()
    except MediaDownloadError:
        raise
    except Exception:
        raise MediaDownloadError("Provider media download failed.") from None
