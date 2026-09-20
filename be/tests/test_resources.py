from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client
from django.utils import timezone

from compass.accounts.models import Designation, Role, User, UserDesignation
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.authentication.sessions import create_auth_session
from compass.publications import PublicationAudience
from compass.resources.models import ResourceCategory, ResourceKind
from compass.resources.services import (
    MAX_FILE_BYTES,
    InvalidResourceInput,
    ResourceConflict,
    ResourceNotFound,
    archive_resource,
    attach_resource_file,
    create_resource,
    create_resource_download,
    get_visible_resource,
    list_visible_resources,
    publish_resource,
)


class FakeStorage:
    def __init__(self) -> None:
        self.saved: dict[str, bytes] = {}
        self.deleted: list[str] = []
        self.private_url_calls: list[tuple[str, int]] = []

    def save(self, name: str, content) -> str:
        self.saved[name] = content.read()
        return name

    def delete(self, name: str) -> None:
        self.deleted.append(name)
        self.saved.pop(name, None)

    def private_url(self, name: str, *, expires_seconds: int) -> str:
        self.private_url_calls.append((name, expires_seconds))
        return f"https://private.example/{name}?signature=synthetic"


def sync_policy() -> None:
    call_command("sync_identity_policy", verbosity=0)


def make_user(email: str, role: str) -> User:
    return User.objects.create_user(
        email=email,
        password="a-test-password",
        role=Role.objects.get(code=role),
        first_name="Resource",
        last_name="Tester",
    )


def context(actor: User) -> AuditContext:
    return AuditContext.user(actor)


def auth_client(user: User) -> Client:
    issued = create_auth_session(user, now=timezone.now())
    client = Client()
    client.cookies["compass_session"] = issued.token
    return client


def csrf(client: Client) -> dict[str, str]:
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    return {"HTTP_X_CSRFTOKEN": response.json()["csrf_token"]}


def create_draft(
    *,
    actor: User,
    kind: str,
    audience: str = PublicationAudience.ALL_AUTHENTICATED,
    category: str = ResourceCategory.GENERAL,
    title: str = "Synthetic resource",
    body: str = "Curated **Markdown** description.",
    external_url: str | None = None,
    display_order: int = 0,
):
    return create_resource(
        actor=actor,
        title=title,
        body_markdown=body,
        category=category,
        kind=kind,
        audience=audience,
        external_url=external_url,
        display_order=display_order,
        context=context(actor),
    )


@pytest.mark.django_db
def test_resource_management_capability_baseline_and_head_compatibility():
    sync_policy()
    counselor = make_user("resource-counselor@example.edu", "COUNSELOR")
    staff = make_user("resource-staff@example.edu", "GUIDANCE_SERVICES_STAFF")
    head = make_user("resource-head@example.edu", "COUNSELOR")
    UserDesignation.objects.create(
        user=head,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )
    student = make_user("resource-student@example.edu", "STUDENT")
    admin = make_user("resource-admin@example.edu", "IT_ADMIN")
    officer = make_user("resource-officer@example.edu", "INSTITUTIONAL_OFFICER")

    assert counselor.has_capability("resources.manage")
    assert staff.has_capability("resources.manage")
    assert head.has_capability("resources.manage")
    for user in (student, admin, officer):
        assert not user.has_capability("resources.manage")


