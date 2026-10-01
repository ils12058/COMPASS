"use client";

import { Pin } from "lucide-react";
import Link from "next/link";

import { Label } from "@/components/ui/label";
import { safeQueryData } from "@/features/freshness/query-freshness";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
import { announcementErrorMessage } from "@/features/announcements/announcement-errors";
import { announcementTimingLine } from "@/features/announcements/announcement-presentation";
import {
  displayTitle,
  isPublicationAudience,
  isPublicationStatus,
  publicationAudienceLabels,
  publicationAudienceOrder,
  publicationStatusLabels,
  publicationStatusOrder,
} from "@/features/content/content-presentation";
import {
  ContentListSkeleton,
  ContentPageHeading,
  ContentQueryError,
  PublicationStatusBadge,
  contentPrimaryLinkClass,
  contentRecordLinkClass,
  contentSelectClass,
} from "@/features/content/content-shared";
import { useContentListParams } from "@/features/content/use-content-list-params";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { useAnnouncementsListManaged } from "@/lib/api/generated/announcements/announcements";

const clearLinkClass =
  "inline-flex min-h-10 items-center text-sm font-semibold text-brand underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus";

export function AnnouncementsListPage() {
  const { searchParams, page, hrefWith, update, setPage } = useContentListParams();
  const statusParam = searchParams.get("status");
  const audienceParam = searchParams.get("audience");
  const status = isPublicationStatus(statusParam) ? statusParam : undefined;
  const audience = isPublicationAudience(audienceParam) ? audienceParam : undefined;
  const hasFilters = Boolean(status || audience);

  const list = useAnnouncementsListManaged(
    {
      ...(status ? { status } : {}),
      ...(audience ? { audience } : {}),
      page,
      page_size: 20,
    },
    { query: { retry: false } },
  );
  const result = safeQueryData(list)?.data;

  return (
    <section aria-labelledby="announcements-heading">
      <ContentPageHeading
        title="Announcements"
        headingId="announcements-heading"
        action={
          <Link href="/portal/announcements/new" className={contentPrimaryLinkClass}>
            Create Announcement
          </Link>
        }
      />

      <div className="mt-8 flex flex-col gap-4 border-y border-border py-5 sm:flex-row sm:flex-wrap sm:items-end">
        <div className="grid gap-2 sm:w-52">
          <Label htmlFor="announcement-status-filter">Status</Label>
          <select
            id="announcement-status-filter"
            className={contentSelectClass}
            value={status ?? ""}
            onChange={(event) => update({ status: event.target.value || null })}
          >
            <option value="">All statuses</option>
            {publicationStatusOrder.map((value) => (
              <option key={value} value={value}>
                {publicationStatusLabels[value]}
              </option>
            ))}
          </select>
        </div>
        <div className="grid gap-2 sm:w-60">
          <Label htmlFor="announcement-audience-filter">Audience</Label>
          <select
            id="announcement-audience-filter"
            className={contentSelectClass}
            value={audience ?? ""}
            onChange={(event) => update({ audience: event.target.value || null })}
          >
            <option value="">All audiences</option>
            {publicationAudienceOrder.map((value) => (
              <option key={value} value={value}>
                {publicationAudienceLabels[value]}
              </option>
            ))}
          </select>
        </div>
        {hasFilters ? (
          <Link href={hrefWith({ status: null, audience: null })} className={clearLinkClass} scroll={false}>
            Clear filters
          </Link>
        ) : null}
      </div>
      {list.isError && result ? <RefreshFailureNotice onRetry={() => void list.refetch()} retrying={list.isFetching} /> : null}

      {list.isPending ? (
        <ContentListSkeleton label="Loading Announcements…" />
      ) : !result ? (
        <div className="mt-5">
          <ContentQueryError
            message={announcementErrorMessage(list.error, "Announcements could not be loaded.")}
            onRetry={() => void list.refetch()}
          />
        </div>
      ) : result && result.items.length === 0 ? (
        <div className="border-b border-border py-8">
          <p className="text-sm text-muted">
            {page > 1
              ? "No Announcements are on this page."
              : hasFilters
                ? "No Announcements match the selected filters."
                : "No Announcements have been created yet."}
          </p>
          {page > 1 ? (
            <Link href={hrefWith({ page: null }, false)} className={`mt-2 ${clearLinkClass}`}>
              Go to the first page
            </Link>
          ) : hasFilters ? (
            <Link href={hrefWith({ status: null, audience: null })} className={`mt-2 ${clearLinkClass}`} scroll={false}>
              Clear filters
            </Link>
          ) : null}
        </div>
      ) : result ? (
        <>
          {list.isFetching ? (
            <p role="status" className="mt-4 text-xs text-muted">
              Refreshing Announcements…
            </p>
          ) : null}
          <ul className="mt-5 divide-y divide-border border-y border-border">
            {result.items.map((item) => (
              <li key={item.id} className="py-4">
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  <Link
                    href={`/portal/announcements/${item.id}`}
                    className={`${contentRecordLinkClass} break-words font-heading text-lg`}
                  >
                    {displayTitle(item.title, "Untitled Announcement")}
                  </Link>
                  <PublicationStatusBadge status={item.status} />
                  {item.is_pinned ? (
                    <span className="inline-flex items-center gap-1 text-xs font-semibold text-brand">
                      <Pin size={13} aria-hidden="true" />
                      Pinned
                    </span>
                  ) : null}
                </div>
                <p className="mt-1 text-sm text-muted">
                  {publicationAudienceLabels[item.audience]} · {announcementTimingLine(item)}
                </p>
              </li>
            ))}
          </ul>
          {page > 1 || result.has_next ? (
            <CanonicalPagination
              page={result.page}
              hasNext={result.has_next}
              label="Announcement pages"
              onPageChange={setPage}
            />
          ) : null}
        </>
      ) : null}
    </section>
  );
}
