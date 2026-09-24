"use client";

import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { GoodMoralError, GoodMoralHeading, GoodMoralStatus, formatGoodMoralDateTime, goodMoralVariantLabel } from "@/features/good-moral/good-moral-shared";
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
  const queue = useGoodMoralListRequests(params, { query: { retry: false } });
  const page = queue.data?.data;
  const hasFilters = Boolean(filters.search || filters.variant || filters.status);

  return (
    <section className="space-y-6" aria-labelledby="good-moral-operational-heading">
      <GoodMoralHeading headingId="good-moral-operational-heading" title="Good Moral" description="Review and issue Good Moral Character certificate requests." />

      <form action="/portal/good-moral" method="get" className="grid gap-4 border-b border-border pb-6 sm:grid-cols-2 xl:grid-cols-[minmax(16rem,2fr)_minmax(10rem,1fr)_minmax(10rem,1fr)_auto]" key={JSON.stringify(filters)}>
        <div className="min-w-0">
          <Label htmlFor="good-moral-search">Search Student name or Institutional ID</Label>
          <Input id="good-moral-search" className="mt-2" name="search" type="search" placeholder="Search Student name or Institutional ID" defaultValue={filters.search} />
        </div>
        <div>
          <Label htmlFor="good-moral-variant">Variant</Label>
          <select id="good-moral-variant" name="variant" defaultValue={filters.variant} className="mt-2 min-h-10 w-full rounded-md border border-border bg-surface-raised px-3 py-2 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
            <option value="">All variants</option>
            <option value={GoodMoralVariantValue.CURRENT_STUDENT}>Current Student</option>
            <option value={GoodMoralVariantValue.GRADUATE}>Graduate</option>
          </select>
        </div>
        <div>
          <Label htmlFor="good-moral-status">Status</Label>
          <select id="good-moral-status" name="status" defaultValue={filters.status} className="mt-2 min-h-10 w-full rounded-md border border-border bg-surface-raised px-3 py-2 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
            <option value="">All statuses</option>
            <option value={GoodMoralStatusValue.REQUESTED}>Requested</option>
            <option value={GoodMoralStatusValue.ISSUED}>Issued</option>
            <option value={GoodMoralStatusValue.CANCELLED}>Cancelled</option>
          </select>
        </div>
        {filters.pageSize ? <input type="hidden" name="page_size" value={filters.pageSize} /> : null}
        <div className="flex flex-wrap items-end gap-3">
          <Button type="submit">Apply filters</Button>
          {hasFilters ? <Link href={pageHref({ ...filters, search: "", variant: "", status: "" }, 1)} className="inline-flex min-h-10 items-center px-2 text-sm font-semibold text-brand underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Clear filters</Link> : null}
        </div>
      </form>

      {queue.isPending ? (
        <div className="space-y-3" aria-busy="true" aria-label="Loading Good Moral requests">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
        </div>
      ) : queue.isError ? (
        <GoodMoralError error={queue.error} fallback="Good Moral requests could not be loaded." onRetry={() => void queue.refetch()} />
      ) : !page ? null : page.items.length === 0 ? (
        <p className="border-y border-border py-6 text-sm text-muted">
          {hasFilters ? "No Good Moral requests match these filters." : "No Good Moral requests have been recorded."}
        </p>
      ) : (
        <>
          <div className="overflow-x-auto rounded-md border border-border">
            <table className="min-w-[680px] w-full border-collapse text-left text-sm">
              <caption className="sr-only">Good Moral certificate request queue</caption>
              <thead className="bg-surface-muted text-xs uppercase tracking-wide text-muted">
                <tr>
                  <th scope="col" className="sticky left-0 z-10 bg-surface-muted px-4 py-3 font-semibold">Applicant</th>
                  <th scope="col" className="px-4 py-3 font-semibold">Variant</th>
                  <th scope="col" className="px-4 py-3 font-semibold">Status</th>
                  <th scope="col" className="px-4 py-3 font-semibold">Requested</th>
                  <th scope="col" className="px-4 py-3 font-semibold">Issued</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {page.items.map((item) => (
                  <tr key={item.id} className="align-top">
                    <th scope="row" className="sticky left-0 bg-surface-raised px-4 py-4 font-semibold text-ink">
                      <Link href={`/portal/good-moral/${item.id}`} className="text-brand underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
                        {item.applicant_name || "Applicant name not provided"}
                      </Link>
                    </th>
                    <td className="px-4 py-4 text-muted">{goodMoralVariantLabel(item.variant)}</td>
                    <td className="px-4 py-4"><GoodMoralStatus status={item.status} /></td>
                    <td className="whitespace-nowrap px-4 py-4 text-muted">{formatGoodMoralDateTime(item.created_at)}</td>
                    <td className="whitespace-nowrap px-4 py-4 text-muted">{formatGoodMoralDateTime(item.issued_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <nav aria-label="Good Moral request pages" className="flex items-center justify-between gap-4">
            {page.page > 1 ? (
              <Link href={pageHref(filters, page.page - 1)} className="inline-flex min-h-10 items-center rounded-md border border-border-strong bg-surface-raised px-4 text-sm font-semibold text-ink hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Previous</Link>
            ) : <Button variant="secondary" disabled>Previous</Button>}
            <p className="text-sm text-muted">Page {page.page}</p>
            {page.has_next ? (
              <Link href={pageHref({ ...filters, pageSize: page.page_size }, page.page + 1)} className="inline-flex min-h-10 items-center rounded-md border border-border-strong bg-surface-raised px-4 text-sm font-semibold text-ink hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Next</Link>
            ) : <Button variant="secondary" disabled>Next</Button>}
          </nav>
        </>
      )}
    </section>
  );
}
