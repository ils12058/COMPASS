"use client";

import { Pin } from "lucide-react";
import Link from "next/link";

import { Select } from "@/components/ui/select";
import { Button, buttonVariants } from "@/components/ui/button";
import { FilterField, FilterToolbar } from "@/components/ui/filter-toolbar";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { describeResultPage } from "@/features/portal/components/result-context";
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
  PublicationStatusBadge,
  contentPrimaryLinkClass,
  contentRecordLinkClass,
} from "@/features/content/content-shared";
import { useContentListParams } from "@/features/content/use-content-list-params";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { useAnnouncementsListManaged } from "@/lib/api/generated/announcements/announcements";

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

      {/* Two selects, so each choice applies as soon as it changes. */}
      <FilterToolbar
        className="mt-5"
        fieldsClassName="lg:grid-cols-[repeat(2,minmax(0,16rem))]"
        actions={hasFilters ? (
          <Link href={hrefWith({ status: null, audience: null })} className={buttonVariants({ variant: "quiet" })} scroll={false}>
            Clear filters
          </Link>
        ) : undefined}
      >
        <FilterField label="Status" htmlFor="announcement-status-filter">
          <Select
            id="announcement-status-filter"
            value={status ?? ""}
            onChange={(event) => update({ status: event.target.value || null })}
          >
            <option value="">All statuses</option>
            {publicationStatusOrder.map((value) => (
              <option key={value} value={value}>
                {publicationStatusLabels[value]}
              </option>
            ))}
          </Select>
        </FilterField>
        <FilterField label="Audience" htmlFor="announcement-audience-filter">
          <Select
            id="announcement-audience-filter"
            value={audience ?? ""}
            onChange={(event) => update({ audience: event.target.value || null })}
          >
            <option value="">All audiences</option>
            {publicationAudienceOrder.map((value) => (
              <option key={value} value={value}>
                {publicationAudienceLabels[value]}
              </option>
            ))}
          </Select>
        </FilterField>
      </FilterToolbar>
      {list.isError && result ? <RefreshFailureNotice onRetry={() => void list.refetch()} retrying={list.isFetching} /> : null}

      <Panel className="mt-5" aria-labelledby="announcement-results-heading">
        <PanelHeader
          title="Announcement records"
          titleId="announcement-results-heading"
          context={list.isFetching && !list.isPending
            ? "Refreshing Announcements…"
            : result
              ? describeResultPage({ count: result.items.length, page: result.page, hasNext: result.has_next, noun: { one: "Announcement", other: "Announcements" }, filtered: hasFilters })
              : null}
        />
      {list.isPending ? (
        <ContentListSkeleton label="Loading Announcements…" />
      ) : !result ? (
        <PanelMessage role="alert" tone="danger" action={<Button variant="secondary" onClick={() => void list.refetch()}>Retry</Button>}>
          {announcementErrorMessage(list.error, "Announcements could not be loaded.")}
        </PanelMessage>
      ) : result && result.items.length === 0 ? (
        <PanelMessage
          action={page > 1 ? (
            <Link href={hrefWith({ page: null }, false)} className={buttonVariants({ variant: "secondary" })}>
              Go to the first page
            </Link>
          ) : hasFilters ? (
            <Link href={hrefWith({ status: null, audience: null })} className={buttonVariants({ variant: "secondary" })} scroll={false}>
              Clear filters
            </Link>
          ) : undefined}
        >
          {page > 1
            ? "No Announcements are on this page."
            : hasFilters
              ? "No Announcements match the selected filters."
              : "No Announcements have been created yet."}
        </PanelMessage>
      ) : result ? (
          <ul className="divide-y divide-border">
            {result.items.map((item) => (
              <li key={item.id} className="px-4 py-4 sm:px-5">
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
      ) : null}
      {result ? (
        <CanonicalPagination
          className="border-brand-line px-4 py-3 sm:px-5"
          page={result.page}
          hasNext={result.has_next}
          label="Announcement pages"
          onPageChange={setPage}
        />
      ) : null}
      </Panel>
    </section>
  );
}
