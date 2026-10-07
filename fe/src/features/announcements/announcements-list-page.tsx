"use client";

import { Pin, Plus } from "lucide-react";
import Link from "next/link";

import { PageActionLink } from "@/components/ui/page-action";
import { Select } from "@/components/ui/select";
import { SortField } from "@/components/ui/sort-field";
import { Button, buttonVariants } from "@/components/ui/button";
import { FilterField } from "@/components/ui/filter-toolbar";
import { FloatingListTools, ListSearchField } from "@/components/ui/floating-list-tools";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { readOrdering } from "@/features/portal/components/list-ordering";
import { describeResultPage } from "@/features/portal/components/result-context";
import { safeQueryData } from "@/features/freshness/query-freshness";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
import { announcementErrorMessage } from "@/features/announcements/announcement-errors";
import {
  announcementManagementOrderingOptions,
  announcementTimingLine,
} from "@/features/announcements/announcement-presentation";
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
  contentRecordLinkClass,
} from "@/features/content/content-shared";
import { useContentListParams } from "@/features/content/use-content-list-params";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { useAnnouncementsListManaged } from "@/lib/api/generated/announcements/announcements";
import { AnnouncementManagementOrdering } from "@/lib/api/generated/model";

export function AnnouncementsListPage() {
  const { searchParams, page, hrefWith, update, setPage } = useContentListParams();
  const statusParam = searchParams.get("status");
  const audienceParam = searchParams.get("audience");
  const search = searchParams.get("search")?.trim() || undefined;
  const status = isPublicationStatus(statusParam) ? statusParam : undefined;
  const audience = isPublicationAudience(audienceParam) ? audienceParam : undefined;
  const requestedOrdering = readOrdering(searchParams.get("ordering"), AnnouncementManagementOrdering);
  const hasFilters = Boolean(search || status || audience);
  const detailParams = new URLSearchParams();
  if (search) detailParams.set("search", search);
  if (status) detailParams.set("status", status);
  if (audience) detailParams.set("audience", audience);
  if (requestedOrdering) detailParams.set("ordering", requestedOrdering);
  if (page > 1) detailParams.set("page", String(page));
  const detailQuery = detailParams.toString();

  const list = useAnnouncementsListManaged(
    {
      ...(status ? { status } : {}),
      ...(audience ? { audience } : {}),
      ...(search ? { search } : {}),
      ...(requestedOrdering ? { ordering: requestedOrdering } : {}),
      page,
      page_size: 20,
    },
    { query: { retry: false } },
  );
  const result = safeQueryData(list)?.data;
  // The order the records are in: the reader's choice, or the default the backend applied.
  const ordering = requestedOrdering ?? result?.ordering;

  return (
    <section aria-labelledby="announcements-heading">
      <ContentPageHeading
        title="Announcements"
        headingId="announcements-heading"
        action={
          <PageActionLink href="/portal/announcements/new" icon={Plus} label="Create" labelDetail="Announcement" />
        }
      />

      <form
        role="search"
        aria-label="Search managed announcements"
        key={searchParams.toString()}
        onSubmit={(event) => {
          event.preventDefault();
          const fields = new FormData(event.currentTarget);
          update({
            search: String(fields.get("search") ?? "").trim() || null,
            status: String(fields.get("status") ?? "") || null,
            audience: String(fields.get("audience") ?? "") || null,
          });
        }}
      >
        <FloatingListTools
          submits
          filterCount={[status, audience].filter(Boolean).length}
          clear={hasFilters ? (
            <Link href={hrefWith({ search: null, status: null, audience: null })} className={buttonVariants({ variant: "quiet" })} scroll={false}>
              Clear filters
            </Link>
          ) : undefined}
          filters={<>
            <FilterField label="Status" htmlFor="announcement-status-filter">
              <Select
                id="announcement-status-filter"
                name="status"
                defaultValue={status ?? ""}
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
                name="audience"
                defaultValue={audience ?? ""}
              >
                <option value="">All audiences</option>
                {publicationAudienceOrder.map((value) => (
                  <option key={value} value={value}>
                    {publicationAudienceLabels[value]}
                  </option>
                ))}
              </Select>
            </FilterField>
          </>}
        >
          <ListSearchField
            id="announcement-search-filter"
            name="search"
            label="Search announcements"
            placeholder="Search announcements"
            defaultValue={search}
          />
        </FloatingListTools>
      </form>
      {list.isError && result ? <RefreshFailureNotice onRetry={() => void list.refetch()} retrying={list.isFetching} /> : null}

      <Panel aria-labelledby="announcement-results-heading">
        <PanelHeader
          title="Announcement records"
          titleId="announcement-results-heading"
          actions={
            <SortField
              id="announcement-management-sort"
              value={ordering}
              options={announcementManagementOrderingOptions}
              onChange={(next) => update({ ordering: next })}
            />
          }
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
            <Link href={hrefWith({ search: null, status: null, audience: null })} className={buttonVariants({ variant: "secondary" })} scroll={false}>
              Clear filters
            </Link>
          ) : undefined}
        >
          {page > 1
            ? "No Announcements are on this page."
            : hasFilters
              ? search
                ? status || audience
                  ? "No Announcements match this search and the selected filters."
                  : "No Announcements match this search."
                : "No Announcements match the selected filters."
              : "No Announcements have been created yet."}
        </PanelMessage>
      ) : result ? (
          <ul className="divide-y divide-border">
            {result.items.map((item) => (
              <li key={item.id} className="px-4 py-4 sm:px-5">
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  <Link
                    href={`/portal/announcements/${item.id}${detailQuery ? `?${detailQuery}` : ""}`}
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
