"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { Button, buttonVariants } from "@/components/ui/button";
import { dataTable } from "@/components/ui/data-table";
import { FilterField } from "@/components/ui/filter-toolbar";
import { FloatingListTools, ListSearchField } from "@/components/ui/floating-list-tools";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { Select } from "@/components/ui/select";
import { safeQueryData } from "@/features/freshness/query-freshness";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { describeResultPage } from "@/features/portal/components/result-context";
import { GoodMoralListSkeleton, GoodMoralHeading, GoodMoralStatus, formatGoodMoralDateTime, goodMoralErrorMessage, goodMoralVariantLabel } from "@/features/good-moral/good-moral-shared";
import { useGoodMoralListRequests } from "@/lib/api/generated/good-moral/good-moral";
import { GoodMoralStatusValue, GoodMoralVariantValue } from "@/lib/api/generated/model";

export type GoodMoralOperationalFilters = {
  search: string;
  variant: GoodMoralVariantValue | "";
  status: GoodMoralStatusValue | "";
  page: number;
  pageSize?: number;
};

function pageHref(filters: GoodMoralOperationalFilters, page: number): string {
  const params = new URLSearchParams();
  if (filters.search) params.set("search", filters.search);
  if (filters.variant) params.set("variant", filters.variant);
  if (filters.status) params.set("status", filters.status);
  if (filters.pageSize) params.set("page_size", String(filters.pageSize));
  if (page > 1) params.set("page", String(page));
  const query = params.toString();
  return query ? `/portal/good-moral?${query}` : "/portal/good-moral";
}

export function GoodMoralOperationalList({ filters }: { filters: GoodMoralOperationalFilters }) {
  const params = {
    ...(filters.search ? { search: filters.search } : {}),
    ...(filters.variant ? { variant: filters.variant } : {}),
    ...(filters.status ? { status: filters.status } : {}),
    page: filters.page,
    ...(filters.pageSize ? { page_size: filters.pageSize } : {}),
  };
  const router = useRouter();
  const queue = useGoodMoralListRequests(params, { query: { retry: false } });
  const page = safeQueryData(queue)?.data;
  const hasFilters = Boolean(filters.search || filters.variant || filters.status);

  const resultContext = page
    ? describeResultPage({
        count: page.items.length,
        page: page.page,
        hasNext: page.has_next,
        noun: { one: "request", other: "requests" },
        filtered: hasFilters,
      })
    : null;
  const clearHref = pageHref({ ...filters, search: "", variant: "", status: "" }, 1);

  return (
    <section className="space-y-5" aria-labelledby="good-moral-operational-heading">
      <GoodMoralHeading headingId="good-moral-operational-heading" title="Good Moral" />

      <form action="/portal/good-moral" method="get" role="search" aria-label="Good Moral requests" key={JSON.stringify(filters)}>
        {filters.pageSize ? <input type="hidden" name="page_size" value={filters.pageSize} /> : null}
        <FloatingListTools
          submits
          filterCount={[filters.variant, filters.status].filter(Boolean).length}
          clear={hasFilters ? <Link href={clearHref} className={buttonVariants({ variant: "quiet" })}>Clear filters</Link> : undefined}
          filters={<>
          <FilterField label="Variant" htmlFor="good-moral-variant">
            <Select id="good-moral-variant" name="variant" defaultValue={filters.variant}>
              <option value="">All variants</option>
              <option value={GoodMoralVariantValue.CURRENT_STUDENT}>Current Student</option>
              <option value={GoodMoralVariantValue.GRADUATE}>Graduate</option>
            </Select>
          </FilterField>
          <FilterField label="Status" htmlFor="good-moral-status">
            <Select id="good-moral-status" name="status" defaultValue={filters.status}>
              <option value="">All statuses</option>
              <option value={GoodMoralStatusValue.REQUESTED}>Requested</option>
              <option value={GoodMoralStatusValue.ISSUED}>Issued</option>
              <option value={GoodMoralStatusValue.CANCELLED}>Cancelled</option>
            </Select>
          </FilterField>
          </>}
        >
          <ListSearchField id="good-moral-search" name="search" label="Search Student name or Institutional ID" placeholder="Search Student name or Institutional ID" defaultValue={filters.search} />
        </FloatingListTools>
      </form>
      {queue.isError && page ? <RefreshFailureNotice onRetry={() => void queue.refetch()} retrying={queue.isFetching} /> : null}

      <Panel aria-labelledby="good-moral-queue-heading">
        <PanelHeader title="Good Moral requests" titleId="good-moral-queue-heading" context={resultContext} />
        {queue.isPending ? (
          <GoodMoralListSkeleton framed={false} />
        ) : !page ? (
          <PanelMessage
            role="alert"
            tone="danger"
            action={<Button variant="secondary" onClick={() => void queue.refetch()}>Retry</Button>}
          >
            {goodMoralErrorMessage(queue.error, "Good Moral requests could not be loaded.")}
          </PanelMessage>
        ) : page.items.length === 0 ? (
          <PanelMessage
            action={hasFilters ? <Link href={clearHref} className={buttonVariants({ variant: "secondary" })}>Clear filters</Link> : undefined}
          >
            {hasFilters ? "No Good Moral requests match these filters." : "No Good Moral requests have been recorded."}
          </PanelMessage>
        ) : (
          <div className={dataTable.scroll}>
            <table className={`${dataTable.table} min-w-[680px]`}>
              <caption className="sr-only">Good Moral certificate request queue</caption>
              <thead className={dataTable.head}>
                <tr>
                  <th scope="col" className={`${dataTable.headerCell} ${dataTable.stickyHeaderCell}`}>Applicant</th>
                  <th scope="col" className={dataTable.headerCell}>Variant</th>
                  <th scope="col" className={dataTable.headerCell}>Status</th>
                  <th scope="col" className={dataTable.headerCell}>Requested</th>
                  <th scope="col" className={dataTable.headerCell}>Issued</th>
                </tr>
              </thead>
              <tbody className={dataTable.body}>
                {page.items.map((item) => (
                  <tr key={item.id} className={dataTable.row}>
                    <th scope="row" className={`${dataTable.cell} ${dataTable.stickyCell} font-semibold text-ink`}>
                      <Link href={`/portal/good-moral/${item.id}`} className="text-brand underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
                        {item.applicant_name || "Applicant name not provided"}
                      </Link>
                      {item.student_institutional_id ? <span className="mt-1 block text-xs font-normal text-muted">{item.student_institutional_id}</span> : null}
                    </th>
                    <td className={`${dataTable.cell} text-muted`}>{goodMoralVariantLabel(item.variant)}</td>
                    <td className={dataTable.cell}><GoodMoralStatus status={item.status} /></td>
                    <td className={`${dataTable.cell} whitespace-nowrap text-muted`}>{formatGoodMoralDateTime(item.created_at)}</td>
                    <td className={`${dataTable.cell} whitespace-nowrap text-muted`}>{formatGoodMoralDateTime(item.issued_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {page ? (
          <CanonicalPagination
            className="border-brand-line px-4 py-3 sm:px-5"
            page={page.page}
            hasNext={page.has_next}
            label="Good Moral request pages"
            onPageChange={(nextPage) => router.push(pageHref({ ...filters, pageSize: page.page_size }, nextPage))}
          />
        ) : null}
      </Panel>
    </section>
  );
}
