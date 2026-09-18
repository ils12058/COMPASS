from __future__ import annotations

import inspect
import json

import pytest
from django.apps import apps
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import Client
from django.utils import timezone
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from compass.accounts.models import Designation, Role, User, UserDesignation
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.authentication.sessions import create_auth_session
from compass.documents import rendering
from compass.documents.assets import get_asset_data_uri, get_document_assets
from compass.documents.models import DocumentBrandingProfile
from compass.documents.rendering import (
    DocumentRenderError,
    DocumentRenderUnavailable,
    DocumentTemplateError,
    render_document_html,
    render_document_pdf,
)
from compass.documents.services import (
    InvalidDocumentBrandingInput,
    get_branding_profile,
    update_branding_profile,
)
from compass.documents.template_specs import (
    LayoutFamily,
    UnknownDocumentTemplate,
    get_template_spec,
)


def sync_policy() -> None:
    call_command("sync_identity_policy", verbosity=0)


def make_user(email: str, role: str) -> User:
    return User.objects.create_user(
        email=email,
        password="a-test-password",
        role=Role.objects.get(code=role),
        first_name=email.split("@")[0].replace(".", " ").title(),
        middle_name="",
        last_name="User",
    )


def make_head(email: str = "head@example.edu") -> User:
    user = make_user(email, "COUNSELOR")
    UserDesignation.objects.create(
        user=user,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )
    return user


def auth_client(user: User, *, recent_mfa: bool = False) -> Client:
    now = timezone.now()
    issued = create_auth_session(
        user,
        now=now,
        mfa_verified_at=now if recent_mfa else None,
    )
    client = Client()
    client.cookies["compass_session"] = issued.token
    return client


def csrf(client: Client) -> dict[str, str]:
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    return {"HTTP_X_CSRFTOKEN": response.json()["csrf_token"]}


def sample_rows(count: int = 60) -> list[dict[str, str]]:
    return [
        {
            "label": f"Row {index:03d}",
            "value": "Deterministic report fixture content for print-safe table behavior.",
        }
        for index in range(1, count + 1)
    ]


@pytest.mark.django_db
def test_default_branding_profile_bootstraps_only_confirmed_identity():
    profile = get_branding_profile()
    assert profile.key == "default"
    assert profile.country_line == "Republic of the Philippines"
    assert profile.institution_name == "University of Camarines Norte"
    assert profile.institution_short_name == "UCN"
    assert profile.former_institution_name == "Camarines Norte State College"
    assert profile.office_name == "Guidance and Counseling Office"

    assert profile.institution_address is None
    assert profile.institution_website_url is None
    assert profile.institution_contact_email is None
    assert profile.institution_social_url is None
    assert profile.office_parent_unit_name is None
    assert profile.office_email is None
    assert profile.office_phone is None
    assert profile.office_location is None

    serialized = json.dumps(
        {
            field.name: getattr(profile, field.name)
            for field in profile._meta.fields
            if field.name not in {"id", "created_at", "updated_at"}
        },
        default=str,
    ).lower()
    assert "college of education" not in serialized
    assert "guidance, testing and admission office" not in serialized
    assert "coedgtao@ucn.edu.ph" not in serialized


@pytest.mark.django_db
def test_only_default_profile_key_is_supported_by_database():
    assert DocumentBrandingProfile.objects.count() == 1
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            DocumentBrandingProfile.objects.create(
                key="another-office",
                country_line="Republic of the Philippines",
                institution_name="University of Camarines Norte",
                institution_short_name="UCN",
                office_name="Another Office",
            )
    assert DocumentBrandingProfile.objects.count() == 1


@pytest.mark.django_db
def test_profile_service_validates_required_email_url_and_normalizes_optional_blank():
    profile = get_branding_profile()
    context = AuditContext.system()

    with pytest.raises(InvalidDocumentBrandingInput, match="institution_name"):
        update_branding_profile(
            changes={"institution_name": "   "},
            context=context,
        )
    with pytest.raises(InvalidDocumentBrandingInput, match="office_email"):
        update_branding_profile(
            changes={"office_email": "not-an-email"},
            context=context,
        )
    with pytest.raises(InvalidDocumentBrandingInput, match="institution_website_url"):
        update_branding_profile(
            changes={"institution_website_url": "definitely-not-a-url"},
            context=context,
        )

    result = update_branding_profile(
        changes={
            "office_email": "  office@example.edu  ",
            "office_location": "   ",
        },
        context=context,
    )
    assert result.changed
    assert result.profile.office_email == "office@example.edu"
    assert result.profile.office_location is None
    profile.refresh_from_db()
    assert profile.office_location is None


