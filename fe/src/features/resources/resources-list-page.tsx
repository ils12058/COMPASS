"use client";

import Link from "next/link";

import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { safeQueryData } from "@/features/freshness/query-freshness";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
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
} from "@/features/content/content-shared";
import { useContentListParams } from "@/features/content/use-content-list-params";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import {
  isResourceCategory,
  isResourceKind,
  resourceCategoryLabels,
  resourceKindLabels,
} from "@/features/public/shared/presentation";
import { resourceErrorMessage } from "@/features/resources/resource-errors";
import { useResourcesListManaged } from "@/lib/api/generated/resources/resources";
import { ResourceCategoryValue, ResourceKindValue } from "@/lib/api/generated/model";
import { formatInstitutionalDateTime } from "@/lib/institutional-time";

const clearLinkClass =
  "inline-flex min-h-10 items-center text-sm font-semibold text-brand underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus";
const headerCell = "px-3 py-3 font-semibold";
const bodyCell = "px-3 py-4 align-top";

const noFilters = { status: null, audience: null, category: null, kind: null };

export function ResourcesListPage() {
  const { searchParams, page, hrefWith, update, setPage } = useContentListParams();
  const statusParam = searchParams.get("status");
  const audienceParam = searchParams.get("audience");
  const categoryParam = searchParams.get("category") ?? undefined;
  const kindParam = searchParams.get("kind") ?? undefined;
  const status = isPublicationStatus(statusParam) ? statusParam : undefined;
  const audience = isPublicationAudience(audienceParam) ? audienceParam : undefined;
  const category = isResourceCategory(categoryParam) ? categoryParam : undefined;
  const kind = isResourceKind(kindParam) ? kindParam : undefined;
  const hasFilters = Boolean(status || audience || category || kind);

  const list = useResourcesListManaged(
    {
      ...(status ? { status } : {}),
      ...(audience ? { audience } : {}),
      ...(category ? { category } : {}),
      ...(kind ? { kind } : {}),
      page,
      page_size: 20,
    },
    { query: { retry: false } },
  );
  const result = safeQueryData(list)?.data;

  return (
    <section aria-labelledby="resources-heading">
      <ContentPageHeading
        title="Resources"
        headingId="resources-heading"
        action={
          <Link href="/portal/resources/new" className={contentPrimaryLinkClass}>
            Create Resource
          </Link>
        }
      />

      <div className="mt-8 border-y border-border py-5">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="grid gap-2">
            <Label htmlFor="resource-status-filter">Status</Label>
            <Select
              id="resource-status-filter"
              value={status ?? ""}
              onChange={(event) => update({ status: event.target.value || null })}
            >
              <option value="">All statuses</option>
              {publicationStatusOrder.map((value) => (
                <option key={value} value={value}>{publicationStatusLabels[value]}</option>
              ))}
            </Select>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="resource-audience-filter">Audience</Label>
            <Select
              id="resource-audience-filter"
              value={audience ?? ""}
              onChange={(event) => update({ audience: event.target.value || null })}
            >
              <option value="">All audiences</option>
              {publicationAudienceOrder.map((value) => (
                <option key={value} value={value}>{publicationAudienceLabels[value]}</option>
              ))}
            </Select>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="resource-category-filter">Category</Label>
            <Select
              id="resource-category-filter"
              value={category ?? ""}
              onChange={(event) => update({ category: event.target.value || null })}
            >
              <option value="">All categories</option>
              {Object.values(ResourceCategoryValue).map((value) => (
                <option key={value} value={value}>{resourceCategoryLabels[value]}</option>
              ))}
            </Select>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="resource-kind-filter">Type</Label>
            <Select
              id="resource-kind-filter"
              value={kind ?? ""}
              onChange={(event) => update({ kind: event.target.value || null })}
            >
              <option value="">All types</option>
              {Object.values(ResourceKindValue).map((value) => (
                <option key={value} value={value}>{resourceKindLabels[value]}</option>
              ))}
            </Select>
          </div>
        </div>
        {hasFilters ? (
          <Link href={hrefWith(noFilters)} className={`mt-3 ${clearLinkClass}`} scroll={false}>
            Clear filters
          </Link>
        ) : null}
      </div>

      {list.isError && result ? <RefreshFailureNotice onRetry={() => void list.refetch()} retrying={list.isFetching} /> : null}
      {list.isPending ? (
        <ContentListSkeleton label="Loading Resources…" />
      ) : !result ? (
        <div className="mt-5">
          <ContentQueryError
            message={resourceErrorMessage(list.error, "Resources could not be loaded.")}
            onRetry={() => void list.refetch()}
          />
        </div>
      ) : result && result.items.length === 0 ? (
        <div className="border-b border-border py-8">
          <p className="text-sm text-muted">
            {page > 1
              ? "No Resources are on this page."
              : hasFilters
                ? "No Resources match the selected filters."
                : "No Resources have been created yet."}
          </p>
          {page > 1 ? (
            <Link href={hrefWith({ page: null }, false)} className={`mt-2 ${clearLinkClass}`}>
              Go to the first page
            </Link>
          ) : hasFilters ? (
            <Link href={hrefWith(noFilters)} className={`mt-2 ${clearLinkClass}`} scroll={false}>
              Clear filters
            </Link>
          ) : null}
        </div>
      ) : result ? (
        <>
          {list.isFetching ? (
            <p role="status" className="mt-4 text-xs text-muted">Refreshing Resources…</p>
          ) : null}
          <div className="mt-5 overflow-x-auto border-y border-border">
            <table className="w-full min-w-[52rem] border-collapse text-left text-sm">
              <caption className="sr-only">Managed Resources</caption>
              <thead className="bg-surface-muted text-xs text-muted">
                <tr>
                  <th scope="col" className={`${headerCell} sticky left-0 z-10 bg-surface-muted`}>Resource</th>
                  <th scope="col" className={headerCell}>Category</th>
                  <th scope="col" className={headerCell}>Audience</th>
                  <th scope="col" className={headerCell}>Status</th>
                  <th scope="col" className={`${headerCell} text-right`}>Order</th>
                  <th scope="col" className={headerCell}>Last updated</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border bg-surface-raised">
                {result.items.map((item) => (
                  <tr key={item.id}>
                    <th scope="row" className={`${bodyCell} sticky left-0 min-w-64 max-w-sm bg-surface-raised text-left font-normal`}>
                      <Link href={`/portal/resources/${item.id}`} className={`${contentRecordLinkClass} break-words`}>
                        {displayTitle(item.title, "Untitled Resource")}
                      </Link>
                      <span className="mt-1 block text-xs text-muted">{resourceKindLabels[item.kind]}</span>
                    </th>
                    <td className={`${bodyCell} text-ink`}>{resourceCategoryLabels[item.category]}</td>
                    <td className={`${bodyCell} text-ink`}>{publicationAudienceLabels[item.audience]}</td>
                    <td className={bodyCell}><PublicationStatusBadge status={item.status} /></td>
                    <td className={`${bodyCell} text-right tabular-nums text-ink`}>{item.display_order}</td>
                    <td className={`${bodyCell} whitespace-nowrap text-ink`}>{formatInstitutionalDateTime(item.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}
      {result ? (
        <CanonicalPagination
          page={result.page}
          hasNext={result.has_next}
          label="Resource pages"
          onPageChange={setPage}
        />
      ) : null}
    </section>
  );
}
