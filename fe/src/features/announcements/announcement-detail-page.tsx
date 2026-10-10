"use client";

import { Pencil } from "lucide-react";
import { PageActionLink } from "@/components/ui/page-action";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState, type ReactNode } from "react";

import { Notice } from "@/components/ui/notice";
import { Panel, PanelSection } from "@/components/ui/panel";
import { announcementErrorCode, announcementErrorMessage, shouldHideAnnouncementData } from "@/features/announcements/announcement-errors";
import { canShowLastKnownData } from "@/features/freshness/query-freshness";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
import { AnnouncementLifecycleActions } from "@/features/announcements/announcement-lifecycle-actions";
import { isAnnouncementExpired } from "@/features/announcements/announcement-presentation";
import { displayTitle, publicationAudienceLabels } from "@/features/content/content-presentation";
import { listReturnHref } from "@/features/content/list-return-href";
import {
  ContentDetailSkeleton,
  ContentNotice,
  ContentPageHeading,
  ContentQueryError,
  PublicationStatusBadge,
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

export function AnnouncementUnavailable({ error, onRetry, backHref = "/portal/announcements" }: { error: unknown; onRetry: () => void; backHref?: string }) {
  const notFound = announcementErrorCode(error) === "announcement_not_found";
  return (
    <section className="space-y-5">
      <ContentPageHeading
        title={notFound ? "Announcement not found" : "Announcement unavailable"}
        backHref={backHref}
        backLabel="Announcements"
      />
      {notFound ? (
        <Notice>
          This Announcement does not exist or is no longer available.
        </Notice>
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
  const backHref = listReturnHref("/portal/announcements", new URLSearchParams(searchParams.toString()), ["search", "status", "audience", "page"]);
  const detail = useAnnouncementsGetManaged(announcementId, { query: { retry: false } });
  const [notice, setNotice] = useState<string | null>(() =>
    searchParams.get("notice") === "created"
      ? "Draft saved. Review it below, then publish it when it is ready."
      : null,
  );

  if (detail.isPending) return <ContentDetailSkeleton label="Loading announcement…" />;
  if (!detail.data || (detail.isError && !canShowLastKnownData(detail))) {
    return <AnnouncementUnavailable error={detail.error} onRetry={() => void detail.refetch()} backHref={backHref} />;
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
        backHref={backHref}
        backLabel="Announcements"
        action={!detail.isError ?
          <>
            {item.status !== AnnouncementStatusValue.ARCHIVED ? (
              <PageActionLink href={`/portal/announcements/${item.id}/edit`} icon={Pencil} variant="secondary" label="Edit Announcement" />
            ) : null}
            <AnnouncementLifecycleActions
              announcement={item}
              publishBlocked={missing.length > 0}
              onCompleted={setNotice}
            />
          </>
        : null}
      >
        <div className="mt-3 flex flex-wrap items-center gap-3 text-sm text-muted">
          <PublicationStatusBadge status={item.status} />
          <span>{publicationAudienceLabels[item.audience]}</span>
          {item.is_pinned ? <span>Pinned</span> : null}
        </div>
      </ContentPageHeading>

      <div className="mt-5 space-y-3 empty:hidden">
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
          <RefreshFailureNotice onRetry={() => void detail.refetch()} retrying={detail.isFetching} />
        ) : detail.isFetching ? (
          <p role="status" className="text-xs text-muted">Refreshing Announcement…</p>
        ) : null}
      </div>

      {/* The record sheet: publication facts, then the file and body as readers get them. */}
      <Panel as="div" className="mt-5">
      <dl className="grid gap-x-8 gap-y-4 px-4 py-4 sm:grid-cols-2 sm:px-5 lg:grid-cols-3">
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
        <p className="border-t border-brand-line px-4 py-3 text-sm sm:px-5">
          <Link
            href={`/announcements/${item.id}`}
            className="font-semibold text-brand underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          >
            Open the public Announcement page
          </Link>
        </p>
      ) : null}

      <PanelSection title="Body" titleId="announcement-body-heading">
        <p className="text-sm text-muted">As readers see it.</p>
        <div className="mt-4 max-w-3xl">
          {item.body_markdown.trim() ? (
            <PublicMarkdown>{item.body_markdown}</PublicMarkdown>
          ) : (
            <p className="text-sm text-muted">No body text yet.</p>
          )}
        </div>
      </PanelSection>
      </Panel>
    </article>
  );
}
