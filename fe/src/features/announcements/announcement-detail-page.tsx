"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState, type ReactNode } from "react";

import { announcementErrorCode, announcementErrorMessage, shouldHideAnnouncementData } from "@/features/announcements/announcement-errors";
import { AnnouncementLifecycleActions } from "@/features/announcements/announcement-lifecycle-actions";
import { isAnnouncementExpired } from "@/features/announcements/announcement-presentation";
import { displayTitle, publicationAudienceLabels } from "@/features/content/content-presentation";
import {
  ContentDetailSkeleton,
  ContentNotice,
  ContentPageHeading,
  ContentQueryError,
  PublicationStatusBadge,
  contentSecondaryLinkClass,
} from "@/features/content/content-shared";
import { PublicMarkdown } from "@/features/public/shared/public-markdown";
import { useAnnouncementsGetManaged } from "@/lib/api/generated/announcements/announcements";
import { AnnouncementAudienceValue, AnnouncementStatusValue } from "@/lib/api/generated/model";
import { formatInstitutionalDateTime } from "@/lib/institutional-time";

function Detail({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-semibold text-muted">{label}</dt>
      <dd className="mt-1 break-words text-sm text-ink">{children}</dd>
    </div>
  );
}

export function AnnouncementUnavailable({ error, onRetry }: { error: unknown; onRetry: () => void }) {
  const notFound = announcementErrorCode(error) === "announcement_not_found";
  return (
    <section className="space-y-6">
      <ContentPageHeading
        title={notFound ? "Announcement not found" : "Announcement unavailable"}
        backHref="/portal/announcements"
        backLabel="Announcements"
      />
      {notFound ? (
        <p className="border-y border-border py-6 text-sm leading-6 text-muted">
          This Announcement does not exist or is no longer available.
        </p>
      ) : (
        <ContentQueryError
          message={announcementErrorMessage(error, "This Announcement could not be loaded.")}
          onRetry={shouldHideAnnouncementData(error) ? undefined : onRetry}
        />
      )}
    </section>
  );
}

export function AnnouncementDetailPage({ announcementId }: { announcementId: string }) {
  const searchParams = useSearchParams();
  const detail = useAnnouncementsGetManaged(announcementId, { query: { retry: false } });
  const [notice, setNotice] = useState<string | null>(() =>
    searchParams.get("notice") === "created"
      ? "Draft saved. Review it below, then publish it when it is ready."
      : null,
  );

  if (detail.isPending) return <ContentDetailSkeleton label="Loading Announcement…" />;
  if (!detail.data || (detail.isError && shouldHideAnnouncementData(detail.error))) {
    return <AnnouncementUnavailable error={detail.error} onRetry={() => void detail.refetch()} />;
  }

  const item = detail.data.data;
  const title = displayTitle(item.title, "Untitled Announcement");
  const isDraft = item.status === AnnouncementStatusValue.DRAFT;
  const isPublished = item.status === AnnouncementStatusValue.PUBLISHED;
  const expired = isAnnouncementExpired(item);
  const missing = [
    item.title.trim() ? null : "a title",
    item.body_markdown.trim() ? null : "body text",
  ].filter((value): value is string => value !== null);

  return (
    <article aria-busy={detail.isFetching}>
      <ContentPageHeading
        title={title}
        backHref="/portal/announcements"
        backLabel="Announcements"
        action={
          <>
            {item.status !== AnnouncementStatusValue.ARCHIVED ? (
              <Link href={`/portal/announcements/${item.id}/edit`} className={contentSecondaryLinkClass}>
                Edit Announcement
              </Link>
            ) : null}
            <AnnouncementLifecycleActions
              announcement={item}
              publishBlocked={missing.length > 0}
              onCompleted={setNotice}
            />
          </>
        }
      >
        <div className="mt-3 flex flex-wrap items-center gap-3 text-sm text-muted">
          <PublicationStatusBadge status={item.status} />
          <span>{publicationAudienceLabels[item.audience]}</span>
          {item.is_pinned ? <span>Pinned</span> : null}
        </div>
      </ContentPageHeading>

      <div className="mt-6 space-y-3">
        {notice ? <ContentNotice tone="success">{notice}</ContentNotice> : null}
        {isDraft && missing.length > 0 ? (
          <ContentNotice tone="warning">Add {missing.join(" and ")} before publishing.</ContentNotice>
        ) : null}
        {isDraft && expired && item.expires_at ? (
          <ContentNotice tone="warning">
            The expiry, {formatInstitutionalDateTime(item.expires_at)}, has already passed. Change or remove it before publishing.
          </ContentNotice>
        ) : null}
        {isPublished && expired && item.expires_at ? (
          <ContentNotice tone="info">
            This Announcement stopped being shown on {formatInstitutionalDateTime(item.expires_at)}. Readers no longer see it.
          </ContentNotice>
        ) : null}
        {detail.isError ? (
          <ContentQueryError
            message={`${announcementErrorMessage(detail.error, "The latest Announcement details could not be loaded.")} Showing the last loaded version.`}
            onRetry={() => void detail.refetch()}
          />
        ) : detail.isFetching ? (
          <p role="status" className="text-xs text-muted">Refreshing Announcement…</p>
        ) : null}
      </div>

      <dl className="mt-6 grid gap-x-8 gap-y-4 border-y border-border py-5 sm:grid-cols-2 lg:grid-cols-3">
        <Detail label="Audience">{publicationAudienceLabels[item.audience]}</Detail>
        <Detail label="Pinned">{item.is_pinned ? "Yes" : "No"}</Detail>
        <Detail label="Stop showing after">
          {item.expires_at ? formatInstitutionalDateTime(item.expires_at) : "No expiry"}
        </Detail>
        <Detail label="Published">
          {item.published_at
            ? `${formatInstitutionalDateTime(item.published_at)}${item.published_by ? ` by ${item.published_by.display_name}` : ""}`
            : "Not published"}
        </Detail>
        <Detail label="Created">
          {formatInstitutionalDateTime(item.created_at)} by {item.created_by.display_name}
        </Detail>
        <Detail label="Last updated">
          {formatInstitutionalDateTime(item.updated_at)} by {item.updated_by.display_name}
        </Detail>
      </dl>

      {isPublished && item.audience === AnnouncementAudienceValue.PUBLIC && !expired ? (
        <p className="mt-4 text-sm">
          <Link
            href={`/announcements/${item.id}`}
            className="font-semibold text-brand underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          >
            Open the public Announcement page
          </Link>
        </p>
      ) : null}

      <section aria-labelledby="announcement-body-heading" className="mt-8">
        <h2 id="announcement-body-heading" className="font-heading text-xl font-semibold text-ink">
          Body
        </h2>
        <p className="mt-1 text-sm text-muted">As readers see it.</p>
        <div className="mt-4 max-w-3xl rounded-md border border-border bg-surface-raised px-5 py-5 sm:px-6">
          {item.body_markdown.trim() ? (
            <PublicMarkdown>{item.body_markdown}</PublicMarkdown>
          ) : (
            <p className="text-sm text-muted">No body text yet.</p>
          )}
        </div>
      </section>
    </article>
  );
}