@pytest.mark.django_db
def test_resource_kind_validation_visibility_filtering_ordering_archive_and_audit():
    sync_policy()
    counselor = make_user("resource-publisher@example.edu", "COUNSELOR")
    student = make_user("resource-reader@example.edu", "STUDENT")

    article = create_draft(
        actor=counselor,
        kind=ResourceKind.ARTICLE,
        audience=PublicationAudience.STUDENTS,
        title="Article",
        display_order=20,
    )
    link = create_draft(
        actor=counselor,
        kind=ResourceKind.EXTERNAL_LINK,
        audience=PublicationAudience.STUDENTS,
        title="Trusted link",
        external_url="https://example.edu/guidance",
        display_order=10,
    )
    gco_only = create_draft(
        actor=counselor,
        kind=ResourceKind.ARTICLE,
        audience=PublicationAudience.GCO_PERSONNEL,
        title="GCO guide",
        display_order=0,
    )

    article = publish_resource(
        actor=counselor,
        resource_id=article.pk,
        context=context(counselor),
    )
    link = publish_resource(
        actor=counselor,
        resource_id=link.pk,
        context=context(counselor),
    )
    publish_resource(
        actor=counselor,
        resource_id=gco_only.pk,
        context=context(counselor),
    )

    rows = list_visible_resources(actor=student).items
    assert [item.pk for item in rows] == [link.pk, article.pk]
    assert [
        item.pk
        for item in list_visible_resources(
            actor=student,
            kind=ResourceKind.ARTICLE,
        ).items
    ] == [article.pk]

    with pytest.raises(ResourceNotFound):
        get_visible_resource(actor=student, resource_id=gco_only.pk)

    with pytest.raises(InvalidResourceInput):
        create_draft(
            actor=counselor,
            kind=ResourceKind.EXTERNAL_LINK,
            external_url="javascript:alert(1)",
        )
    with pytest.raises(InvalidResourceInput):
        create_draft(
            actor=counselor,
            kind=ResourceKind.ARTICLE,
            external_url="https://example.edu/not-article",
        )

    incomplete_link = create_draft(
        actor=counselor,
        kind=ResourceKind.EXTERNAL_LINK,
        external_url=None,
    )
    with pytest.raises(InvalidResourceInput):
        publish_resource(
            actor=counselor,
            resource_id=incomplete_link.pk,
            context=context(counselor),
        )

    archived = archive_resource(
        actor=counselor,
        resource_id=article.pk,
        context=context(counselor),
    )
    with pytest.raises(ResourceNotFound):
        get_visible_resource(actor=student, resource_id=archived.pk)
    with pytest.raises(ResourceConflict):
        publish_resource(
            actor=counselor,
            resource_id=archived.pk,
            context=context(counselor),
        )

    events = AuditEvent.objects.filter(
        target_type="resources.resource",
        target_id=str(link.pk),
    ).order_by("occurred_at", "id")
    assert [event.action for event in events] == [
        "resource.created",
        "resource.published",
    ]
    serialized = json.dumps([event.metadata for event in events])
    assert "Curated **Markdown** description." not in serialized
    assert "https://example.edu/guidance" not in serialized


@pytest.mark.django_db
def test_file_resource_private_storage_security_replacement_and_download_authorization():
    sync_policy()
    counselor = make_user("resource-file-publisher@example.edu", "COUNSELOR")
    student = make_user("resource-file-reader@example.edu", "STUDENT")
    storage = FakeStorage()

    item = create_draft(
        actor=counselor,
        kind=ResourceKind.FILE,
        audience=PublicationAudience.STUDENTS,
        title="Student PDF",
    )
    first_upload = SimpleUploadedFile(
        "../../unsafe-name.pdf",
        b"%PDF-1.7\nsynthetic first",
        content_type="application/pdf",
    )
    item = attach_resource_file(
        actor=counselor,
        resource_id=item.pk,
        uploaded_file=first_upload,
        context=context(counselor),
        storage=storage,
    )
    first_key = item.storage_key
    assert first_key.startswith(f"resources/{item.pk}/")
    assert first_key.endswith(".pdf")
    assert ".." not in first_key
    assert "unsafe-name" not in first_key
    assert item.original_filename == "unsafe-name.pdf"

    second_upload = SimpleUploadedFile(
        "replacement.pdf",
        b"%PDF-1.7\nsynthetic replacement",
        content_type="application/pdf",
    )
    item = attach_resource_file(
        actor=counselor,
        resource_id=item.pk,
        uploaded_file=second_upload,
        context=context(counselor),
        storage=storage,
    )
    assert item.storage_key != first_key
    assert first_key in storage.deleted

    item = publish_resource(
        actor=counselor,
        resource_id=item.pk,
        context=context(counselor),
    )
    download = create_resource_download(
        actor=student,
        resource_id=item.pk,
        storage=storage,
    )
    assert download.url.startswith("https://private.example/")
    assert "signature=synthetic" in download.url
    assert storage.private_url_calls == [(item.storage_key, download.expires_in_seconds)]

    before_saves = set(storage.saved)
    with pytest.raises(ResourceConflict):
        attach_resource_file(
            actor=counselor,
            resource_id=item.pk,
            uploaded_file=SimpleUploadedFile(
                "published-replacement.pdf",
                b"%PDF-1.7\nno replacement",
                content_type="application/pdf",
            ),
            context=context(counselor),
            storage=storage,
        )
    assert set(storage.saved) == before_saves

    with pytest.raises(ResourceNotFound):
        create_resource_download(
            actor=counselor,
            resource_id=item.pk,
            storage=storage,
        )
    assert len(storage.private_url_calls) == 1

    archive_resource(
        actor=counselor,
        resource_id=item.pk,
        context=context(counselor),
    )
    with pytest.raises(ResourceNotFound):
        create_resource_download(
            actor=student,
            resource_id=item.pk,
            storage=storage,
        )


