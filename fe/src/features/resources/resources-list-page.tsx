"use client";

import Link from "next/link";

import { Select } from "@/components/ui/select";
import { Button, buttonVariants } from "@/components/ui/button";
import { dataTable } from "@/components/ui/data-table";
import { FilterField, FilterToolbar } from "@/components/ui/filter-toolbar";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { describeResultPage } from "@/features/portal/components/result-context";
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

      {/* Selects only, so each choice applies as soon as it changes. */}
      <FilterToolbar
        className="mt-5"
        actions={hasFilters ? (
          <Link href={hrefWith(noFilters)} className={buttonVariants({ variant: "quiet" })} scroll={false}>
            Clear filters
          </Link>
        ) : undefined}
      >
        <FilterField label="Status" htmlFor="resource-status-filter">
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
        </FilterField>
        <FilterField label="Audience" htmlFor="resource-audience-filter">
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
        </FilterField>
        <FilterField label="Category" htmlFor="resource-category-filter">
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
        </FilterField>
        <FilterField label="Type" htmlFor="resource-kind-filter">
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
        </FilterField>
      </FilterToolbar>

      {list.isError && result ? <RefreshFailureNotice onRetry={() => void list.refetch()} retrying={list.isFetching} /> : null}
      <Panel className="mt-5" aria-labelledby="resource-results-heading">
        <PanelHeader
          title="Resource records"
          titleId="resource-results-heading"
          context={list.isFetching && !list.isPending
            ? "Refreshing Resources…"
            : result
              ? describeResultPage({ count: result.items.length, page: result.page, hasNext: result.has_next, noun: { one: "Resource", other: "Resources" }, filtered: hasFilters })
              : null}
        />
      {list.isPending ? (
        <ContentListSkeleton label="Loading Resources…" />
      ) : !result ? (
        <PanelMessage role="alert" tone="danger" action={<Button variant="secondary" onClick={() => void list.refetch()}>Retry</Button>}>
          {resourceErrorMessage(list.error, "Resources could not be loaded.")}
        </PanelMessage>
      ) : result && result.items.length === 0 ? (
        <PanelMessage
          action={page > 1 ? (
            <Link href={hrefWith({ page: null }, false)} className={buttonVariants({ variant: "secondary" })}>
              Go to the first page
            </Link>
          ) : hasFilters ? (
            <Link href={hrefWith(noFilters)} className={buttonVariants({ variant: "secondary" })} scroll={false}>
              Clear filters
            </Link>
          ) : undefined}
        >
          {page > 1
            ? "No Resources are on this page."
            : hasFilters
              ? "No Resources match the selected filters."
              : "No Resources have been created yet."}
        </PanelMessage>
      ) : result ? (
          <div className={dataTable.scroll}>
            <table className={`${dataTable.table} min-w-[52rem]`}>
              <caption className="sr-only">Managed Resources</caption>
              <thead className={dataTable.head}>
                <tr>
                  <th scope="col" className={`${dataTable.headerCell} ${dataTable.stickyHeaderCell}`}>Resource</th>
                  <th scope="col" className={dataTable.headerCell}>Category</th>
                  <th scope="col" className={dataTable.headerCell}>Audience</th>
                  <th scope="col" className={dataTable.headerCell}>Status</th>
                  <th scope="col" className={`${dataTable.headerCell} text-right`}>Order</th>
                  <th scope="col" className={dataTable.headerCell}>Last updated</th>
                </tr>
              </thead>
              <tbody className={dataTable.body}>
                {result.items.map((item) => (
                  <tr key={item.id} className={dataTable.row}>
                    <th scope="row" className={`${dataTable.cell} ${dataTable.stickyCell} min-w-64 max-w-sm text-left font-normal`}>
                      <Link href={`/portal/resources/${item.id}`} className={`${contentRecordLinkClass} break-words`}>
                        {displayTitle(item.title, "Untitled Resource")}
                      </Link>
                      <span className="mt-1 block text-xs text-muted">{resourceKindLabels[item.kind]}</span>
                    </th>
                    <td className={`${dataTable.cell} text-ink`}>{resourceCategoryLabels[item.category]}</td>
                    <td className={`${dataTable.cell} text-ink`}>{publicationAudienceLabels[item.audience]}</td>
                    <td className={dataTable.cell}><PublicationStatusBadge status={item.status} /></td>
                    <td className={`${dataTable.cell} text-right tabular-nums text-ink`}>{item.display_order}</td>
                    <td className={`${dataTable.cell} whitespace-nowrap text-ink`}>{formatInstitutionalDateTime(item.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
      ) : null}
      {result ? (
        <CanonicalPagination
          className="border-brand-line px-4 py-3 sm:px-5"
          page={result.page}
          hasNext={result.has_next}
          label="Resource pages"
          onPageChange={setPage}
        />
      ) : null}
      </Panel>
    </section>
  );
}
