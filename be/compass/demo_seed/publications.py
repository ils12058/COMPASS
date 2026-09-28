"""Announcements, Resources, Privacy Governance, and Feedback seeded through their services.

These records have no scenario owner, so each is matched by a stable natural key (author and
title, policy or notice code, or respondent and response text) and created only when absent.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from django.db import transaction

from compass.announcements.models import Announcement
from compass.announcements.services import (
    archive_announcement,
    create_announcement,
    publish_announcement,
)
from compass.counseling.models import CounselingEncounter
from compass.feedback.models import (
    ClientSatisfactionResponse,
    CustomerFeedbackResponse,
    CustomerFeedbackService,
    FeedbackOpportunity,
    FeedbackOpportunitySourceType,
)
from compass.feedback.services import (
    create_csm_response,
    create_customer_feedback,
    ensure_feedback_opportunity,
)
from compass.good_moral.models import GoodMoralRequest, GoodMoralStatus, GoodMoralVariant
from compass.privacy_governance.expansion import (
    acknowledge_revision,
    create_notice,
    create_retention,
    create_revision,
    publish_revision,
)
from compass.privacy_governance.models import (
    PrivacyNotice,
    PrivacyNoticeRevisionStatus,
    RetentionPolicy,
)
from compass.resources.models import Resource
from compass.resources.services import archive_resource, create_resource, publish_resource

from . import narratives, publication_data
from .cast import DPO, HEAD_GUIDANCE, PERSONAS_BY_KEY, SECOND_YEAR
from .publication_data import AnnouncementSpec, ResourceSpec
from .support import DemoSeedError, SeedSession, align_timestamps

DRAFTED_BEFORE_PUBLISHING = timedelta(minutes=25)
ARCHIVED_AFTER = timedelta(days=28)


def _published_at(session: SeedSession, spec) -> datetime | None:
    if spec.published_on is not None:
        return session.timeline.on(*spec.published_on)
    if spec.published_days_ago is not None:
        return session.timeline.past(spec.published_days_ago, 8, 30)
    return None


def _author_available(session: SeedSession, spec) -> bool:
    author = session.user(spec.author)
    if author.is_active:
        return True
    session.notes.append(
        f"Skipped '{spec.title}': its author account is disabled and cannot author new content."
    )
    return False


def _seed_announcement(session: SeedSession, spec: AnnouncementSpec) -> None:
    author = session.users[spec.author]
    if Announcement.objects.filter(created_by=author, title=spec.title).exists():
        session.record("Announcements", created=False)
        return
    if not _author_available(session, spec):
        return
    published_at = _published_at(session, spec)
    drafted_at = (published_at or session.timeline.past(1, 16)) - DRAFTED_BEFORE_PUBLISHING
    expires_at = (
        session.timeline.future(spec.expires_in_business_days, 17)
        if spec.expires_in_business_days is not None
        else None
    )
    item = create_announcement(
        actor=session.user(spec.author),
        title=spec.title,
        body_markdown=spec.body_markdown,
        audience=spec.audience,
        is_pinned=spec.is_pinned,
        expires_at=expires_at,
        context=session.as_user(spec.author),
    )
    last_change = drafted_at
    if published_at is not None:
        publish_announcement(
            actor=session.user(spec.author),
            announcement_id=item.pk,
            context=session.as_user(spec.author),
            now=published_at,
        )
        last_change = published_at
    if spec.state == "ARCHIVED":
        archive_announcement(
            actor=session.user(HEAD_GUIDANCE.key),
            announcement_id=item.pk,
            context=session.as_user(HEAD_GUIDANCE.key),
        )
        last_change = (published_at or drafted_at) + ARCHIVED_AFTER
    align_timestamps(item, created_at=drafted_at, updated_at=last_change)
    session.record("Announcements", created=True)


def _seed_resource(session: SeedSession, spec: ResourceSpec) -> None:
    author = session.users[spec.author]
    if Resource.objects.filter(created_by=author, title=spec.title).exists():
        session.record("Resources", created=False)
        return
    if not _author_available(session, spec):
        return
    published_at = _published_at(session, spec)
    drafted_at = (published_at or session.timeline.past(2, 15)) - DRAFTED_BEFORE_PUBLISHING
    item = create_resource(
        actor=session.user(spec.author),
        title=spec.title,
        body_markdown=spec.body_markdown,
        category=spec.category,
        kind=spec.kind,
        audience=spec.audience,
        external_url=spec.external_url or None,
        display_order=spec.display_order,
        context=session.as_user(spec.author),
    )
    timestamps = {"created_at": drafted_at, "updated_at": drafted_at}
    if published_at is not None:
        publish_resource(
            actor=session.user(spec.author),
            resource_id=item.pk,
            context=session.as_user(spec.author),
        )
        timestamps.update(published_at=published_at, updated_at=published_at)
    if spec.state == "ARCHIVED":
        archive_resource(
            actor=session.user(HEAD_GUIDANCE.key),
            resource_id=item.pk,
            context=session.as_user(HEAD_GUIDANCE.key),
        )
        timestamps["updated_at"] = (published_at or drafted_at) + ARCHIVED_AFTER
    align_timestamps(item, **timestamps)
    session.record("Resources", created=True)


def seed_publications(session: SeedSession) -> None:
    with transaction.atomic():
        for spec in publication_data.ANNOUNCEMENTS:
            _seed_announcement(session, spec)
        for spec in publication_data.RESOURCES:
            _seed_resource(session, spec)


def _date(parts: tuple[int, int, int] | None) -> date | None:
    return None if parts is None else date(*parts)


def seed_privacy_governance(session: SeedSession) -> None:
    dpo_context = session.as_user(DPO.key)
    t = session.timeline
    with transaction.atomic():
        for policy in publication_data.RETENTION_POLICIES:
            exists = RetentionPolicy.objects.filter(code=policy["code"]).exists()
            if not exists:
                values = {
                    key: value
                    for key, value in policy.items()
                    if key not in {"code", "effective_on", "review_due_on"}
                }
                item = create_retention(
                    code=policy["code"],
                    context=dpo_context,
                    effective_on=_date(policy["effective_on"]),
                    review_due_on=_date(policy["review_due_on"]),
                    **values,
                )
                adopted = t.on(2026, 7, 28, 15)
                align_timestamps(item, created_at=adopted, updated_at=adopted)
            session.record("Retention Policies", created=not exists)

        notice_spec = publication_data.PRIVACY_NOTICE
        notice = PrivacyNotice.objects.filter(code=notice_spec["code"]).first()
        if notice is None:
            published = dict(publication_data.PRIVACY_NOTICE_PUBLISHED)
            published["effective_on"] = _date(published["effective_on"])
            notice = create_notice(
                actor=session.user(DPO.key),
                context=dpo_context,
                code=notice_spec["code"],
                name=notice_spec["name"],
                **published,
            )
            first = notice.revisions.get(revision_number=1)
            publish_revision(revision_id=first.pk, actor=session.user(DPO.key), context=dpo_context)
            drafted_at = t.on(2026, 7, 29, 10)
            published_at = t.on(2026, 8, 3, 9)
            align_timestamps(notice, created_at=drafted_at, updated_at=drafted_at)
            align_timestamps(
                first,
                created_at=drafted_at,
                updated_at=published_at,
                published_at=published_at,
            )
            session.record("Privacy Notices", created=True)
        else:
            session.record("Privacy Notices", created=False)

        if not notice.revisions.filter(status=PrivacyNoticeRevisionStatus.DRAFT).exists() and (
            notice.revisions.count() < 2
        ):
            draft = create_revision(
                notice_id=notice.pk,
                actor=session.user(DPO.key),
                context=dpo_context,
                **publication_data.PRIVACY_NOTICE_DRAFT,
            )
            align_timestamps(draft, created_at=t.past(5, 15), updated_at=t.past(5, 15))
            session.record("Privacy Notice revisions", created=True)

        # One Student has already acknowledged the current notice; the others still see it pending.
        current = notice.revisions.filter(status=PrivacyNoticeRevisionStatus.PUBLISHED).first()
        student = session.user(SECOND_YEAR.key)
        if current is not None and not current.acknowledgments.filter(user=student).exists():
            acknowledge_revision(
                revision_id=current.pk,
                actor=student,
                context=session.as_user(SECOND_YEAR.key),
            )


# Customer Feedback and CSM are submitted after the services they describe.
FEEDBACK_TIMES = {
    "second_year": ("past", 9, 18, 20),
    "good_moral": ("past", 6, 12, 10),
    "recent_graduate": ("on", (2026, 7, 15, 16, 5)),
    "referred": ("past", 4, 18, 40),
}


def _feedback_time(session: SeedSession, persona_key: str, *, offset_minutes: int = 0):
    spec = FEEDBACK_TIMES[persona_key]
    if spec[0] == "on":
        base = session.timeline.on(*spec[1])
    else:
        base = session.timeline.past(spec[1], spec[2], spec[3])
    return base + timedelta(minutes=offset_minutes)


def _demo_feedback_opportunity(
    session: SeedSession,
    persona_key: str,
) -> FeedbackOpportunity:
    student = session.user(persona_key)
    if persona_key in {"second_year", "referred"}:
        encounter = (
            CounselingEncounter.objects.filter(student=student).order_by("-ended_at", "-id").first()
        )
        if encounter is None:
            raise DemoSeedError(
                f"Demo Feedback source Counseling Encounter is missing for {persona_key}."
            )
        return ensure_feedback_opportunity(
            student=student,
            source_type=FeedbackOpportunitySourceType.COUNSELING_ENCOUNTER,
            source_id=encounter.pk,
            service_kind=CustomerFeedbackService.COUNSELING,
            service_label_snapshot="Counseling",
            service_completed_at=encounter.ended_at,
        )

    request = (
        GoodMoralRequest.objects.filter(
            student=student,
            status=GoodMoralStatus.ISSUED,
            issued_at__isnull=False,
        )
        .order_by("-issued_at", "-id")
        .first()
    )
    if request is None or request.issued_at is None:
        raise DemoSeedError(
            f"Demo Feedback source issued Good Moral request is missing for {persona_key}."
        )
    return ensure_feedback_opportunity(
        student=student,
        source_type=FeedbackOpportunitySourceType.GOOD_MORAL_REQUEST,
        source_id=request.pk,
        service_kind=CustomerFeedbackService.REQUEST_FOR_CERTIFICATION,
        service_label_snapshot=(
            "Issuance of Good Moral Certificate"
            if request.variant == GoodMoralVariant.CURRENT_STUDENT
            else "Issuance of Good Moral Certificate (graduate)"
        ),
        service_completed_at=request.issued_at,
    )


def _stamp_demo_feedback_marker(
    opportunity: FeedbackOpportunity,
    *,
    customer_feedback_at=None,
    csm_at=None,
) -> None:
    updates: list[str] = []
    if customer_feedback_at is not None and opportunity.customer_feedback_submitted_at is None:
        opportunity.customer_feedback_submitted_at = customer_feedback_at
        updates.append("customer_feedback_submitted_at")
    if csm_at is not None and opportunity.csm_submitted_at is None:
        opportunity.csm_submitted_at = csm_at
        updates.append("csm_submitted_at")
    if updates:
        opportunity.save(update_fields=[*updates, "updated_at"])


def seed_feedback(session: SeedSession) -> None:
    with transaction.atomic():
        opportunities = {
            persona_key: _demo_feedback_opportunity(session, persona_key)
            for persona_key in FEEDBACK_TIMES
        }

        for persona_key, values in narratives.CUSTOMER_FEEDBACK.items():
            persona = PERSONAS_BY_KEY[persona_key]
            existing = CustomerFeedbackResponse.objects.filter(
                respondent_name_snapshot=persona.full_name,
                additional_feedback=values["additional_feedback"],
            ).first()
            created = existing is None
            if existing is None:
                existing = create_customer_feedback(
                    student=session.user(persona_key),
                    opportunity_id=opportunities[persona_key].pk,
                    values=dict(values),
                    context=session.as_user(persona_key),
                )
                align_timestamps(existing, submitted_at=_feedback_time(session, persona_key))
            _stamp_demo_feedback_marker(
                opportunities[persona_key],
                customer_feedback_at=existing.submitted_at,
            )
            session.record("Customer Feedback", created=created)

        for response in narratives.CLIENT_SATISFACTION:
            persona_key = response["persona"]
            values = {key: value for key, value in response.items() if key != "persona"}
            existing = ClientSatisfactionResponse.objects.filter(
                service_availed=values["service_availed"],
                suggestions=values["suggestions"],
                age=values["age"],
                sex=values["sex"],
            ).first()
            created = existing is None
            if existing is None:
                existing = create_csm_response(
                    student=session.user(persona_key),
                    opportunity_id=opportunities[persona_key].pk,
                    values=values,
                    context=session.as_user(persona_key),
                )
                align_timestamps(
                    existing,
                    submitted_at=_feedback_time(session, persona_key, offset_minutes=6),
                )
            _stamp_demo_feedback_marker(
                opportunities[persona_key],
                csm_at=existing.submitted_at,
            )
            session.record("CSM responses", created=created)


__all__ = ["seed_feedback", "seed_privacy_governance", "seed_publications"]
