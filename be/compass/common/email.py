"""Code-owned rendering for COMPASS transactional email.

Every message is a plain-text body plus an HTML alternative rendered from a ``<name>.txt`` and
``<name>.html`` template pair. Both extend the shared shells in ``compass/email/`` (``base`` or
``security``), so branding, header, and footer live in one place. Templates and context are
code-owned: callers pass fixed wording and transient values, never stored records, user-entered
text, URLs, or markup. Rendering stays upstream of ``Mailer``, which remains the SMTP transport.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field

from django.template.loader import render_to_string

_EXTRA_BLANK_LINES = re.compile(r"\n{3,}")


@dataclass(frozen=True, slots=True)
class RenderedEmail:
    subject: str
    # Bodies can carry a transient security code, so they stay out of reprs and logs.
    text_body: str = field(repr=False)
    html_body: str = field(repr=False)


def _tidy_text(text: str) -> str:
    lines = "\n".join(line.rstrip() for line in text.strip().splitlines())
    return _EXTRA_BLANK_LINES.sub("\n\n", lines) + "\n"


def render_email(
    subject: str,
    template: str,
    context: Mapping[str, object] | None = None,
) -> RenderedEmail:
    """Render ``<template>.txt`` and ``<template>.html`` with the same code-owned context."""

    values = {**(context or {}), "subject": subject}
    return RenderedEmail(
        subject=subject,
        text_body=_tidy_text(render_to_string(f"{template}.txt", values)),
        html_body=render_to_string(f"{template}.html", values),
    )


__all__ = ["RenderedEmail", "render_email"]
