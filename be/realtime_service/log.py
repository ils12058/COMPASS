"""Structured JSON lifecycle logs for the realtime service.

Only reviewed fields are written, and only as numbers or short codes. Frames, tickets, Origins,
query strings, client addresses, Redis URLs, and user or session identifiers are never logged.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import UTC, datetime

logger = logging.getLogger("compass.realtime")

_FIELDS = (
    "reason",
    "close_code",
    "connection_id",
    "duration_seconds",
    "active_connections",
    "allowed_origin_count",
    "error_type",
)
_CODE = re.compile(r"[A-Za-z0-9_.-]{1,64}")


def _value(value: object) -> str | int | float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return value
    if isinstance(value, str) and _CODE.fullmatch(value):
        return value
    return None


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": getattr(record, "event", "realtime"),
        }
        for field in _FIELDS:
            value = _value(getattr(record, field, None))
            if value is not None:
                payload[field] = value
        return json.dumps(payload, separators=(",", ":"))


def configure() -> None:
    if logger.handlers:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def event(name: str, *, level: int = logging.INFO, **fields: object) -> None:
    logger.log(level, name, extra={"event": name, **fields})
