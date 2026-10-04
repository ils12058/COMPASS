"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { Button, buttonVariants } from "@/components/ui/button";
import { dataTable } from "@/components/ui/data-table";
import { FilterField } from "@/components/ui/filter-toolbar";
import { FloatingListTools, ListSearchField } from "@/components/ui/floating-list-tools";
import { Input } from "@/components/ui/input";
import { Notice } from "@/components/ui/notice";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { RowsSkeleton } from "@/components/ui/rows-skeleton";
import { Select } from "@/components/ui/select";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { describeResultPage } from "@/features/portal/components/result-context";
import { EMPLOYMENT_STATE_CHOICES, formatGraduateTracerDateTime } from "@/features/graduate-tracer/graduate-tracer-presentation";
import { GraduateTracerError, GraduateTracerHeading, graduateTracerErrorMessage } from "@/features/graduate-tracer/graduate-tracer-shared";
import { useGraduateTracerListResponses } from "@/lib/api/generated/graduate-tracer/graduate-tracer";
import type { GTSEmploymentStateValue } from "@/lib/api/generated/model";

export type GraduateTracerOperationalFilters = {
  search: string;
  submittedFrom: string;
  submittedTo: string;
  employmentState: GTSEmploymentStateValue | "";
  page: number;
  pageSize?: number;
};

function pageHref(filters: GraduateTracerOperationalFilters, page: number, pageSize?: number): string {
  const params = new URLSearchParams();
  if (filters.search) params.set("search", filters.search);
  if (filters.submittedFrom) params.set("submitted_from", filters.submittedFrom);
  if (filters.submittedTo) params.set("submitted_to", filters.submittedTo);
  if (filters.employmentState) params.set("current_employment_state", filters.employmentState);
  const effectivePageSize = pageSize ?? filters.pageSize;
  if (effectivePageSize) params.set("page_size", String(effectivePageSize));
  if (page > 1) params.set("page", String(page));
  const query = params.toString();
  return query ? `/portal/graduate-tracer?${query}` : "/portal/graduate-tracer";
}

function hideCachedResults(error: unknown): boolean {
  return error instanceof Error && "status" in error && [401, 403, 404].includes(Number(error.status));
}

