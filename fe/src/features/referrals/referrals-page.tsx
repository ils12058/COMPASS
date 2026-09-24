"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { getReferralAccess } from "@/features/referrals/referrals-access";
import {
  ReferralAccessUnavailable,
  ReferralHeading,
  ReferralQueryError,
} from "@/features/referrals/referrals-shared";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { useReferralsList } from "@/lib/api/generated/referrals/referrals";
import { formatDateOnly, formatDateTime } from "@/lib/date-time";

export type ReferralListFilters = {
  search: string;
  fromDate: string;
  toDate: string;
  includeVoided: boolean;
  page: number;
};

function filtersToUrl(filters: ReferralListFilters): string {
  const params = new URLSearchParams();
  if (filters.search.trim()) params.set("search", filters.search.trim());
  if (filters.fromDate) params.set("from_date", filters.fromDate);
  if (filters.toDate) params.set("to_date", filters.toDate);
  if (filters.includeVoided) params.set("include_voided", "true");
  if (filters.page > 1) params.set("page", String(filters.page));
  const query = params.toString();
  return query ? `/portal/referrals?${query}` : "/portal/referrals";
}

export function ReferralsPage({ filters }: { filters: ReferralListFilters }) {
  const router = useRouter();
  const { user } = usePortalSession();
  const access = getReferralAccess(user);
  const [draft, setDraft] = useState(filters);
  const referrals = useReferralsList(
    {
      ...(filters.search ? { search: filters.search } : {}),
      ...(filters.fromDate ? { from_date: filters.fromDate } : {}),
      ...(filters.toDate ? { to_date: filters.toDate } : {}),
      ...(filters.includeVoided ? { include_voided: true } : {}),
      page: filters.page,
      page_size: 20,
    },
    { query: { enabled: access.canView, retry: false } },
  );

  if (!access.hasWorkspace) return <ReferralAccessUnavailable />;

  const data = referrals.data?.data;
  const items = data?.items ?? [];
  const filtered = Boolean(
    filters.search || filters.fromDate || filters.toDate || filters.includeVoided || filters.page > 1,
  );

  function submitFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (draft.fromDate && draft.toDate && draft.fromDate > draft.toDate) return;
    router.push(filtersToUrl({ ...draft, page: 1 }), { scroll: false });
  }

  return (
    <main className="space-y-7">
      <ReferralHeading
        title="Referrals"
        description="Record and review Student referrals within your authorized Guidance scope."
        action={access.canManage ? (
          <Link href="/portal/referrals/new" className="inline-flex min-h-10 items-center justify-center rounded-md border border-brand bg-brand px-4 py-2 text-sm font-semibold text-on-brand hover:bg-brand-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
            Record referral
          </Link>
        ) : null}
      />

      {!access.canView ? (
        <p className="max-w-2xl border-y border-border py-5 text-sm leading-6 text-muted">
          Your current access allows recording Referrals but not reviewing existing Referral records.
        </p>
      ) : (
        <>
          <form onSubmit={submitFilters} className="grid gap-4 border-b border-border pb-6 md:grid-cols-2 xl:grid-cols-4 xl:items-end">
            <div className="grid gap-2 md:col-span-2 xl:col-span-1">
              <Label htmlFor="referrals-search">Search</Label>
              <Input
                id="referrals-search"
                type="search"
                maxLength={160}
                placeholder="Search reference, Student name, or Institutional ID"
                value={draft.search}
                onChange={(event) => setDraft({ ...draft, search: event.target.value })}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="referrals-from">From</Label>
              <Input id="referrals-from" type="date" value={draft.fromDate} onChange={(event) => setDraft({ ...draft, fromDate: event.target.value })} />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="referrals-to">To</Label>
              <Input id="referrals-to" type="date" value={draft.toDate} onChange={(event) => setDraft({ ...draft, toDate: event.target.value })} />
            </div>
            <div className="flex min-h-11 items-center gap-3">
              <input
                id="referrals-include-voided"
                className="h-4 w-4 accent-brand"
                type="checkbox"
                checked={draft.includeVoided}
                onChange={(event) => setDraft({ ...draft, includeVoided: event.target.checked })}
              />
              <Label htmlFor="referrals-include-voided">Include voided</Label>
            </div>
            <div className="flex flex-wrap gap-2 md:col-span-2 xl:col-span-4">
              <Button type="submit" variant="secondary">Apply filters</Button>
              {filtered ? <Link href="/portal/referrals" className="inline-flex min-h-10 items-center px-3 text-sm font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Clear filters</Link> : null}
            </div>
          </form>

          {draft.fromDate && draft.toDate && draft.fromDate > draft.toDate ? (
            <p role="alert" className="text-sm text-danger">From date must not be after To date.</p>
          ) : null}

          {referrals.isError ? (
            <ReferralQueryError error={referrals.error} fallback="Referrals could not be loaded." onRetry={() => void referrals.refetch()} />
          ) : referrals.isPending ? (
            <div aria-label="Loading Referrals" className="space-y-3" aria-busy="true">
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
            </div>
          ) : items.length === 0 ? (
            <div className="border-y border-border py-6">
              <p className="text-sm text-muted">
                {filtered ? "No Referrals match these filters." : "No Referrals have been recorded in your current scope."}
              </p>
              {filtered ? <Link href="/portal/referrals" className="mt-3 inline-block text-sm font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Clear filters</Link> : null}
              {(data?.page ?? filters.page) > 1 ? (
                <CanonicalPagination
                  page={data?.page ?? filters.page}
                  hasNext={data?.has_next ?? false}
                  onPageChange={(page) => router.push(filtersToUrl({ ...filters, page }), { scroll: false })}
                  label="Referral results"
                />
              ) : null}
            </div>
          ) : (
            <>
              <p className="text-sm text-muted" aria-live="polite">
                Showing {items.length} Referrals on page {data?.page ?? filters.page}.
              </p>
              <ul className="divide-y divide-border border-y border-border md:hidden">
                {items.map((referral) => (
                  <li key={referral.id} className="space-y-2 py-4">
                    <Link href={`/portal/referrals/${referral.id}`} className="font-semibold text-brand underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
                      {referral.reference_code}
                    </Link>
                    <p className="text-sm font-medium text-ink">{referral.student_name_snapshot}</p>
                    <p className="text-sm text-muted">{referral.course_year_block_snapshot}</p>
                    <p className="text-sm text-muted">Referred {formatDateOnly(referral.referred_on)}{referral.received_at ? ` · Received ${formatDateTime(referral.received_at)}` : ""}</p>
                    {referral.status_note ? <p className="whitespace-pre-wrap break-words text-sm text-ink"><span className="font-semibold">Status note:</span> {referral.status_note}</p> : <p className="text-sm text-muted">No status note</p>}
                    {referral.voided_at ? <p className="text-sm font-semibold text-warning">Voided</p> : null}
                  </li>
                ))}
              </ul>
              <div className="hidden overflow-x-auto md:block">
                <table className="w-full min-w-[760px] border-collapse text-left text-sm">
                  <thead>
                    <tr className="border-b border-border-strong text-xs font-semibold uppercase tracking-wide text-muted">
                      <th scope="col" className="px-3 py-3">Referral / Student</th>
                      <th scope="col" className="px-3 py-3">Course / Year / Block</th>
                      <th scope="col" className="px-3 py-3">Referred</th>
                      <th scope="col" className="px-3 py-3">Received</th>
                      <th scope="col" className="px-3 py-3">Status note</th>
                      {filters.includeVoided ? <th scope="col" className="px-3 py-3">Record state</th> : null}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {items.map((referral) => (
                      <tr key={referral.id} className="align-top">
                        <td className="px-3 py-4">
                          <Link href={`/portal/referrals/${referral.id}`} className="font-semibold text-brand underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">{referral.reference_code}</Link>
                          <span className="mt-1 block text-ink">{referral.student_name_snapshot}</span>
                        </td>
                        <td className="px-3 py-4 text-ink">{referral.course_year_block_snapshot}</td>
                        <td className="px-3 py-4 text-ink">{formatDateOnly(referral.referred_on)}</td>
                        <td className="px-3 py-4 text-ink">{formatDateTime(referral.received_at)}</td>
                        <td className="max-w-64 px-3 py-4 text-ink">
                          {referral.status_note ? <p className="line-clamp-2 whitespace-pre-wrap">{referral.status_note}</p> : <span className="text-muted">—</span>}
                        </td>
                        {filters.includeVoided ? <td className="px-3 py-4">{referral.voided_at ? <span className="font-semibold text-warning">Voided</span> : <span className="text-muted">—</span>}</td> : null}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <CanonicalPagination
                page={data?.page ?? filters.page}
                hasNext={data?.has_next ?? false}
                onPageChange={(page) => router.push(filtersToUrl({ ...filters, page }), { scroll: false })}
                label="Referral results"
              />
            </>
          )}
        </>
      )}
    </main>
  );
}
