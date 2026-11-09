"""Announcement field issues carry stable identifiers through the existing envelope."""

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from django.utils import timezone

from compass.announcements import api, services
from compass.common.api import ValidationIssue
from compass.common.errors import APIError


@pytest.mark.parametrize(
    ("validate", "identifier", "field"),
    [
        (lambda: services._clean_title(None), "title_text_required", "title"),
        (lambda: services._clean_title(" ", require_nonblank=True), "title_required", "title"),
        (lambda: services._clean_title("x" * 201), "title_too_long", "title"),
        (lambda: services._clean_body(None), "body_text_required", "body_markdown"),
        (
            lambda: services._clean_body(" ", require_nonblank=True),
            "body_required",
            "body_markdown",
        ),
        (lambda: services._clean_body("é" * 25601), "body_too_large", "body_markdown"),
        (lambda: services._clean_audience("bad"), "audience_invalid", "audience"),
        (lambda: services._clean_expiry(datetime(2026, 1, 1)), "expiry_invalid", "expires_at"),
        (lambda: services._clean_page(0, 20), "page_invalid", "page"),
        (lambda: services._clean_page(1, 51), "page_size_invalid", "page_size"),
        (lambda: services._reader_ordering("bad"), "ordering_invalid", "ordering"),
    ],
)
def test_announcement_validation_cases_have_stable_field_issues(validate, identifier, field):
    with pytest.raises(services.InvalidAnnouncementInput) as failure:
        validate()
    with pytest.raises(APIError) as response:
        api._raise(failure.value)
    error = response.value
    assert error.status_code == 422 and error.code == "invalid_announcement_input"
    issue = ValidationIssue.model_validate(error.details[0])
    assert issue.type == identifier and issue.loc == [field]
    assert issue.message == error.message


def test_published_expiry_rejection_has_its_own_identifier():
    now = timezone.now()
    item = SimpleNamespace(
        title="Title",
        body_markdown="Body",
        audience="PUBLIC",
        expires_at=now - timedelta(seconds=1),
    )
    with pytest.raises(services.InvalidAnnouncementInput) as failure:
        services._validate_published_announcement_state(item, now=now)
    assert failure.value.details[0]["type"] == "expiry_not_future"
    assert failure.value.details[0]["loc"] == ["expires_at"]


@pytest.mark.django_db
def test_announcement_http_validation_keeps_code_and_adds_identifier():
    from tests.test_announcements import auth_client, context, csrf, make_user, sync_policy

    sync_policy()
    actor = make_user("announcement-validation@example.edu", "COUNSELOR")
    client = auth_client(actor)
    item = services.create_announcement(
        actor=actor,
        title=" ",
        body_markdown="Body",
        audience="PUBLIC",
        is_pinned=False,
        expires_at=None,
        context=context(actor),
    )
    response = client.post(f"/api/v1/announcements/management/{item.pk}/publish", **csrf(client))
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "invalid_announcement_input"
    assert error["details"][0]["type"] == "title_required"
    assert error["details"][0]["loc"] == ["title"]
