"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { EMPLOYMENT_STATE_CHOICES, formatGraduateTracerDateTime } from "@/features/graduate-tracer/graduate-tracer-presentation";
import { GraduateTracerError, GraduateTracerHeading } from "@/features/graduate-tracer/graduate-tracer-shared";
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

  return (
    <section className="space-y-6" aria-labelledby="graduate-tracer-queue-heading">
      <GraduateTracerHeading
        id="graduate-tracer-queue-heading"
        title="Graduate Tracer"
        description="Review submitted Graduate Tracer responses. Draft answers are not available in this workspace."
      />

      <form action="/portal/graduate-tracer" method="get" className="grid gap-4 border-b border-border pb-6 sm:grid-cols-2 xl:grid-cols-[minmax(14rem,2fr)_minmax(11rem,1fr)_minmax(11rem,1fr)_minmax(12rem,1.2fr)_auto]" key={JSON.stringify(filters)}>
        <div className="min-w-0">
          <Label htmlFor="gts-queue-search">Search Graduate name or Institutional ID</Label>
          <Input id="gts-queue-search" className="mt-2" type="search" name="search" placeholder="Name or Institutional ID" defaultValue={filters.search} />
        </div>
        <div>
          <Label htmlFor="gts-submitted-from">Submitted from</Label>
          <Input id="gts-submitted-from" className="mt-2" type="date" name="submitted_from" defaultValue={filters.submittedFrom} />
        </div>
        <div>
          <Label htmlFor="gts-submitted-to">Submitted to</Label>
          <Input id="gts-submitted-to" className="mt-2" type="date" name="submitted_to" defaultValue={filters.submittedTo} />
        </div>
        <div>
          <Label htmlFor="gts-employment-filter">Current employment state</Label>
          <select id="gts-employment-filter" name="current_employment_state" defaultValue={filters.employmentState} className="mt-2 min-h-10 w-full rounded-md border border-border bg-surface-raised px-3 py-2 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
            <option value="">All employment states</option>
            {EMPLOYMENT_STATE_CHOICES.map((choice) => <option key={choice.value} value={choice.value}>{choice.label === "Yes" ? "Employed" : choice.label === "No" ? "Not employed" : choice.label}</option>)}
          </select>
        </div>
        {filters.pageSize ? <input type="hidden" name="page_size" value={filters.pageSize} /> : null}
        <div className="flex flex-wrap items-end gap-3 xl:col-span-1">
          <Button type="submit">Apply filters</Button>
          {hasFilters ? <Link href={pageHref({ ...filters, search: "", submittedFrom: "", submittedTo: "", employmentState: "" }, 1)} className="inline-flex min-h-10 items-center px-2 text-sm font-semibold text-brand underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Clear filters</Link> : null}
        </div>
      </form>

      {dateRangeInvalid ? <p role="alert" className="border-l-4 border-warning bg-warning/5 px-4 py-3 text-sm text-ink">Submitted-from date must be on or before the submitted-to date.</p> : null}
      {!dateRangeInvalid && queue.isFetching && !queue.isPending ? <p role="status" className="text-xs text-muted">Refreshing submitted responses…</p> : null}
      {!dateRangeInvalid && queue.isError && page && !hideCached ? <GraduateTracerError error={queue.error} fallback="The submitted-response queue could not be refreshed. Showing the last confirmed results." onRetry={() => void queue.refetch()} /> : null}

      {dateRangeInvalid ? null : queue.isPending ? (
        <div className="space-y-3" aria-busy="true" aria-label="Loading submitted Graduate Tracer responses"><Skeleton className="h-12 w-full" /><Skeleton className="h-16 w-full" /><Skeleton className="h-16 w-full" /><Skeleton className="h-16 w-full" /></div>
      ) : queue.isError && (!page || hideCached) ? (
        <GraduateTracerError error={queue.error} fallback="The submitted-response queue could not be loaded." onRetry={() => void queue.refetch()} />
      ) : !page ? null : page.items.length === 0 ? (
        <div className="border-y border-border py-6">
          <p className="text-sm text-muted">{hasFilters ? "No submitted Graduate Tracer responses match the current filters." : "No submitted Graduate Tracer responses are available."}</p>
          {page.page > 1 ? <CanonicalPagination page={page.page} hasNext={page.has_next} label="Graduate Tracer response pages" onPageChange={(nextPage) => router.push(pageHref(filters, nextPage, page.page_size))} /> : null}
        </div>
      ) : (
        <div className="overflow-x-auto rounded-md border border-border">
          <table className="min-w-[42rem] w-full border-collapse text-left text-sm">
            <caption className="sr-only">Submitted Graduate Tracer responses</caption>
            <thead className="bg-surface-muted text-xs uppercase tracking-wide text-muted">
              <tr>
                <th scope="col" className="sticky left-0 z-10 min-w-56 bg-surface-muted px-4 py-3 font-semibold">Graduate</th>
                <th scope="col" className="min-w-44 px-4 py-3 font-semibold">Employment</th>
                <th scope="col" className="min-w-48 px-4 py-3 font-semibold">Submitted</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {page.items.map((item) => (
                <tr key={item.id} className="align-top">
                  <th scope="row" className="sticky left-0 z-10 bg-surface-raised px-4 py-4 font-semibold text-ink">
                    <Link href={`/portal/graduate-tracer/responses/${item.id}`} className="text-brand underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">{item.name || item.student.display_name}</Link>
                    {item.student.institutional_id ? <span className="mt-1 block text-xs font-normal text-muted">{item.student.institutional_id}</span> : null}
                  </th>
                  <td className="px-4 py-4 text-ink">{item.current_employment_state === "EMPLOYED" ? "Employed" : item.current_employment_state === "NOT_EMPLOYED" ? "Not employed" : "Never employed"}</td>
                  <td className="whitespace-nowrap px-4 py-4 text-muted">{formatGraduateTracerDateTime(item.submitted_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {page && page.items.length > 0 ? <CanonicalPagination page={page.page} hasNext={page.has_next} label="Graduate Tracer response pages" onPageChange={(nextPage) => router.push(pageHref(filters, nextPage, page.page_size))} /> : null}
    </section>
  );
}