@pytest.mark.django_db
def test_file_resource_rejects_unsafe_uploads_and_cleans_new_object_on_db_failure():
    sync_policy()
    counselor = make_user("resource-file-errors@example.edu", "COUNSELOR")
    storage = FakeStorage()
    item = create_draft(actor=counselor, kind=ResourceKind.FILE)

    with pytest.raises(InvalidResourceInput):
        attach_resource_file(
            actor=counselor,
            resource_id=item.pk,
            uploaded_file=SimpleUploadedFile(
                "not-pdf.txt",
                b"%PDF-1.7\ncontent",
                content_type="text/plain",
            ),
            context=context(counselor),
            storage=storage,
        )
    with pytest.raises(InvalidResourceInput):
        attach_resource_file(
            actor=counselor,
            resource_id=item.pk,
            uploaded_file=SimpleUploadedFile(
                "fake.pdf",
                b"not a pdf",
                content_type="application/pdf",
            ),
            context=context(counselor),
            storage=storage,
        )
    with pytest.raises(InvalidResourceInput):
        attach_resource_file(
            actor=counselor,
            resource_id=item.pk,
            uploaded_file=SimpleUploadedFile(
                "too-large.pdf",
                b"%PDF-" + (b"x" * MAX_FILE_BYTES),
                content_type="application/pdf",
            ),
            context=context(counselor),
            storage=storage,
        )

    cleanup_item = create_draft(actor=counselor, kind=ResourceKind.FILE, title="Cleanup")
    with patch(
        "compass.resources.services.record_event",
        side_effect=RuntimeError("synthetic audit failure"),
    ):
        with pytest.raises(RuntimeError, match="synthetic audit failure"):
            attach_resource_file(
                actor=counselor,
                resource_id=cleanup_item.pk,
                uploaded_file=SimpleUploadedFile(
                    "cleanup.pdf",
                    b"%PDF-1.7\ncleanup",
                    content_type="application/pdf",
                ),
                context=context(counselor),
                storage=storage,
            )
    cleanup_item.refresh_from_db()
    assert cleanup_item.storage_key == ""
    assert storage.deleted


@pytest.mark.django_db
def test_resource_api_hides_storage_key_and_gss_can_publish_without_head_approval():
    sync_policy()
    staff = make_user("resource-api-staff@example.edu", "GUIDANCE_SERVICES_STAFF")
    student = make_user("resource-api-student@example.edu", "STUDENT")
    client = auth_client(staff)

    response = client.post(
        "/api/v1/resources/management",
        data=json.dumps(
            {
                "title": "Staff article",
                "body_markdown": "<script>raw source only</script>",
                "category": "GENERAL",
                "kind": "ARTICLE",
                "audience": "ALL_AUTHENTICATED",
                "display_order": 1,
            }
        ),
        content_type="application/json",
        **csrf(client),
    )
    assert response.status_code == 201
    resource_id = response.json()["id"]
    assert "storage_key" not in response.json()

    published = client.post(
        f"/api/v1/resources/management/{resource_id}/publish",
        **csrf(client),
    )
    assert published.status_code == 200

    reader = auth_client(student).get(f"/api/v1/resources/{resource_id}")
    assert reader.status_code == 200
    assert reader.json()["body_markdown"] == "<script>raw source only</script>"
    assert "storage_key" not in reader.json()
    assert "body_html" not in reader.json()
