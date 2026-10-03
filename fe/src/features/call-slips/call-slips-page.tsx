"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { safeQueryData } from "@/features/freshness/query-freshness";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
import { CallSlipAccessUnavailable, CallSlipHeading, CallSlipListSkeleton, CallSlipQueryError, callSlipDestinationLabel, callSlipStateLabel } from "@/features/call-slips/call-slips-shared";
import { getCallSlipAccess } from "@/features/call-slips/call-slips-access";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { getReferralAccess } from "@/features/referrals/referrals-access";
import { useCallSlipsList, useCallSlipsListMy } from "@/lib/api/generated/call-slips/call-slips";
import { CallSlipDestinationTypeValue, CallSlipLifecycleStateValue } from "@/lib/api/generated/model";
import type { CallSlipDestinationTypeValue as CallSlipDestinationType } from "@/lib/api/generated/model";
import { formatInstitutionalDateTime } from "@/lib/institutional-time";

export type CallSlipListFilters = {
  search: string;
  destination: "" | CallSlipDestinationType;
  fromDate: string;
  toDate: string;
  includeVoided: boolean;
  state: "" | CallSlipLifecycleStateValue;
  page: number;
};

export type CallSlipStudentListFilters = {
  fromDate: string;
  toDate: string;
  state: "" | CallSlipLifecycleStateValue;
  page: number;
};

function lifecycleStateFrom(value: string): "" | CallSlipLifecycleStateValue {
  return Object.values(CallSlipLifecycleStateValue).find((state) => state === value) ?? "";
}

function operationalFiltersToUrl(filters: CallSlipListFilters): string {
  const params = new URLSearchParams();
  if (filters.search.trim()) params.set("search", filters.search.trim());
  if (filters.destination) params.set("destination", filters.destination);
  if (filters.fromDate) params.set("from_date", filters.fromDate);
  if (filters.toDate) params.set("to_date", filters.toDate);
  if (filters.includeVoided) params.set("include_voided", "true");
  if (filters.state) params.set("state", filters.state);
  if (filters.page > 1) params.set("page", String(filters.page));
  const query = params.toString();
  return query ? `/portal/call-slips?${query}` : "/portal/call-slips";
}

function studentFiltersToUrl(filters: CallSlipStudentListFilters): string {
  const params = new URLSearchParams();
  if (filters.fromDate) params.set("from_date", filters.fromDate);
  if (filters.toDate) params.set("to_date", filters.toDate);
  if (filters.state) params.set("state", filters.state);
  if (filters.page > 1) params.set("page", String(filters.page));
  const query = params.toString();
  return query ? `/portal/call-slips?${query}` : "/portal/call-slips";
}

export function CallSlipsPage({
  operationalFilters,
  studentFilters,
}: {
  operationalFilters: CallSlipListFilters;
  studentFilters: CallSlipStudentListFilters;
}) {
  const { user } = usePortalSession();
  const access = getCallSlipAccess(user);

  if (!access.hasWorkspace) return <CallSlipAccessUnavailable />;
  if (access.isStudent) return <StudentCallSlipsPage filters={studentFilters} />;
  if (access.isOperational) return <OperationalCallSlipsPage filters={operationalFilters} />;
  return <CallSlipAccessUnavailable />;
}