@pytest.mark.django_db
def test_head_profile_api_requires_head_capability_and_recent_mfa_for_mutation():
    sync_policy()
    head = make_head()

    no_mfa = auth_client(head)
    get_response = no_mfa.get("/api/v1/document-branding/profile")
    assert get_response.status_code == 200
    assert get_response.json()["institution_short_name"] == "UCN"

    denied = no_mfa.patch(
        "/api/v1/document-branding/profile",
        data=json.dumps({"office_phone": "(054) 000-0000"}),
        content_type="application/json",
        **csrf(no_mfa),
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "recent_mfa_required"

    with_mfa = auth_client(head, recent_mfa=True)
    updated = with_mfa.patch(
        "/api/v1/document-branding/profile",
        data=json.dumps(
            {
                "institution_website_url": "https://www.ucn.edu.ph",
                "office_email": "gco@example.edu",
            }
        ),
        content_type="application/json",
        **csrf(with_mfa),
    )
    assert updated.status_code == 200
    assert updated.json()["institution_website_url"] == "https://www.ucn.edu.ph"
    assert updated.json()["office_email"] == "gco@example.edu"


@pytest.mark.django_db
def test_non_head_roles_and_dpo_have_no_document_branding_access():
    sync_policy()
    users = [
        make_user("counselor@example.edu", "COUNSELOR"),
        make_user("gss@example.edu", "GUIDANCE_SERVICES_STAFF"),
        make_user("student@example.edu", "STUDENT"),
        make_user("admin@example.edu", "IT_ADMIN"),
    ]
    dpo = make_user("dpo@example.edu", "IT_ADMIN")
    UserDesignation.objects.create(
        user=dpo,
        designation=Designation.objects.get(code="DPO"),
    )
    users.append(dpo)

    for user in users:
        assert not user.has_capability("document_branding.view")
        assert not user.has_capability("document_branding.manage")
        client = auth_client(user, recent_mfa=True)
        assert client.get("/api/v1/document-branding/profile").status_code == 403
        response = client.patch(
            "/api/v1/document-branding/profile",
            data=json.dumps({"office_phone": "1234"}),
            content_type="application/json",
            **csrf(client),
        )
        assert response.status_code == 403


@pytest.mark.django_db
def test_profile_api_rejects_invalid_values_has_no_delete_and_audits_only_field_names():
    sync_policy()
    head = make_head()
    client = auth_client(head, recent_mfa=True)
    headers = csrf(client)

    invalid = client.patch(
        "/api/v1/document-branding/profile",
        data=json.dumps({"institution_name": "  "}),
        content_type="application/json",
        **headers,
    )
    assert invalid.status_code == 422

    invalid_email = client.patch(
        "/api/v1/document-branding/profile",
        data=json.dumps({"office_email": "PRIVATE-BAD-EMAIL"}),
        content_type="application/json",
        **headers,
    )
    assert invalid_email.status_code == 422

    secret_value = "https://private.example.invalid/branding"
    updated = client.patch(
        "/api/v1/document-branding/profile",
        data=json.dumps({"institution_social_url": secret_value}),
        content_type="application/json",
        **headers,
    )
    assert updated.status_code == 200

    event = AuditEvent.objects.get(action="document_branding.updated")
    assert event.target_type == "documents.documentbrandingprofile"
    assert event.metadata == {
        "profile_key": "default",
        "changed_fields": ["institution_social_url"],
    }
    assert secret_value not in json.dumps(event.metadata)

    deleted = client.delete(
        "/api/v1/document-branding/profile",
        **headers,
    )
    assert deleted.status_code in {404, 405}


@pytest.mark.django_db
def test_html_uses_shared_branding_partials_local_assets_and_autoescaping():
    update_branding_profile(
        changes={
            "institution_name": "<script>institution()</script>",
            "office_name": "Guidance & Counseling <Office>",
        },
        context=AuditContext.system(),
    )
    html, spec = render_document_html(
        "foundation_test",
        1,
        context={
            "title": "Trusted test report",
            "sample_body": "<script>alert('body')</script>",
            "rows": sample_rows(3),
            "controlled_form": {
                "official_code": "CNSC-OP-GTA-01F8",
                "official_revision": "0",
                "page_label": "Page 1 of 1",
            },
        },
    )

    assert spec.layout_family is LayoutFamily.REPORT
    assert '<header class="institution-masthead">' in html
    assert '<section class="office-heading">' in html
    assert '<footer class="accreditation-footer">' in html
    assert "data:image/png;base64," in html
    assert "CNSC-OP-GTA-01F8" in html
    assert "Revision: 0" in html
    assert "Page 1 of 1" in html

    assert "<script>institution()</script>" not in html
    assert "&lt;script&gt;institution()&lt;/script&gt;" in html
    assert "Guidance &amp; Counseling &lt;Office&gt;" in html
    assert "<script>alert('body')</script>" not in html
    assert "&lt;script&gt;alert" in html

    assert "http://minio" not in html
    assert "https://example" not in html


@pytest.mark.django_db
def test_code_owned_layout_can_omit_accreditation_footer_and_spec_rejects_unknown_paths():
    html, spec = render_document_html(
        "foundation_test_no_footer",
        1,
        context={
            "title": "No footer fixture",
            "sample_body": "Body",
            "rows": sample_rows(2),
        },
    )
    assert spec.include_accreditation_footer is False
    assert '<footer class="accreditation-footer">' not in html
    assert get_document_assets(include_accreditation_footer=False)["accreditation_footer"] is None

    known = get_template_spec("foundation_test", 1)
    assert known.template_name == "documents/test/foundation_fixture.html"
    with pytest.raises(UnknownDocumentTemplate):
        get_template_spec("../../arbitrary/template.html", 1)
    with pytest.raises(DocumentTemplateError):
        render_document_html("../../arbitrary/template.html", 1)

    document_models = set(apps.all_models["documents"])
    assert document_models == {"documentbrandingprofile"}


def test_supplied_packaged_assets_resolve_locally_without_static_storage_urls():
    for key in ("ucn_logo", "bagong_pilipinas_logo", "accreditation_footer"):
        data_uri = get_asset_data_uri(key)
        assert data_uri.startswith("data:image/png;base64,")
        assert "http://" not in data_uri
        assert "https://" not in data_uri


@pytest.mark.django_db
def test_real_chromium_renders_nontrivial_local_pdf_with_report_table():
    result = render_document_pdf(
        "foundation_test",
        1,
        context={
            "title": "Multipage report-capability fixture",
            "sample_body": "Local deterministic HTML and packaged assets only.",
            "rows": sample_rows(90),
            "controlled_form": {
                "official_code": "CNSC-OP-GTA-01F8",
                "official_revision": "0",
                "page_label": "Historical metadata fixture",
            },
        },
    )
    assert result.template_key == "foundation_test"
    assert result.template_version == 1
    assert result.pdf_bytes.startswith(b"%PDF-")
    assert len(result.pdf_bytes) > 10_000


@pytest.mark.django_db
def test_renderer_blocks_unexpected_remote_resource():
    with pytest.raises(DocumentRenderError, match="remote resource"):
        render_document_pdf(
            "foundation_test_no_footer",
            1,
            context={
                "title": "Remote block fixture",
                "sample_body": "The remote image must never be fetched.",
                "rows": sample_rows(1),
                "test_remote_asset": True,
            },
        )


@pytest.mark.django_db
def test_renderer_maps_chromium_unavailable_and_timeout_without_leaking_browser_error(monkeypatch):
    class FakeChromium:
        def __init__(self, error):
            self.error = error

        def launch(self, **kwargs):
            raise self.error

    class FakePlaywright:
        def __init__(self, error):
            self.chromium = FakeChromium(error)

    class FakeContext:
        def __init__(self, error):
            self.error = error

        def __enter__(self):
            return FakePlaywright(self.error)

        def __exit__(self, exc_type, exc, traceback):
            return False

    monkeypatch.setattr(
        rendering,
        "sync_playwright",
        lambda: FakeContext(PlaywrightError("PRIVATE-CHROMIUM-INTERNAL")),
    )
    with pytest.raises(DocumentRenderUnavailable) as unavailable:
        render_document_pdf(
            "foundation_test_no_footer",
            1,
            context={"title": "Unavailable", "sample_body": "Body", "rows": []},
        )
    assert "PRIVATE-CHROMIUM-INTERNAL" not in str(unavailable.value)

    monkeypatch.setattr(
        rendering,
        "sync_playwright",
        lambda: FakeContext(PlaywrightTimeoutError("PRIVATE-TIMEOUT-INTERNAL")),
    )
    with pytest.raises(DocumentRenderUnavailable, match="render timeout") as timed_out:
        render_document_pdf(
            "foundation_test_no_footer",
            1,
            context={"title": "Timeout", "sample_body": "Body", "rows": []},
        )
    assert "PRIVATE-TIMEOUT-INTERNAL" not in str(timed_out.value)


def test_renderer_never_uses_caller_url_navigation():
    source = inspect.getsource(rendering.render_document_pdf)
    assert ".goto(" not in source
    assert "page.set_content(" in source
