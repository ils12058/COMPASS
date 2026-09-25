"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import {
  ExitInterviewError,
  ExitInterviewHeading,
  ExitInterviewStatus,
  shouldHideExitInterviewCachedData,
} from "@/features/exit-interviews/exit-interview-shared";
import { formatExitInterviewDateTime } from "@/features/exit-interviews/exit-interview-presentation";
import { useExitInterviewsList } from "@/lib/api/generated/exit-interviews/exit-interviews";
import { ExitInterviewStatusValue } from "@/lib/api/generated/model";
import type { ExitInterviewStatusValue as ExitInterviewStatusCode } from "@/lib/api/generated/model";

export type ExitInterviewOperationalFilters = {
  search: string;
  status: ExitInterviewStatusCode | "";
  page: number;
  pageSize?: number;
};

function pageHref(filters: ExitInterviewOperationalFilters, page: number): string {
  const params = new URLSearchParams();
  if (filters.search) params.set("search", filters.search);
  if (filters.status) params.set("status", filters.status);
  if (filters.pageSize) params.set("page_size", String(filters.pageSize));
  if (page > 1) params.set("page", String(page));
  const query = params.toString();
  return query ? `/portal/exit-interviews?${query}` : "/portal/exit-interviews";
}

export function ExitInterviewOperationalList({
  filters,
  notice,
}: {
  filters: ExitInterviewOperationalFilters;
  notice?: "reopened";
}) {
  const router = useRouter();
  const params = {
    ...(filters.search ? { search: filters.search } : {}),
    ...(filters.status ? { status: filters.status } : {}),
    page: filters.page,
    ...(filters.pageSize ? { page_size: filters.pageSize } : {}),
  };
  const queue = useExitInterviewsList(params, { query: { retry: false } });
  const page = queue.data?.data;
  const hasFilters = Boolean(filters.search || filters.status);
  const hideStaleQueue =
    queue.isError && shouldHideExitInterviewCachedData(queue.error);

  return (
    <section className="space-y-6" aria-labelledby="exit-interview-operational-heading">
      <ExitInterviewHeading
        id="exit-interview-operational-heading"
        title="Exit Interviews"
        description="Review submitted Exit Interviews and monitor draft status without access to draft answers."
      />
      {notice === "reopened" ? (
        <p role="status" className="border-l-4 border-success bg-success/5 px-4 py-3 text-sm text-ink">
          The Exit Interview was reopened for Student correction.
        </p>
      ) : null}

      <form
        action="/portal/exit-interviews"
        method="get"
        className="grid gap-4 border-b border-border pb-6 sm:grid-cols-[minmax(16rem,2fr)_minmax(10rem,1fr)_auto]"
        key={JSON.stringify(filters)}
      >
        <div className="min-w-0">
          <Label htmlFor="exit-interview-search">Search Student name or Institutional ID</Label>
          <Input
            id="exit-interview-search"
            className="mt-2"
            name="search"
            type="search"
            placeholder="Search Student name or Institutional ID"
            defaultValue={filters.search}
          />
        </div>
        <div>
          <Label htmlFor="exit-interview-status">Status</Label>
          <select
            id="exit-interview-status"
            name="status"
            defaultValue={filters.status}
            className="mt-2 min-h-10 w-full rounded-md border border-border bg-surface-raised px-3 py-2 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          >
            <option value="">All statuses</option>
            <option value={ExitInterviewStatusValue.DRAFT}>Draft</option>
            <option value={ExitInterviewStatusValue.SUBMITTED}>Submitted</option>
          </select>
        </div>
        {filters.pageSize ? <input type="hidden" name="page_size" value={filters.pageSize} /> : null}
        <div className="flex flex-wrap items-end gap-3">
          <Button type="submit">Apply filters</Button>
          {hasFilters ? (
            <Link
              href={pageHref({ ...filters, search: "", status: "" }, 1)}
              className="inline-flex min-h-10 items-center px-2 text-sm font-semibold text-brand underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
            >
              Clear filters
            </Link>
          ) : null}
        </div>
      </form>

      {queue.isFetching && !queue.isPending ? (
        <p role="status" className="text-xs text-muted">Refreshing Exit Interview results…</p>
      ) : null}
      {queue.isError && page && !hideStaleQueue ? (
        <ExitInterviewError
          error={queue.error}
          fallback="The Exit Interview queue could not be refreshed. Showing the last confirmed results."
          onRetry={() => void queue.refetch()}
        />
      ) : null}
      {queue.isPending ? (
        <div className="space-y-3" aria-busy="true" aria-label="Loading Exit Interview queue">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
        </div>
      ) : queue.isError && (!page || hideStaleQueue) ? (
        <ExitInterviewError
          error={queue.error}
          fallback="The Exit Interview queue could not be loaded."
          onRetry={() => void queue.refetch()}
        />
      ) : !page ? null : page.items.length === 0 && page.page > 1 ? (
        <div className="border-y border-border py-6">
          <p className="text-sm text-muted">No Exit Interviews are available on this page.</p>
          <Button
            variant="secondary"
            className="mt-3"
            onClick={() => router.push(pageHref({ ...filters, pageSize: page.page_size }, page.page - 1))}
          >
            Previous page
          </Button>
        </div>
      ) : page.items.length === 0 ? (
        <p className="border-y border-border py-6 text-sm text-muted">
          {hasFilters
            ? "No Exit Interviews match the current search or status filter."
            : "No Exit Interviews have been started."}
        </p>
      ) : (
        <>
          <div className="overflow-x-auto rounded-md border border-border">
            <table className="min-w-[700px] w-full border-collapse text-left text-sm">
              <caption className="sr-only">Head Guidance Exit Interview review queue</caption>
              <thead className="bg-surface-muted text-xs uppercase tracking-wide text-muted">
                <tr>
                  <th scope="col" className="sticky left-0 z-10 min-w-56 bg-surface-muted px-4 py-3 font-semibold">Student</th>
                  <th scope="col" className="px-4 py-3 font-semibold">Academic Year</th>
                  <th scope="col" className="px-4 py-3 font-semibold">Status</th>
                  <th scope="col" className="px-4 py-3 font-semibold">Submitted</th>
                  <th scope="col" className="px-4 py-3 font-semibold">Updated</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {page.items.map((item) => {
                  const studentName = item.student_name || item.student.display_name;
                  return (
                    <tr key={item.id} className="align-top">
                      <th scope="row" className="sticky left-0 z-10 bg-surface-raised px-4 py-4 font-semibold text-ink">
                        {item.status === "SUBMITTED" ? (
                          <Link
                            href={`/portal/exit-interviews/${item.id}`}
                            className="text-brand underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                          >
                            {studentName}
                          </Link>
                        ) : (
                          <span>{studentName}</span>
                        )}
                        {item.student.institutional_id ? (
                          <span className="mt-1 block text-xs font-normal text-muted">{item.student.institutional_id}</span>
                        ) : null}
                      </th>
                      <td className="whitespace-nowrap px-4 py-4 text-muted">{item.academic_year.label}</td>
                      <td className="px-4 py-4"><ExitInterviewStatus status={item.status} /></td>
                      <td className="whitespace-nowrap px-4 py-4 text-muted">
                        {formatExitInterviewDateTime(item.last_submitted_at ?? item.first_submitted_at)}
                      </td>
                      <td className="whitespace-nowrap px-4 py-4 text-muted">{formatExitInterviewDateTime(item.updated_at)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <CanonicalPagination
            page={page.page}
            hasNext={page.has_next}
            label="Exit Interview queue pages"
            onPageChange={(nextPage) => router.push(pageHref({ ...filters, pageSize: page.page_size }, nextPage))}
          />
        </>
      )}
    </section>
  );
}