function StudentCallSlipsPage({ filters }: { filters: CallSlipStudentListFilters }) {
  const router = useRouter();
  const [draft, setDraft] = useState(filters);
  const slips = useCallSlipsListMy(
    {
      ...(filters.fromDate ? { from_date: filters.fromDate } : {}),
      ...(filters.toDate ? { to_date: filters.toDate } : {}),
      ...(filters.state ? { state: filters.state } : {}),
      page: filters.page,
      page_size: 20,
    },
    { query: { retry: false } },
  );

  function submitFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (draft.fromDate && draft.toDate && draft.fromDate > draft.toDate) return;
    router.push(studentFiltersToUrl({ ...draft, page: 1 }), { scroll: false });
  }

  const data = safeQueryData(slips)?.data;
  const items = data?.items ?? [];
  const hasFilters = Boolean(filters.fromDate || filters.toDate || filters.state || filters.page > 1);

  return (
    <div className="space-y-7">
      <CallSlipHeading title="My Call Slips"  />
      <form onSubmit={submitFilters} className="grid gap-4 border-b border-border pb-6 sm:grid-cols-3 sm:items-end">
        <div className="grid gap-2">
          <Label htmlFor="my-call-slips-state">Status</Label>
          <Select id="my-call-slips-state" value={draft.state} onChange={(event) => setDraft({ ...draft, state: lifecycleStateFrom(event.target.value) })}>
            <option value="">All statuses</option>
            {Object.values(CallSlipLifecycleStateValue).map((state) => (
              <option key={state} value={state}>{callSlipStateLabel(state, true)}</option>
            ))}
          </Select>
        </div>
        <div className="grid gap-2">
          <Label htmlFor="my-call-slips-from">From</Label>
          <Input id="my-call-slips-from" type="date" value={draft.fromDate} onChange={(event) => setDraft({ ...draft, fromDate: event.target.value })} />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="my-call-slips-to">To</Label>
          <Input id="my-call-slips-to" type="date" value={draft.toDate} onChange={(event) => setDraft({ ...draft, toDate: event.target.value })} />
        </div>
        {draft.fromDate && draft.toDate && draft.fromDate > draft.toDate ? (
          <p role="alert" className="text-sm text-danger sm:col-span-3">From date must not be after To date.</p>
        ) : null}
        <div className="flex flex-wrap gap-2 sm:col-span-3">
          <Button type="submit" variant="secondary">Apply filters</Button>
          {hasFilters ? <Link href="/portal/call-slips" className="inline-flex min-h-10 items-center px-3 text-sm font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Clear filters</Link> : null}
        </div>
      </form>
      {slips.isError && data ? <RefreshFailureNotice onRetry={() => void slips.refetch()} retrying={slips.isFetching} /> : null}

      {!data && slips.isError ? (
        <CallSlipQueryError error={slips.error} fallback="Your Call Slips could not be loaded." onRetry={() => void slips.refetch()} />
      ) : slips.isPending ? (
        <CallSlipListSkeleton label="Loading My Call Slips…" />
      ) : items.length === 0 ? (
        <div className="border-y border-border py-6">
          <p className="text-sm text-muted">{hasFilters ? "No Call Slips match these filters." : "You do not have any Call Slips yet."}</p>
          {hasFilters ? <Link href="/portal/call-slips" className="mt-3 inline-block text-sm font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Clear filters</Link> : null}
          <CanonicalPagination page={data?.page ?? filters.page} hasNext={data?.has_next ?? false} onPageChange={(page) => router.push(studentFiltersToUrl({ ...filters, page }), { scroll: false })} label="My Call Slip results" />
        </div>
      ) : (
        <>
          <p className="text-sm text-muted" aria-live="polite">Showing {items.length} {items.length === 1 ? "Call Slip" : "Call Slips"} on page {data?.page ?? filters.page}.</p>
          <ul className="divide-y divide-border border-y border-border">
            {items.map((slip) => (
              <li key={slip.id} className="grid gap-x-8 gap-y-2 py-4 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
                <div>
                  <Link href={`/portal/call-slips/${slip.id}`} className="font-semibold text-brand underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Call Slip for {formatInstitutionalDateTime(slip.report_at)}</Link>
                </div>
                <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
                  <div><dt className="text-xs font-semibold text-muted">Destination</dt><dd className="mt-1 text-ink">{callSlipDestinationLabel(slip.destination_type, slip.other_destination)}</dd></div>
                  <div><dt className="text-xs font-semibold text-muted">Issued by</dt><dd className="mt-1 text-ink">{slip.issued_by_name_snapshot}</dd></div>
                  <div><dt className="text-xs font-semibold text-muted">State</dt><dd className="mt-1 text-ink">{callSlipStateLabel(slip.state, true)}</dd></div>
                </dl>
              </li>
            ))}
          </ul>
          <CanonicalPagination page={data?.page ?? filters.page} hasNext={data?.has_next ?? false} onPageChange={(page) => router.push(studentFiltersToUrl({ ...filters, page }), { scroll: false })} label="My Call Slip results" />
        </>
      )}
    </div>
  );
}

// Voided records stay limited to operational managers, as with the Include voided toggle.
function effectiveState(
  filters: CallSlipListFilters,
  canManage: boolean,
): "" | CallSlipLifecycleStateValue {
  return filters.state === CallSlipLifecycleStateValue.VOIDED && !canManage ? "" : filters.state;
}

function OperationalCallSlipsPage({ filters }: { filters: CallSlipListFilters }) {
  const router = useRouter();
  const { user } = usePortalSession();
  const access = getCallSlipAccess(user);
  const referralAccess = getReferralAccess(user);
  const [draft, setDraft] = useState(() => access.canManageOperational ? filters : { ...filters, includeVoided: false });
  const state = effectiveState(filters, access.canManageOperational);
  const slips = useCallSlipsList(
    {
      ...(filters.search ? { search: filters.search } : {}),
      ...(filters.destination ? { destination_type: filters.destination } : {}),
      ...(filters.fromDate ? { from_date: filters.fromDate } : {}),
      ...(filters.toDate ? { to_date: filters.toDate } : {}),
      ...(filters.includeVoided && access.canManageOperational ? { include_voided: true } : {}),
      ...(state ? { state } : {}),
      page: filters.page,
      page_size: 20,
    },
    { query: { enabled: access.canViewOperational, retry: false } },
  );

  function submitFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (draft.fromDate && draft.toDate && draft.fromDate > draft.toDate) return;
    const normalizedDraft = access.canManageOperational ? draft : { ...draft, includeVoided: false };
    router.push(operationalFiltersToUrl({ ...normalizedDraft, page: 1 }), { scroll: false });
  }

  const data = safeQueryData(slips)?.data;
  const items = data?.items ?? [];
  const effectiveFilters = access.canManageOperational
    ? filters
    : { ...filters, includeVoided: false, state: effectiveState(filters, false) };
  const hasFilters = Boolean(effectiveFilters.search || effectiveFilters.destination || effectiveFilters.fromDate || effectiveFilters.toDate || effectiveFilters.includeVoided || effectiveFilters.state || effectiveFilters.page > 1);

  return (
    <div className="space-y-7">
      <CallSlipHeading
        title="Call Slips"
        description={access.canManageOperational ? "Review and manage Call Slips assigned to your guidance area." : "Review Call Slips assigned to your guidance area."}
        action={access.canManageOperational ? <Link href="/portal/call-slips/new" className={buttonVariants({ variant: "primary" })}>Issue Call Slip</Link> : null}
      />
      <form onSubmit={submitFilters} className="grid gap-4 border-b border-border pb-6 md:grid-cols-2 xl:grid-cols-5 xl:items-end">
        <div className="grid gap-2 md:col-span-2 xl:col-span-2">
          <Label htmlFor="call-slips-search">Search</Label>
          <Input id="call-slips-search" type="search" maxLength={160} placeholder="Search Student or Referral reference" value={draft.search} onChange={(event) => setDraft({ ...draft, search: event.target.value })} />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="call-slips-destination">Destination</Label>
          <Select id="call-slips-destination" value={draft.destination} onChange={(event) => setDraft({ ...draft, destination: event.target.value as CallSlipListFilters["destination"] })}>
            <option value="">All destinations</option>
            <option value={CallSlipDestinationTypeValue.GUIDANCE_OFFICE}>Guidance Office</option>
            <option value={CallSlipDestinationTypeValue.OTHER}>Other</option>
          </Select>
        </div>
        <div className="grid gap-2">
          <Label htmlFor="call-slips-state">Status</Label>
          <Select id="call-slips-state" value={draft.state} onChange={(event) => setDraft({ ...draft, state: lifecycleStateFrom(event.target.value) })}>
            <option value="">{access.canManageOperational ? "Active and completed" : "All statuses"}</option>
            <option value={CallSlipLifecycleStateValue.ACTIVE}>{callSlipStateLabel(CallSlipLifecycleStateValue.ACTIVE, false)}</option>
            <option value={CallSlipLifecycleStateValue.COMPLETED}>{callSlipStateLabel(CallSlipLifecycleStateValue.COMPLETED, false)}</option>
            {access.canManageOperational ? <option value={CallSlipLifecycleStateValue.VOIDED}>{callSlipStateLabel(CallSlipLifecycleStateValue.VOIDED, false)}</option> : null}
          </Select>
        </div>
        <div className="grid gap-2"><Label htmlFor="call-slips-from">From</Label><Input id="call-slips-from" type="date" value={draft.fromDate} onChange={(event) => setDraft({ ...draft, fromDate: event.target.value })} /></div>
        <div className="grid gap-2"><Label htmlFor="call-slips-to">To</Label><Input id="call-slips-to" type="date" value={draft.toDate} onChange={(event) => setDraft({ ...draft, toDate: event.target.value })} /></div>
        {access.canManageOperational ? (
          <div className="flex min-h-11 items-center gap-3">
            <input id="call-slips-include-voided" className="h-4 w-4 accent-brand" type="checkbox" checked={draft.includeVoided} onChange={(event) => setDraft({ ...draft, includeVoided: event.target.checked })} />
            <Label htmlFor="call-slips-include-voided">Include voided</Label>
          </div>
        ) : null}
        {draft.fromDate && draft.toDate && draft.fromDate > draft.toDate ? <p role="alert" className="text-sm text-danger md:col-span-2">From date must not be after To date.</p> : null}
        <div className="flex flex-wrap gap-2 md:col-span-2 xl:col-span-5">
          <Button type="submit" variant="secondary">Apply filters</Button>
          {hasFilters ? <Link href="/portal/call-slips" className="inline-flex min-h-10 items-center px-3 text-sm font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Clear filters</Link> : null}
        </div>
      </form>
      {slips.isError && data ? <RefreshFailureNotice onRetry={() => void slips.refetch()} retrying={slips.isFetching} /> : null}

      {!data && slips.isError ? (
        <CallSlipQueryError error={slips.error} fallback="Call Slips could not be loaded." onRetry={() => void slips.refetch()} />
      ) : slips.isPending ? (
        <CallSlipListSkeleton />
      ) : items.length === 0 ? (
        <div className="border-y border-border py-6">
          <p className="text-sm text-muted">{hasFilters ? "No Call Slips match these filters." : "No Call Slips have been recorded."}</p>
          {hasFilters ? <Link href="/portal/call-slips" className="mt-3 inline-block text-sm font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Clear filters</Link> : null}
          <CanonicalPagination page={data?.page ?? filters.page} hasNext={data?.has_next ?? false} onPageChange={(page) => router.push(operationalFiltersToUrl({ ...effectiveFilters, page }), { scroll: false })} label="Call Slip results" />
        </div>
      ) : (
        <>
          <p className="text-sm text-muted" aria-live="polite">Showing {items.length} {items.length === 1 ? "Call Slip" : "Call Slips"} on page {data?.page ?? filters.page}.</p>
          <ul className="divide-y divide-border border-y border-border md:hidden">
            {items.map((slip) => (
              <li key={slip.id} className="space-y-2 py-4">
                <Link href={`/portal/call-slips/${slip.id}`} className="font-semibold text-brand underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">{slip.student_name_snapshot}</Link>
                {slip.student_institutional_id ? <p className="text-xs text-muted">{slip.student_institutional_id}</p> : null}
                <p className="text-sm text-ink">{slip.course_year_snapshot}</p>
                <p className="text-sm text-muted">Report {formatInstitutionalDateTime(slip.report_at)} · {callSlipDestinationLabel(slip.destination_type, slip.other_destination)}</p>
                <p className="text-sm text-muted">Issued by {slip.issued_by_name_snapshot} · {callSlipStateLabel(slip.state)}</p>
                {slip.referral ? <p className="text-sm text-muted">Referral {referralAccess.canView ? <Link href={`/portal/referrals/${slip.referral.id}`} className="font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">{slip.referral.reference_code}</Link> : slip.referral.reference_code}</p> : null}
              </li>
            ))}
          </ul>
          <div className="hidden overflow-x-auto md:block">
            <table className="w-full min-w-[850px] border-collapse text-left text-sm">
              <caption className="sr-only">Call Slips</caption>
              <thead><tr className="border-b border-border-strong text-xs font-semibold uppercase tracking-wide text-muted">
                <th scope="col" className="px-3 py-3">Student</th><th scope="col" className="px-3 py-3">Course / Year</th><th scope="col" className="px-3 py-3">Report</th><th scope="col" className="px-3 py-3">Destination</th><th scope="col" className="px-3 py-3">Issuer</th><th scope="col" className="px-3 py-3">State</th><th scope="col" className="px-3 py-3">Referral</th>
              </tr></thead>
              <tbody className="divide-y divide-border">{items.map((slip) => (
                <tr key={slip.id} className="align-top">
                  <th scope="row" className="px-3 py-4 font-normal"><Link href={`/portal/call-slips/${slip.id}`} className="font-semibold text-brand underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">{slip.student_name_snapshot}</Link>{slip.student_institutional_id ? <span className="mt-1 block text-xs text-muted">{slip.student_institutional_id}</span> : null}</th>
                  <td className="px-3 py-4 text-ink">{slip.course_year_snapshot}</td><td className="px-3 py-4 text-ink">{formatInstitutionalDateTime(slip.report_at)}</td><td className="px-3 py-4 text-ink">{callSlipDestinationLabel(slip.destination_type, slip.other_destination)}</td><td className="px-3 py-4 text-ink">{slip.issued_by_name_snapshot}</td><td className="px-3 py-4 text-ink">{callSlipStateLabel(slip.state)}</td>
                  <td className="px-3 py-4 text-ink">{slip.referral ? referralAccess.canView ? <Link href={`/portal/referrals/${slip.referral.id}`} className="font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">{slip.referral.reference_code}</Link> : slip.referral.reference_code : <span className="text-muted">—</span>}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
          <CanonicalPagination page={data?.page ?? filters.page} hasNext={data?.has_next ?? false} onPageChange={(page) => router.push(operationalFiltersToUrl({ ...effectiveFilters, page }), { scroll: false })} label="Call Slip results" />
        </>
      )}
    </div>
  );
}
