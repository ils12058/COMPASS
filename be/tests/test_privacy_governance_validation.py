"""Privacy validation uses safe field issues rather than message-keyed translations."""

import pytest

from compass.common.api import ValidationIssue
from compass.common.errors import APIError
from compass.privacy_governance import api, expansion, services


@pytest.mark.parametrize(
    ("validate", "identifier", "field"),
    [
        (lambda: services._validate_page(page=0, page_size=20), "page_invalid", "page"),
        (lambda: services._validate_page(page=1, page_size=51), "page_size_invalid", "page_size"),
        (lambda: services._clean_code("*bad"), "code_invalid", "code"),
        (lambda: services._clean_code(" "), "code_required", "code"),
        (
            lambda: services._clean_required("x" * 161, label="name", maximum=160),
            "name_too_long",
            "name",
        ),
        (lambda: expansion._audiences([]), "audiences_required", "audiences"),
        (lambda: expansion._audiences(["bad"]), "audiences_invalid", "audiences"),
        (lambda: expansion._audiences(["STAFF", "STAFF"]), "audiences_duplicate", "audiences"),
        (lambda: expansion._revision_values({"title": " "}), "title_required", "title"),
        (
            lambda: expansion._revision_values({"requires_acknowledgment": 1}),
            "acknowledgment_invalid",
            "requires_acknowledgment",
        ),
        (
            lambda: expansion._revision_values({"effective_on": "bad"}),
            "effective_date_invalid",
            "effective_on",
        ),
        (
            lambda: expansion._revision_values({"unknown": "value"}),
            "unsupported_revision_fields",
            None,
        ),
    ],
)
def test_privacy_validation_cases_have_stable_field_issues(validate, identifier, field):
    with pytest.raises(services.PrivacyInputError) as failure:
        validate()
    with pytest.raises(APIError) as response:
        api._raise(failure.value)
    error = response.value
    assert error.status_code == 422 and error.code == "invalid_privacy_governance_input"
    issue = ValidationIssue.model_validate(error.details[0])
    assert issue.type == identifier and issue.loc == ([field] if field else [])
    assert issue.message == error.message


@pytest.mark.django_db
def test_privacy_http_validation_keeps_code_and_adds_identifier():
    from tests.test_privacy_governance import auth_client, make_dpo, sync_policy
    from tests.test_privacy_governance_expansion import ROOT, notice_payload, post_json

    sync_policy()
    client = auth_client(make_dpo("privacy-validation@example.edu"))
    response = post_json(
        client, f"{ROOT}/notices", notice_payload() | {"audiences": ["STAFF", "STAFF"]}
    )
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "invalid_privacy_governance_input"
    assert error["details"][0]["type"] == "audiences_duplicate"
    assert error["details"][0]["loc"] == ["audiences"]


@pytest.mark.parametrize(
    ("metadata", "expected"),
    [
        (
            {"from_role": "STUDENT", "to_role": "IT_ADMIN"},
            "Changed from Student to IT Administrator.",
        ),
    ],
)
def test_access_activity_uses_role_labels(metadata, expected):
    from types import SimpleNamespace
    from uuid import uuid4

    from django.utils import timezone

    from compass.audit.actions import ACCOUNT_ROLE_CHANGED
    from compass.audit.models import AuditActorType
    from compass.privacy_governance.activity import _access_control

    event = SimpleNamespace(
        action=ACCOUNT_ROLE_CHANGED,
        target_type="accounts.user",
        target_id=uuid4(),
        metadata=metadata,
        pk=uuid4(),
        occurred_at=timezone.now(),
        actor_type=AuditActorType.SYSTEM,
        actor_user=None,
    )
    item = _access_control(event)
    assert item.description == expected
    assert "IT_ADMIN" not in item.description