export function GraduateTracerOperationalList({ filters }: { filters: GraduateTracerOperationalFilters }) {
  const router = useRouter();
  const dateRangeInvalid = Boolean(filters.submittedFrom && filters.submittedTo && filters.submittedFrom > filters.submittedTo);
  const params = {
    ...(filters.search ? { search: filters.search } : {}),
    ...(filters.submittedFrom ? { submitted_from: filters.submittedFrom } : {}),
    ...(filters.submittedTo ? { submitted_to: filters.submittedTo } : {}),
    ...(filters.employmentState ? { current_employment_state: filters.employmentState } : {}),
    page: filters.page,
    ...(filters.pageSize ? { page_size: filters.pageSize } : {}),
  };
  const queue = useGraduateTracerListResponses(params, { query: { retry: false, enabled: !dateRangeInvalid } });
  const page = queue.data?.data;
  const hasFilters = Boolean(filters.search || filters.submittedFrom || filters.submittedTo || filters.employmentState);
  const hideCached = queue.isError && hideCachedResults(queue.error);
  const clearHref = pageHref({ ...filters, search: "", submittedFrom: "", submittedTo: "", employmentState: "" }, 1);
  const advancedCount = [filters.submittedFrom, filters.submittedTo, filters.employmentState].filter(Boolean).length;

  return (
    <section className="space-y-5" aria-labelledby="graduate-tracer-queue-heading">
      <GraduateTracerHeading
        id="graduate-tracer-queue-heading"
        title="Graduate Tracer"
        description="Only submitted responses are shown. Draft answers are not available in this workspace."
      />

      <form action="/portal/graduate-tracer" method="get" role="search" aria-label="Graduate Tracer responses" key={JSON.stringify(filters)}>
        {filters.pageSize ? <input type="hidden" name="page_size" value={filters.pageSize} /> : null}
        <FloatingListTools
          submits
          filterCount={advancedCount}
          clear={hasFilters ? <Link href={clearHref} className={buttonVariants({ variant: "quiet" })}>Clear filters</Link> : undefined}
          filters={
            <>
          <FilterField label="Submitted from" htmlFor="gts-submitted-from">
            <Input id="gts-submitted-from" type="date" name="submitted_from" defaultValue={filters.submittedFrom} />
          </FilterField>
          <FilterField label="Submitted to" htmlFor="gts-submitted-to">
            <Input id="gts-submitted-to" type="date" name="submitted_to" defaultValue={filters.submittedTo} />
          </FilterField>
          <FilterField label="Current employment state" htmlFor="gts-employment-filter">
            <Select id="gts-employment-filter" name="current_employment_state" defaultValue={filters.employmentState}>
              <option value="">All employment states</option>
              {EMPLOYMENT_STATE_CHOICES.map((choice) => <option key={choice.value} value={choice.value}>{choice.label === "Yes" ? "Employed" : choice.label === "No" ? "Not employed" : choice.label}</option>)}
            </Select>
          </FilterField>
            </>
          }
        >
          <ListSearchField id="gts-queue-search" name="search" label="Search Graduate name or Institutional ID" placeholder="Search Graduate name or Institutional ID" defaultValue={filters.search} />
        </FloatingListTools>
      </form>

      {dateRangeInvalid ? <Notice role="alert" tone="warning"><span className="text-ink">Submitted-from date must be on or before the submitted-to date.</span></Notice> : null}
      {!dateRangeInvalid && queue.isError && page && !hideCached ? <GraduateTracerError error={queue.error} fallback="The submitted-response queue could not be refreshed. Showing the last confirmed results." onRetry={() => void queue.refetch()} /> : null}

      {dateRangeInvalid ? null : (
        <Panel aria-labelledby="graduate-tracer-results-heading">
          <PanelHeader
            title="Submitted responses"
            titleId="graduate-tracer-results-heading"
            context={queue.isFetching && !queue.isPending
              ? "Refreshing submitted responses…"
              : page && !queue.isError
                ? describeResultPage({
                    count: page.items.length,
                    page: page.page,
                    hasNext: page.has_next,
                    noun: { one: "response", other: "responses" },
                    filtered: hasFilters,
                  })
                : null}
          />
          {queue.isPending ? (
            <RowsSkeleton label="Loading submitted Graduate Tracer responses…" rows={4} />
          ) : queue.isError && (!page || hideCached) ? (
            <PanelMessage role="alert" tone="danger" action={<Button variant="secondary" onClick={() => void queue.refetch()}>Retry</Button>}>
              {graduateTracerErrorMessage(queue.error, "The submitted-response queue could not be loaded.")}
            </PanelMessage>
          ) : !page ? null : page.items.length === 0 ? (
            <PanelMessage action={hasFilters ? <Link href={clearHref} className={buttonVariants({ variant: "secondary" })}>Clear filters</Link> : undefined}>
              {hasFilters ? "No submitted Graduate Tracer responses match the current filters." : "No submitted Graduate Tracer responses are available."}
            </PanelMessage>
          ) : (
            <div className={dataTable.scroll}>
              <table className={`${dataTable.table} min-w-[42rem]`}>
                <caption className="sr-only">Submitted Graduate Tracer responses</caption>
                <thead className={dataTable.head}>
                  <tr>
                    <th scope="col" className={`${dataTable.headerCell} ${dataTable.stickyHeaderCell} min-w-56`}>Graduate</th>
                    <th scope="col" className={`${dataTable.headerCell} min-w-44`}>Employment</th>
                    <th scope="col" className={`${dataTable.headerCell} min-w-48`}>Submitted</th>
                  </tr>
                </thead>
                <tbody className={dataTable.body}>
                  {page.items.map((item) => (
                    <tr key={item.id} className={dataTable.row}>
                      <th scope="row" className={`${dataTable.cell} ${dataTable.stickyCell} font-semibold text-ink`}>
                        <Link href={`/portal/graduate-tracer/responses/${item.id}`} className="text-brand underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">{item.name || item.student.display_name}</Link>
                        {item.student.institutional_id ? <span className="mt-1 block text-xs font-normal text-muted">{item.student.institutional_id}</span> : null}
                      </th>
                      <td className={`${dataTable.cell} text-ink`}>{item.current_employment_state === "EMPLOYED" ? "Employed" : item.current_employment_state === "NOT_EMPLOYED" ? "Not employed" : "Never employed"}</td>
                      <td className={`${dataTable.cell} whitespace-nowrap text-muted`}>{formatGraduateTracerDateTime(item.submitted_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {page ? <CanonicalPagination className="border-brand-line px-4 py-3 sm:px-5" page={page.page} hasNext={page.has_next} label="Graduate Tracer response pages" onPageChange={(nextPage) => router.push(pageHref(filters, nextPage, page.page_size))} /> : null}
        </Panel>
      )}
    </section>
  );
}
