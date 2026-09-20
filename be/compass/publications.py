"""Small shared publication enums and audience eligibility helpers."""

from __future__ import annotations

from django.db import models


class PublicationStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    PUBLISHED = "PUBLISHED", "Published"
    ARCHIVED = "ARCHIVED", "Archived"


class PublicationAudience(models.TextChoices):
    ALL_AUTHENTICATED = "ALL_AUTHENTICATED", "All authenticated"
    STUDENTS = "STUDENTS", "Students"
    GCO_PERSONNEL = "GCO_PERSONNEL", "GCO personnel"


def eligible_audiences_for(user) -> tuple[str, ...]:
    if not getattr(user, "is_active", False):
        return ()
    audiences = [PublicationAudience.ALL_AUTHENTICATED]
    role_code = getattr(getattr(user, "role", None), "code", None)
    if role_code == "STUDENT":
        audiences.append(PublicationAudience.STUDENTS)
    elif role_code in {"COUNSELOR", "GUIDANCE_SERVICES_STAFF"}:
        audiences.append(PublicationAudience.GCO_PERSONNEL)
    return tuple(value.value for value in audiences)


__all__ = ["PublicationAudience", "PublicationStatus", "eligible_audiences_for"]
