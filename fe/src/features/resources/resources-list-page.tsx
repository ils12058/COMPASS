"use client";

import { Plus } from "lucide-react";

import Link from "next/link";

import { PageActionLink } from "@/components/ui/page-action";
import { Select } from "@/components/ui/select";
import { SortField } from "@/components/ui/sort-field";
import { SortableColumnHeader } from "@/components/ui/sortable-column-header";
import { Button, buttonVariants } from "@/components/ui/button";
import { dataTable } from "@/components/ui/data-table";
import { FilterField } from "@/components/ui/filter-toolbar";
import { FloatingListTools, ListSearchField } from "@/components/ui/floating-list-tools";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { readOrdering } from "@/features/portal/components/list-ordering-params";
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
import { resourceManagementOrderingOptions } from "@/features/resources/resource-presentation";
import { useResourcesListManaged } from "@/lib/api/generated/resources/resources";
import { ResourceCategoryValue, ResourceKindValue, ResourceManagementOrdering } from "@/lib/api/generated/model";
import { formatInstitutionalDateTime } from "@/lib/institutional-time";


const noFilters = { search: null, status: null, audience: null, category: null, kind: null };

export function ResourcesListPage() {
  const { searchParams, page, hrefWith, update, setPage } = useContentListParams();
  const statusParam = searchParams.get("status");
  const audienceParam = searchParams.get("audience");
  const categoryParam = searchParams.get("category") ?? undefined;
  const kindParam = searchParams.get("kind") ?? undefined;
  const search = searchParams.get("search")?.trim() || undefined;
  const status = isPublicationStatus(statusParam) ? statusParam : undefined;
  const audience = isPublicationAudience(audienceParam) ? audienceParam : undefined;
  const category = isResourceCategory(categoryParam) ? categoryParam : undefined;
  const kind = isResourceKind(kindParam) ? kindParam : undefined;
  const hasFilters = Boolean(search || status || audience || category || kind);
  const advancedCount = [status, audience, category, kind].filter(Boolean).length;
  const detailParams = new URLSearchParams();
  if (search) detailParams.set("search", search);
  if (status) detailParams.set("status", status);
  if (audience) detailParams.set("audience", audience);
  if (category) detailParams.set("category", category);
  if (kind) detailParams.set("kind", kind);
  const requestedOrdering = readOrdering(searchParams.get("ordering"), ResourceManagementOrdering);
  if (requestedOrdering) detailParams.set("ordering", requestedOrdering);
  if (page > 1) detailParams.set("page", String(page));
  const detailQuery = detailParams.toString();

  const list = useResourcesListManaged(
    {
      ...(status ? { status } : {}),
      ...(audience ? { audience } : {}),
      ...(category ? { category } : {}),
      ...(kind ? { kind } : {}),
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
  const setOrdering = (next: ResourceManagementOrdering) => update({ ordering: next });

  return (
    <section aria-labelledby="resources-heading">
      <ContentPageHeading
        title="Resources"
        headingId="resources-heading"
        action={
          <PageActionLink href="/portal/resources/new" icon={Plus} label="Create" labelDetail="Resource" />
        }
      />

      <form
        role="search"
        aria-label="Search managed resources"
        key={searchParams.toString()}
        onSubmit={(event) => {
          event.preventDefault();
          const fields = new FormData(event.currentTarget);
          update({
            search: String(fields.get("search") ?? "").trim() || null,
            status: String(fields.get("status") ?? "") || null,
            audience: String(fields.get("audience") ?? "") || null,
            category: String(fields.get("category") ?? "") || null,
            kind: String(fields.get("kind") ?? "") || null,
          });
        }}
      >
      <FloatingListTools
        submits
        filterCount={advancedCount}
        clear={hasFilters ? (
          <Link href={hrefWith(noFilters)} className={buttonVariants({ variant: "quiet" })} scroll={false}>
            Clear filters
          </Link>
        ) : undefined}
        filters={<>
        <FilterField label="Status" htmlFor="resource-status-filter">
          <Select
            id="resource-status-filter"
            name="status"
            defaultValue={status ?? ""}
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
            name="audience"
            defaultValue={audience ?? ""}
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
            name="category"
            defaultValue={category ?? ""}
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
            name="kind"
            defaultValue={kind ?? ""}
          >
            <option value="">All types</option>
            {Object.values(ResourceKindValue).map((value) => (
              <option key={value} value={value}>{resourceKindLabels[value]}</option>
            ))}
          </Select>
        </FilterField>
        </>}
      >
        <ListSearchField
          id="resource-search-filter"
          name="search"
          label="Search resources"
          placeholder="Search resources"
          defaultValue={search}
        />
      </FloatingListTools>
      </form>

      {list.isError && result ? <RefreshFailureNotice onRetry={() => void list.refetch()} retrying={list.isFetching} /> : null}
      <Panel aria-labelledby="resource-results-heading">
        <PanelHeader
          title="Resource records"
          titleId="resource-results-heading"
          description={
            ordering === ResourceManagementOrdering.DISPLAY_ORDER
              ? "Readers see Resources in this order: lower display order first, then the newest published."
              : undefined
          }
          actions={
            <SortField
              id="resource-management-sort"
              value={ordering}
              options={resourceManagementOrderingOptions}
              onChange={setOrdering}
            />
          }
          context={list.isFetching && !list.isPending
            ? "Refreshing Resources…"
            : result
              ? describeResultPage({ count: result.items.length, page: result.page, hasNext: result.has_next, noun: { one: "Resource", other: "Resources" }, filtered: hasFilters })
              : null}
        />
      {list.isPending ? (
        <ContentListSkeleton label="Loading resources…" />
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
              ? search
                ? advancedCount > 0
                  ? "No resources match this search and the selected filters."
                  : "No resources match this search."
                : "No resources match the selected filters."
              : "No resources have been created yet."}
        </PanelMessage>
      ) : result ? (
          <div className={dataTable.scroll}>
            <table className={`${dataTable.table} min-w-[52rem]`}>
              <caption className="sr-only">Managed Resources</caption>
              <thead className={dataTable.head}>
                <tr>
                  <SortableColumnHeader
                    label="Resource"
                    ascending={ResourceManagementOrdering.TITLE_ASC}
                    descending={ResourceManagementOrdering.TITLE_DESC}
                    ascendingLabel="Title A–Z"
                    descendingLabel="Title Z–A"
                    current={ordering}
                    onSort={setOrdering}
                    className={`${dataTable.headerCell} ${dataTable.stickyHeaderCell}`}
                  />
                  <th scope="col" className={dataTable.headerCell}>Category</th>
                  <th scope="col" className={dataTable.headerCell}>Audience</th>
                  <th scope="col" className={dataTable.headerCell}>Status</th>
                  <SortableColumnHeader
                    label="Order"
                    ascending={ResourceManagementOrdering.DISPLAY_ORDER}
                    ascendingLabel="Display order, as readers see it"
                    current={ordering}
                    onSort={setOrdering}
                    className={`${dataTable.headerCell} text-right`}
                  />
                  <SortableColumnHeader
                    label="Last updated"
                    ascending={ResourceManagementOrdering.OLDEST_UPDATED}
                    descending={ResourceManagementOrdering.RECENTLY_UPDATED}
                    ascendingLabel="Oldest updated first"
                    descendingLabel="Recently updated first"
                    firstDirection="descending"
                    current={ordering}
                    onSort={setOrdering}
                    className={dataTable.headerCell}
                  />
                </tr>
              </thead>
              <tbody className={dataTable.body}>
                {result.items.map((item) => (
                  <tr key={item.id} className={dataTable.row}>
                    <th scope="row" className={`${dataTable.cell} ${dataTable.stickyCell} min-w-64 max-w-sm text-left font-normal`}>
                      <Link href={`/portal/resources/${item.id}${detailQuery ? `?${detailQuery}` : ""}`} className={`${contentRecordLinkClass} break-words`}>
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
