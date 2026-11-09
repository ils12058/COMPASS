"""Resource validation identifiers survive API serialization and copy changes."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from compass.common.api import ValidationIssue
from compass.common.errors import APIError
from compass.publications import PublicationAudience
from compass.resources import api, services
from compass.resources.models import ResourceCategory, ResourceKind


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
        (lambda: services._clean_external_url(1), "external_url_text_required", "external_url"),
        (
            lambda: services._clean_external_url(None, required=True),
            "external_url_required",
            "external_url",
        ),
        (lambda: services._clean_external_url("x" * 2049), "external_url_too_long", "external_url"),
        (
            lambda: services._clean_external_url("ftp://example.edu"),
            "external_url_invalid",
            "external_url",
        ),
        (
            lambda: services._clean_external_url("https://user:secret@example.edu"),
            "external_url_credentials",
            "external_url",
        ),
        (
            lambda: services._clean_display_order(True),
            "display_order_integer_required",
            "display_order",
        ),
        (
            lambda: services._clean_display_order(2**31),
            "display_order_out_of_range",
            "display_order",
        ),
        (lambda: services._clean_page(0, 20), "page_invalid", "page"),
        (lambda: services._clean_page(1, 51), "page_size_invalid", "page_size"),
        (
            lambda: services._choice("bad", PublicationAudience, "audience"),
            "audience_invalid",
            "audience",
        ),
        (lambda: services._choice("bad", ResourceKind, "kind"), "kind_invalid", "kind"),
        (
            lambda: services._choice("bad", ResourceCategory, "category"),
            "category_invalid",
            "category",
        ),
        (lambda: services._reader_ordering("bad"), "ordering_invalid", "ordering"),
    ],
)
def test_resource_validation_cases_have_stable_field_issues(validate, identifier, field):
    with pytest.raises(services.InvalidResourceInput) as failure:
        validate()
    with pytest.raises(APIError) as response:
        api._raise(failure.value)
    error = response.value
    assert error.status_code == 422 and error.code == "invalid_resource_input"
    issue = ValidationIssue.model_validate(error.details[0])
    assert issue.type == identifier and issue.loc == [field]
    assert issue.message == error.message


@pytest.mark.parametrize(
    ("upload", "identifier"),
    [
        (None, "pdf_required"),
        (
            SimpleUploadedFile("test.txt", b"%PDF-", content_type="text/plain"),
            "pdf_content_type_invalid",
        ),
        (SimpleUploadedFile("test.pdf", b"", content_type="application/pdf"), "pdf_empty"),
        (
            SimpleUploadedFile(
                "test.pdf",
                b"%PDF-" + b"x" * services.MAX_FILE_BYTES,
                content_type="application/pdf",
            ),
            "pdf_too_large",
        ),
        (
            SimpleUploadedFile("test.pdf", b"bad file", content_type="application/pdf"),
            "pdf_signature_invalid",
        ),
    ],
)
def test_pdf_rejections_have_distinct_identifiers_without_storage_access(upload, identifier):
    with pytest.raises(services.InvalidResourceInput) as failure:
        services.attach_resource_file(
            actor=None, resource_id=uuid4(), uploaded_file=upload, context=None
        )
    assert failure.value.details[0]["type"] == identifier


@pytest.mark.parametrize(
    ("kind", "url", "storage_key", "identifier"),
    [
        (ResourceKind.ARTICLE, "https://example.edu", "", "article_attachment_not_allowed"),
        (ResourceKind.EXTERNAL_LINK, "", "attached.pdf", "external_link_file_not_allowed"),
        (ResourceKind.FILE, "https://example.edu", "", "file_external_url_not_allowed"),
        (ResourceKind.FILE, "", "", "pdf_required_for_publication"),
    ],
)
def test_resource_channel_rejections_have_distinct_identifiers(kind, url, storage_key, identifier):
    item = SimpleNamespace(kind=kind, external_url=url, storage_key=storage_key)
    with pytest.raises(services.InvalidResourceInput) as failure:
        services._validate_channel_state(item, for_publish=True)
    assert failure.value.details[0]["type"] == identifier


@pytest.mark.django_db
def test_resource_http_validation_and_conflict_keep_codes_and_add_identifiers():
    from tests.test_resources import (
        auth_client,
        context,
        create_draft,
        csrf,
        make_user,
        sync_policy,
    )

    sync_policy()
    actor = make_user("resource-validation@example.edu", "COUNSELOR")
    client = auth_client(actor)
    item = create_draft(actor=actor, kind=ResourceKind.ARTICLE, title=" ")
    response = client.post(f"/api/v1/resources/management/{item.pk}/publish", **csrf(client))
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "invalid_resource_input"
    assert error["details"][0]["type"] == "title_required"
    assert error["details"][0]["loc"] == ["title"]
    services.archive_resource(actor=actor, resource_id=item.pk, context=context(actor))
    with pytest.raises(services.ResourceConflict) as failure:
        services.update_resource(
            actor=actor, resource_id=item.pk, values={"title": "Changed"}, context=context(actor)
        )
    with pytest.raises(APIError) as response_error:
        api._raise(failure.value)
    assert response_error.value.status_code == 409
    assert response_error.value.code == "resource_conflict"
    assert response_error.value.details[0]["type"] == "resource_archived"
