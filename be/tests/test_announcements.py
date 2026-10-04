from __future__ import annotations

import json
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.test import Client
from django.utils import timezone

from compass.accounts.models import (
    Capability,
    Designation,
    Role,
    User,
    UserDesignation,
)
from compass.accounts.services import set_user_capability_override
from compass.announcements.services import (
    AnnouncementConflict,
    AnnouncementNotFound,
    AnnouncementPublicationConsequenceReviewRequired,
    InvalidAnnouncementInput,
    archive_announcement,
    create_announcement,
    get_public_announcement,
    get_visible_announcement,
    list_public_announcements,
    list_visible_announcements,
    publish_announcement,
    update_announcement,
)
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.authentication.sessions import create_auth_session
from compass.publications import PublicationAudience


def sync_policy() -> None:
    call_command("sync_identity_policy", verbosity=0)


def make_user(email: str, role: str) -> User:
    return User.objects.create_user(
        email=email,
        password="a-test-password",
        role=Role.objects.get(code=role),
        first_name="Publication",
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


@pytest.mark.django_db
def test_announcement_management_capability_baseline_head_compatibility_and_override():
    sync_policy()
    counselor = make_user("announcement-counselor@example.edu", "COUNSELOR")
    staff = make_user("announcement-staff@example.edu", "GUIDANCE_SERVICES_STAFF")
    student = make_user("announcement-student@example.edu", "STUDENT")
    admin = make_user("announcement-admin@example.edu", "IT_ADMIN")
    officer = make_user("announcement-officer@example.edu", "INSTITUTIONAL_OFFICER")
    head = make_user("announcement-head@example.edu", "COUNSELOR")
    UserDesignation.objects.create(
        user=head,
        designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR"),
    )

    assert counselor.has_capability("announcements.manage")
    assert staff.has_capability("announcements.manage")
    assert head.has_capability("announcements.manage")
    for user in (student, admin, officer):
        assert not user.has_capability("announcements.manage")

    set_user_capability_override(
        user=admin,
        capability=Capability.objects.get(code="announcements.manage"),
        effect="GRANT",
        reason="Temporary publication duty",
    )
    assert admin.has_capability("announcements.manage")


@pytest.mark.django_db
def test_announcement_lifecycle_audience_expiry_ordering_and_audit_are_bounded():
    sync_policy()
    counselor = make_user("announcement-publisher@example.edu", "COUNSELOR")
    student = make_user("announcement-reader@example.edu", "STUDENT")
    staff = make_user("announcement-gss@example.edu", "GUIDANCE_SERVICES_STAFF")
    admin = make_user("announcement-it@example.edu", "IT_ADMIN")
    officer = make_user("announcement-institutional@example.edu", "INSTITUTIONAL_OFFICER")
    now = timezone.now()

    all_item = create_announcement(
        actor=counselor,
        title="Office reminder",
        body_markdown="**Office-wide** information.",
        audience=PublicationAudience.ALL_AUTHENTICATED,
        is_pinned=False,
        expires_at=None,
        context=context(counselor),
    )
    student_item = create_announcement(
        actor=counselor,
        title="Student notice",
        body_markdown="Student-only notice.",
        audience=PublicationAudience.STUDENTS,
        is_pinned=True,
        expires_at=now + timedelta(hours=2),
        context=context(counselor),
    )
    gco_item = create_announcement(
        actor=counselor,
        title="GCO operations",
        body_markdown="Internal GCO notice.",
        audience=PublicationAudience.GCO_PERSONNEL,
        is_pinned=False,
        expires_at=None,
        context=context(counselor),
    )
    draft = create_announcement(
        actor=counselor,
        title="Draft",
        body_markdown="Not reader visible.",
        audience=PublicationAudience.ALL_AUTHENTICATED,
        is_pinned=False,
        expires_at=None,
        context=context(counselor),
    )

    all_item = publish_announcement(
        actor=counselor,
        announcement_id=all_item.pk,
        context=context(counselor),
        now=now,
    )
    student_item = publish_announcement(
        actor=counselor,
        announcement_id=student_item.pk,
        context=context(counselor),
        now=now + timedelta(seconds=1),
    )
    gco_item = publish_announcement(
        actor=counselor,
        announcement_id=gco_item.pk,
        context=context(counselor),
        now=now + timedelta(seconds=2),
    )

    student_rows = list_visible_announcements(
        actor=student,
        now=now + timedelta(minutes=1),
    ).items
    assert [item.pk for item in student_rows] == [student_item.pk, all_item.pk]
    visible_at = now + timedelta(minutes=1)
    assert {item.pk for item in list_visible_announcements(actor=staff, now=visible_at).items} == {
        all_item.pk,
        gco_item.pk,
    }
    assert {
        item.pk for item in list_visible_announcements(actor=counselor, now=visible_at).items
    } == {
        all_item.pk,
        gco_item.pk,
    }
    assert [item.pk for item in list_visible_announcements(actor=admin, now=visible_at).items] == [
        all_item.pk
    ]
    assert [
        item.pk for item in list_visible_announcements(actor=officer, now=visible_at).items
    ] == [all_item.pk]

    with pytest.raises(AnnouncementNotFound):
        get_visible_announcement(actor=student, announcement_id=draft.pk)
    with pytest.raises(AnnouncementNotFound):
        get_visible_announcement(actor=counselor, announcement_id=student_item.pk)

    original_published_at = all_item.published_at
    updated = update_announcement(
        actor=counselor,
        announcement_id=all_item.pk,
        values={"body_markdown": "Corrected office information.", "is_pinned": True},
        context=context(counselor),
    )
    assert updated.published_at == original_published_at

    archived = archive_announcement(
        actor=counselor,
        announcement_id=all_item.pk,
        context=context(counselor),
    )
    assert archived.status == "ARCHIVED"
    with pytest.raises(AnnouncementNotFound):
        get_visible_announcement(actor=student, announcement_id=all_item.pk)
    with pytest.raises(AnnouncementConflict):
        publish_announcement(
            actor=counselor,
            announcement_id=archived.pk,
            context=context(counselor),
        )

    expired = create_announcement(
        actor=counselor,
        title="Temporary closure",
        body_markdown="Short-lived notice.",
        audience=PublicationAudience.ALL_AUTHENTICATED,
        is_pinned=False,
        expires_at=now + timedelta(minutes=5),
        context=context(counselor),
    )
    publish_announcement(
        actor=counselor,
        announcement_id=expired.pk,
        context=context(counselor),
        now=now,
    )
    assert get_visible_announcement(
        actor=student,
        announcement_id=expired.pk,
        now=now + timedelta(minutes=1),
    )
    with pytest.raises(AnnouncementNotFound):
        get_visible_announcement(
            actor=student,
            announcement_id=expired.pk,
            now=now + timedelta(minutes=6),
        )

    events = AuditEvent.objects.filter(
        target_type="announcements.announcement",
        target_id=str(all_item.pk),
    ).order_by("occurred_at", "id")
    assert [event.action for event in events] == [
        "announcement.created",
        "announcement.published",
        "announcement.updated",
        "announcement.archived",
    ]
    assert "Corrected office information" not in json.dumps([event.metadata for event in events])


@pytest.mark.django_db
def test_announcement_api_enforces_management_and_returns_raw_markdown_without_html_surface():
    sync_policy()
    counselor = make_user("announcement-api-counselor@example.edu", "COUNSELOR")
    staff = make_user("announcement-api-staff@example.edu", "GUIDANCE_SERVICES_STAFF")
    student = make_user("announcement-api-student@example.edu", "STUDENT")
    markdown = "<script>alert('x')</script>\n\n**Guidance source**"

    student_client = auth_client(student)
    response = student_client.post(
        "/api/v1/announcements/management",
        data=json.dumps(
            {
                "title": "Denied",
                "body_markdown": "No.",
                "audience": "STUDENTS",
            }
        ),
        content_type="application/json",
        **csrf(student_client),
    )
    assert response.status_code == 403

    counselor_client = auth_client(counselor)
    response = counselor_client.post(
        "/api/v1/announcements/management",
        data=json.dumps(
            {
                "title": "Safe Markdown contract",
                "body_markdown": markdown,
                "audience": "STUDENTS",
                "is_pinned": False,
            }
        ),
        content_type="application/json",
        **csrf(counselor_client),
    )
    assert response.status_code == 201
    announcement_id = response.json()["id"]

    publish = counselor_client.post(
        f"/api/v1/announcements/management/{announcement_id}/publish",
        **csrf(counselor_client),
    )
    assert publish.status_code == 200

    reader = student_client.get(f"/api/v1/announcements/{announcement_id}")
    assert reader.status_code == 200
    assert reader.json()["body_markdown"] == markdown
    assert "body_html" not in reader.json()
    assert "rendered_html" not in reader.json()

    staff_client = auth_client(staff)
    staff_create = staff_client.post(
        "/api/v1/announcements/management",
        data=json.dumps(
            {
                "title": "Staff-authored",
                "body_markdown": "Guidance Services Staff may publish directly.",
                "audience": "ALL_AUTHENTICATED",
            }
        ),
        content_type="application/json",
        **csrf(staff_client),
    )
    assert staff_create.status_code == 201


@pytest.mark.django_db
def test_public_announcement_audience_is_anonymous_only_when_explicitly_public():
    sync_policy()
    counselor = make_user("announcement-public-publisher@example.edu", "COUNSELOR")
    student = make_user("announcement-public-student@example.edu", "STUDENT")
    staff = make_user("announcement-public-staff@example.edu", "GUIDANCE_SERVICES_STAFF")
    now = timezone.now()

    public_item = create_announcement(
        actor=counselor,
        title="Public guidance notice",
        body_markdown="Public **Markdown** notice.",
        audience=PublicationAudience.PUBLIC,
        is_pinned=True,
        expires_at=now + timedelta(hours=1),
        context=context(counselor),
    )
    all_item = create_announcement(
        actor=counselor,
        title="Authenticated only",
        body_markdown="Signed-in readers only.",
        audience=PublicationAudience.ALL_AUTHENTICATED,
        is_pinned=False,
        expires_at=None,
        context=context(counselor),
    )
    student_item = create_announcement(
        actor=counselor,
        title="Students only",
        body_markdown="Student audience.",
        audience=PublicationAudience.STUDENTS,
        is_pinned=False,
        expires_at=None,
        context=context(counselor),
    )
    gco_item = create_announcement(
        actor=counselor,
        title="GCO only",
        body_markdown="Personnel audience.",
        audience=PublicationAudience.GCO_PERSONNEL,
        is_pinned=False,
        expires_at=None,
        context=context(counselor),
    )
    draft_public = create_announcement(
        actor=counselor,
        title="Draft public",
        body_markdown="Not published.",
        audience=PublicationAudience.PUBLIC,
        is_pinned=False,
        expires_at=None,
        context=context(counselor),
    )

    for item in (public_item, all_item, student_item, gco_item):
        publish_announcement(
            actor=counselor,
            announcement_id=item.pk,
            context=context(counselor),
            now=now,
        )

    anonymous_rows = list_public_announcements(now=now + timedelta(minutes=1)).items
    assert [item.pk for item in anonymous_rows] == [public_item.pk]
    assert (
        get_public_announcement(
            announcement_id=public_item.pk,
            now=now + timedelta(minutes=1),
        ).pk
        == public_item.pk
    )

    future_public = create_announcement(
        actor=counselor,
        title="Future public",
        body_markdown="Not visible yet.",
        audience=PublicationAudience.PUBLIC,
        is_pinned=False,
        expires_at=None,
        context=context(counselor),
    )
    publish_announcement(
        actor=counselor,
        announcement_id=future_public.pk,
        context=context(counselor),
        now=now + timedelta(hours=1),
    )

    archived_public = create_announcement(
        actor=counselor,
        title="Archived public",
        body_markdown="No longer public.",
        audience=PublicationAudience.PUBLIC,
        is_pinned=False,
        expires_at=None,
        context=context(counselor),
    )
    archived_public = publish_announcement(
        actor=counselor,
        announcement_id=archived_public.pk,
        context=context(counselor),
        now=now,
    )
    archive_announcement(
        actor=counselor,
        announcement_id=archived_public.pk,
        context=context(counselor),
    )

    for hidden in (
        all_item,
        student_item,
        gco_item,
        draft_public,
        future_public,
        archived_public,
    ):
        with pytest.raises(AnnouncementNotFound):
            get_public_announcement(
                announcement_id=hidden.pk,
                now=now + timedelta(minutes=1),
            )

    assert {
        item.pk
        for item in list_visible_announcements(actor=student, now=now + timedelta(minutes=1)).items
    } == {public_item.pk, all_item.pk, student_item.pk}
    assert {
        item.pk
        for item in list_visible_announcements(actor=staff, now=now + timedelta(minutes=1)).items
    } == {public_item.pk, all_item.pk, gco_item.pk}

    expired = create_announcement(
        actor=counselor,
        title="Expired public",
        body_markdown="Expired.",
        audience=PublicationAudience.PUBLIC,
        is_pinned=False,
        expires_at=now + timedelta(minutes=2),
        context=context(counselor),
    )
    publish_announcement(
        actor=counselor,
        announcement_id=expired.pk,
        context=context(counselor),
        now=now,
    )
    with pytest.raises(AnnouncementNotFound):
        get_public_announcement(
            announcement_id=expired.pk,
            now=now + timedelta(minutes=3),
        )


@pytest.mark.django_db
def test_public_announcement_api_is_anonymous_and_does_not_leak_other_audiences():
    sync_policy()
    counselor = make_user("announcement-public-api@example.edu", "COUNSELOR")
    client = auth_client(counselor)

    public_create = client.post(
        "/api/v1/announcements/management",
        data=json.dumps(
            {
                "title": "Public API notice",
                "body_markdown": "Visible without sign-in.",
                "audience": "PUBLIC",
                "is_pinned": True,
            }
        ),
        content_type="application/json",
        **csrf(client),
    )
    assert public_create.status_code == 201
    public_id = public_create.json()["id"]
    assert (
        client.post(
            f"/api/v1/announcements/management/{public_id}/publish",
            **csrf(client),
        ).status_code
        == 200
    )

    private_create = client.post(
        "/api/v1/announcements/management",
        data=json.dumps(
            {
                "title": "Signed-in notice",
                "body_markdown": "Not public.",
                "audience": "ALL_AUTHENTICATED",
            }
        ),
        content_type="application/json",
        **csrf(client),
    )
    assert private_create.status_code == 201
    private_id = private_create.json()["id"]
    assert (
        client.post(
            f"/api/v1/announcements/management/{private_id}/publish",
            **csrf(client),
        ).status_code
        == 200
    )

    anonymous = Client()
    listing = anonymous.get("/api/v1/public/announcements?page_size=3")
    assert listing.status_code == 200
    assert [item["id"] for item in listing.json()["items"]] == [public_id]

    detail = anonymous.get(f"/api/v1/public/announcements/{public_id}")
    assert detail.status_code == 200
    assert detail.json()["title"] == "Public API notice"
    assert "body_html" not in detail.json()

    hidden = anonymous.get(f"/api/v1/public/announcements/{private_id}")
    assert hidden.status_code == 404


@pytest.mark.django_db
def test_published_announcement_consequences_require_acknowledgement_and_are_atomic():
    sync_policy()
    actor = make_user("announcement-consequence@example.edu", "COUNSELOR")
    now = timezone.now()
    item = create_announcement(
        actor=actor,
        title="Original title",
        body_markdown="Published body.",
        audience=PublicationAudience.STUDENTS,
        is_pinned=False,
        expires_at=None,
        context=context(actor),
    )
    item = publish_announcement(
        actor=actor,
        announcement_id=item.pk,
        context=context(actor),
        now=now,
    )

    with pytest.raises(AnnouncementPublicationConsequenceReviewRequired) as caught:
        update_announcement(
            actor=actor,
            announcement_id=item.pk,
            values={"title": "Reviewed title", "audience": PublicationAudience.PUBLIC},
            context=context(actor),
            now=now + timedelta(minutes=1),
        )
    assert caught.value.fields == ("audience",)

    item.refresh_from_db()
    assert item.title == "Original title"
    assert item.audience == PublicationAudience.STUDENTS

    item = update_announcement(
        actor=actor,
        announcement_id=item.pk,
        values={"title": "Reviewed title", "audience": PublicationAudience.PUBLIC},
        context=context(actor),
        acknowledge_publication_consequences=True,
        now=now + timedelta(minutes=1),
    )
    assert item.title == "Reviewed title"
    assert item.audience == PublicationAudience.PUBLIC

    event = AuditEvent.objects.filter(
        target_type="announcements.announcement",
        target_id=str(item.pk),
        action="announcement.updated",
    ).latest("occurred_at")
    assert event.metadata["publication_consequences"]["audience"] == {
        "before": PublicationAudience.STUDENTS,
        "after": PublicationAudience.PUBLIC,
    }

    same_audience = update_announcement(
        actor=actor,
        announcement_id=item.pk,
        values={"title": "Typo corrected", "audience": PublicationAudience.PUBLIC},
        context=context(actor),
        now=now + timedelta(minutes=2),
    )
    assert same_audience.title == "Typo corrected"


@pytest.mark.django_db
def test_published_announcement_expiry_review_and_validity_invariants():
    sync_policy()
    actor = make_user("announcement-expiry@example.edu", "COUNSELOR")
    now = timezone.now()
    item = create_announcement(
        actor=actor,
        title="Expiry notice",
        body_markdown="Published body.",
        audience=PublicationAudience.ALL_AUTHENTICATED,
        is_pinned=False,
        expires_at=None,
        context=context(actor),
    )
    item = publish_announcement(
        actor=actor,
        announcement_id=item.pk,
        context=context(actor),
        now=now,
    )
    future = now + timedelta(days=2)

    with pytest.raises(AnnouncementPublicationConsequenceReviewRequired):
        update_announcement(
            actor=actor,
            announcement_id=item.pk,
            values={"expires_at": future},
            context=context(actor),
            now=now + timedelta(minutes=1),
        )
    item.refresh_from_db()
    assert item.expires_at is None

    item = update_announcement(
        actor=actor,
        announcement_id=item.pk,
        values={"expires_at": future},
        context=context(actor),
        acknowledge_publication_consequences=True,
        now=now + timedelta(minutes=1),
    )
    assert item.expires_at == future

    with pytest.raises(AnnouncementPublicationConsequenceReviewRequired):
        update_announcement(
            actor=actor,
            announcement_id=item.pk,
            values={"expires_at": None},
            context=context(actor),
            now=now + timedelta(minutes=2),
        )
    item = update_announcement(
        actor=actor,
        announcement_id=item.pk,
        values={"expires_at": None},
        context=context(actor),
        acknowledge_publication_consequences=True,
        now=now + timedelta(minutes=2),
    )
    assert item.expires_at is None

    with pytest.raises(
        InvalidAnnouncementInput, match="future while the Announcement is published"
    ):
        update_announcement(
            actor=actor,
            announcement_id=item.pk,
            values={"expires_at": now - timedelta(minutes=1)},
            context=context(actor),
            acknowledge_publication_consequences=True,
            now=now + timedelta(minutes=3),
        )
    item.refresh_from_db()
    assert item.expires_at is None

    with pytest.raises(InvalidAnnouncementInput, match="body_markdown is required"):
        update_announcement(
            actor=actor,
            announcement_id=item.pk,
            values={"body_markdown": "   "},
            context=context(actor),
            now=now + timedelta(minutes=4),
        )
    item.refresh_from_db()
    assert item.body_markdown == "Published body."

    archive_announcement(actor=actor, announcement_id=item.pk, context=context(actor))
    with pytest.raises(AnnouncementConflict, match="Archived Announcements cannot be edited"):
        update_announcement(
            actor=actor,
            announcement_id=item.pk,
            values={"title": "No longer editable"},
            context=context(actor),
        )


@pytest.mark.django_db
def test_announcement_api_returns_structured_publication_consequence_review_required():
    sync_policy()
    actor = make_user("announcement-review-api@example.edu", "COUNSELOR")
    client = auth_client(actor)
    created = client.post(
        "/api/v1/announcements/management",
        data=json.dumps(
            {
                "title": "Review boundary",
                "body_markdown": "Published body.",
                "audience": "GCO_PERSONNEL",
            }
        ),
        content_type="application/json",
        **csrf(client),
    )
    assert created.status_code == 201
    announcement_id = created.json()["id"]
    assert (
        client.post(
            f"/api/v1/announcements/management/{announcement_id}/publish",
            **csrf(client),
        ).status_code
        == 200
    )

    rejected = client.patch(
        f"/api/v1/announcements/management/{announcement_id}",
        data=json.dumps({"title": "Atomic title", "audience": "PUBLIC"}),
        content_type="application/json",
        **csrf(client),
    )
    assert rejected.status_code == 409
    assert rejected.json()["error"]["code"] == "publication_consequence_review_required"
    assert rejected.json()["error"]["details"] == {"fields": ["audience"]}

    unchanged = client.get(f"/api/v1/announcements/management/{announcement_id}")
    assert unchanged.status_code == 200
    assert unchanged.json()["title"] == "Review boundary"
    assert unchanged.json()["audience"] == "GCO_PERSONNEL"

    accepted = client.patch(
        f"/api/v1/announcements/management/{announcement_id}",
        data=json.dumps(
            {
                "title": "Atomic title",
                "audience": "PUBLIC",
                "acknowledge_publication_consequences": True,
            }
        ),
        content_type="application/json",
        **csrf(client),
    )
    assert accepted.status_code == 200
    assert accepted.json()["title"] == "Atomic title"
    assert accepted.json()["audience"] == "PUBLIC"

@pytest.mark.django_db
def test_announcement_search_matches_normalizes_filters_orders_and_paginates():
    sync_policy()
    counselor = make_user("announcement-search-publisher@example.edu", "COUNSELOR")
    now = timezone.now()

    pinned = create_announcement(
        actor=counselor,
        title="Mental Health Workshop",
        body_markdown="Registration details.",
        audience=PublicationAudience.PUBLIC,
        is_pinned=True,
        expires_at=None,
        context=context(counselor),
    )
    body_match = create_announcement(
        actor=counselor,
        title="Campus support",
        body_markdown="Practical ANXIETY support is available.",
        audience=PublicationAudience.PUBLIC,
        is_pinned=False,
        expires_at=None,
        context=context(counselor),
    )
    later_title_match = create_announcement(
        actor=counselor,
        title="Mental health follow-up",
        body_markdown="Additional guidance.",
        audience=PublicationAudience.PUBLIC,
        is_pinned=False,
        expires_at=None,
        context=context(counselor),
    )
    unrelated = create_announcement(
        actor=counselor,
        title="Enrollment reminder",
        body_markdown="Bring your registration form.",
        audience=PublicationAudience.PUBLIC,
        is_pinned=False,
        expires_at=None,
        context=context(counselor),
    )

    for offset, item in enumerate((pinned, body_match, later_title_match, unrelated)):
        publish_announcement(
            actor=counselor,
            announcement_id=item.pk,
            context=context(counselor),
            now=now + timedelta(seconds=offset),
        )

    title_rows = list_public_announcements(
        search="  MENTAL health  ",
        now=now + timedelta(minutes=1),
    ).items
    assert [item.pk for item in title_rows] == [pinned.pk, later_title_match.pk]

    body_rows = list_public_announcements(
        search="anxiety",
        now=now + timedelta(minutes=1),
    ).items
    assert [item.pk for item in body_rows] == [body_match.pk]

    blank_rows = list_public_announcements(
        search="   ",
        now=now + timedelta(minutes=1),
    ).items
    baseline_rows = list_public_announcements(now=now + timedelta(minutes=1)).items
    assert [item.pk for item in blank_rows] == [item.pk for item in baseline_rows]
    assert not list_public_announcements(
        search="does-not-exist",
        now=now + timedelta(minutes=1),
    ).items

    pinned_rows = list_public_announcements(
        pinned=True,
        search="mental",
        now=now + timedelta(minutes=1),
    ).items
    assert [item.pk for item in pinned_rows] == [pinned.pk]

    page_one = list_public_announcements(
        search="mental",
        page=1,
        page_size=1,
        now=now + timedelta(minutes=1),
    )
    page_two = list_public_announcements(
        search="mental",
        page=2,
        page_size=1,
        now=now + timedelta(minutes=1),
    )
    assert [item.pk for item in page_one.items] == [pinned.pk]
    assert page_one.has_next is True
    assert [item.pk for item in page_two.items] == [later_title_match.pk]
    assert page_two.has_next is False


@pytest.mark.django_db
def test_announcement_search_preserves_visibility_management_filters_and_api_contract():
    sync_policy()
    counselor = make_user("announcement-search-manager@example.edu", "COUNSELOR")
    student = make_user("announcement-search-student@example.edu", "STUDENT")
    now = timezone.now()

    public_item = create_announcement(
        actor=counselor,
        title="Search needle public",
        body_markdown="Visible public content.",
        audience=PublicationAudience.PUBLIC,
        is_pinned=False,
        expires_at=None,
        context=context(counselor),
    )
    student_item = create_announcement(
        actor=counselor,
        title="Student notice",
        body_markdown="Contains search NEEDLE for students.",
        audience=PublicationAudience.STUDENTS,
        is_pinned=False,
        expires_at=None,
        context=context(counselor),
    )
    gco_item = create_announcement(
        actor=counselor,
        title="Needle GCO operations",
        body_markdown="Internal content.",
        audience=PublicationAudience.GCO_PERSONNEL,
        is_pinned=False,
        expires_at=None,
        context=context(counselor),
    )
    draft_public = create_announcement(
        actor=counselor,
        title="Needle draft",
        body_markdown="Management only.",
        audience=PublicationAudience.PUBLIC,
        is_pinned=False,
        expires_at=None,
        context=context(counselor),
    )
    expired = create_announcement(
        actor=counselor,
        title="Needle expired",
        body_markdown="Short lived.",
        audience=PublicationAudience.PUBLIC,
        is_pinned=False,
        expires_at=now + timedelta(minutes=2),
        context=context(counselor),
    )
    archived = create_announcement(
        actor=counselor,
        title="Needle archived",
        body_markdown="No longer visible.",
        audience=PublicationAudience.PUBLIC,
        is_pinned=False,
        expires_at=None,
        context=context(counselor),
    )

    for item in (public_item, student_item, gco_item, expired, archived):
        publish_announcement(
            actor=counselor,
            announcement_id=item.pk,
            context=context(counselor),
            now=now,
        )
    archive_announcement(
        actor=counselor,
        announcement_id=archived.pk,
        context=context(counselor),
    )

    public_rows = list_public_announcements(
        search="needle",
        now=now + timedelta(minutes=3),
    ).items
    assert [item.pk for item in public_rows] == [public_item.pk]

    visible_rows = list_visible_announcements(
        actor=student,
        search="needle",
        now=now + timedelta(minutes=3),
    ).items
    assert {item.pk for item in visible_rows} == {public_item.pk, student_item.pk}

    assert not list_public_announcements(
        search="PUBLIC",
        now=now + timedelta(minutes=3),
    ).items

    anonymous = Client()
    public_api = anonymous.get("/api/v1/public/announcements?search=needle&page_size=10")
    assert public_api.status_code == 200
    assert [item["id"] for item in public_api.json()["items"]] == [str(public_item.pk)]

    visible_api = auth_client(student).get("/api/v1/announcements?search=needle&page_size=10")
    assert visible_api.status_code == 200
    assert {item["id"] for item in visible_api.json()["items"]} == {
        str(public_item.pk),
        str(student_item.pk),
    }

    manager = auth_client(counselor)
    managed_draft = manager.get(
        "/api/v1/announcements/management"
        "?search=needle&status=DRAFT&audience=PUBLIC&page_size=10"
    )
    assert managed_draft.status_code == 200
    assert [item["id"] for item in managed_draft.json()["items"]] == [str(draft_public.pk)]

    managed_gco = manager.get(
        "/api/v1/announcements/management"
        "?search=needle&audience=GCO_PERSONNEL&page_size=10"
    )
    assert managed_gco.status_code == 200
    assert [item["id"] for item in managed_gco.json()["items"]] == [str(gco_item.pk)]
