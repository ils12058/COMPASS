"""Small shared filename helpers for generated report representations."""

from __future__ import annotations

import re


def safe_report_filename_part(value: str, *, fallback: str = "report") -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-._")
    return safe or fallback
