"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { dataTable } from "@/components/ui/data-table";
import { FilterField } from "@/components/ui/filter-toolbar";
import { FloatingListTools, ListSearchField } from "@/components/ui/floating-list-tools";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { Select } from "@/components/ui/select";
import { safeQueryData } from "@/features/freshness/query-freshness";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
import { CallSlipAccessUnavailable, CallSlipHeading, CallSlipListSkeleton, callSlipDestinationLabel, callSlipErrorMessage, callSlipStateLabel } from "@/features/call-slips/call-slips-shared";
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
  const draftRangeInvalid = Boolean(draft.fromDate && draft.toDate && draft.fromDate > draft.toDate);

  return (
    <div className="space-y-5">
      <CallSlipHeading title="My Call Slips"  />
      <form onSubmit={submitFilters} aria-label="My Call Slips filters">
        <FloatingListTools
          submits
          invalid={draftRangeInvalid}
          filterCount={[filters.state, filters.fromDate, filters.toDate].filter(Boolean).length}
          filtersClassName="sm:grid-cols-3"
          clear={hasFilters ? <Link href="/portal/call-slips" className={buttonVariants({ variant: "quiet" })}>Clear filters</Link> : undefined}
          filters={<>
          <FilterField label="Status" htmlFor="my-call-slips-state">
            <Select id="my-call-slips-state" value={draft.state} onChange={(event) => setDraft({ ...draft, state: lifecycleStateFrom(event.target.value) })}>
              <option value="">All statuses</option>
              {Object.values(CallSlipLifecycleStateValue).map((state) => (
                <option key={state} value={state}>{callSlipStateLabel(state, true)}</option>
              ))}
            </Select>
          </FilterField>
          <FilterField label="From" htmlFor="my-call-slips-from">
            <Input id="my-call-slips-from" type="date" value={draft.fromDate} onChange={(event) => setDraft({ ...draft, fromDate: event.target.value })} />
          </FilterField>
          <FilterField label="To" htmlFor="my-call-slips-to">
            <Input id="my-call-slips-to" type="date" value={draft.toDate} onChange={(event) => setDraft({ ...draft, toDate: event.target.value })} />
          </FilterField>
          {draftRangeInvalid ? (
            <p role="alert" className="text-sm text-danger sm:col-span-full">From date must not be after To date.</p>
          ) : null}
          </>}
        />
      </form>
      {slips.isError && data ? <RefreshFailureNotice onRetry={() => void slips.refetch()} retrying={slips.isFetching} /> : null}

      <Panel aria-labelledby="my-call-slips-results">
        <PanelHeader
          title="Call Slips"
          titleId="my-call-slips-results"
          context={data && items.length > 0 ? `Showing ${items.length} ${items.length === 1 ? "Call Slip" : "Call Slips"} on page ${data.page}.` : null}
        />
        {!data && slips.isError ? (
          <PanelMessage role="alert" tone="danger" action={<Button variant="secondary" onClick={() => void slips.refetch()}>Retry</Button>}>
            {callSlipErrorMessage(slips.error, "Your Call Slips could not be loaded.")}
          </PanelMessage>
        ) : slips.isPending ? (
          <CallSlipListSkeleton label="Loading My Call Slips…" framed={false} />
        ) : items.length === 0 ? (
          <PanelMessage action={hasFilters ? <Link href="/portal/call-slips" className={buttonVariants({ variant: "secondary" })}>Clear filters</Link> : undefined}>
            {hasFilters ? "No Call Slips match these filters." : "You do not have any Call Slips yet."}
          </PanelMessage>
        ) : (
          <ul className="divide-y divide-border">
            {items.map((slip) => (
              <li key={slip.id} className="grid gap-x-8 gap-y-2 px-4 py-4 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] sm:px-5">
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
        )}
        {data ? <CanonicalPagination className="border-brand-line px-4 py-3 sm:px-5" page={data.page ?? filters.page} hasNext={data.has_next ?? false} onPageChange={(page) => router.push(studentFiltersToUrl({ ...filters, page }), { scroll: false })} label="My Call Slip results" /> : null}
      </Panel>
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
  const advancedCount = [effectiveFilters.destination, effectiveFilters.state, effectiveFilters.fromDate, effectiveFilters.toDate, effectiveFilters.includeVoided].filter(Boolean).length;
  const draftRangeInvalid = Boolean(draft.fromDate && draft.toDate && draft.fromDate > draft.toDate);

  return (
    <div className="space-y-5">
      <CallSlipHeading
        title="Call Slips"
        action={access.canManageOperational ? <Link href="/portal/call-slips/new" className={buttonVariants({ variant: "primary" })}>Issue Call Slip</Link> : null}
      />
      <form onSubmit={submitFilters} role="search" aria-label="Call Slips">
        <FloatingListTools
          submits
          invalid={draftRangeInvalid}
          filterCount={advancedCount}
          clear={hasFilters ? <Link href="/portal/call-slips" className={buttonVariants({ variant: "quiet" })}>Clear filters</Link> : undefined}
          filters={
            <>
          <FilterField label="Destination" htmlFor="call-slips-destination">
            <Select id="call-slips-destination" value={draft.destination} onChange={(event) => setDraft({ ...draft, destination: event.target.value as CallSlipListFilters["destination"] })}>
              <option value="">All destinations</option>
              <option value={CallSlipDestinationTypeValue.GUIDANCE_OFFICE}>Guidance Office</option>
              <option value={CallSlipDestinationTypeValue.OTHER}>Other</option>
            </Select>
          </FilterField>
          <FilterField label="Status" htmlFor="call-slips-state">
            <Select id="call-slips-state" value={draft.state} onChange={(event) => setDraft({ ...draft, state: lifecycleStateFrom(event.target.value) })}>
              <option value="">{access.canManageOperational ? "Active and completed" : "All statuses"}</option>
              <option value={CallSlipLifecycleStateValue.ACTIVE}>{callSlipStateLabel(CallSlipLifecycleStateValue.ACTIVE, false)}</option>
              <option value={CallSlipLifecycleStateValue.COMPLETED}>{callSlipStateLabel(CallSlipLifecycleStateValue.COMPLETED, false)}</option>
              {access.canManageOperational ? <option value={CallSlipLifecycleStateValue.VOIDED}>{callSlipStateLabel(CallSlipLifecycleStateValue.VOIDED, false)}</option> : null}
            </Select>
          </FilterField>
          <FilterField label="From" htmlFor="call-slips-from"><Input id="call-slips-from" type="date" value={draft.fromDate} onChange={(event) => setDraft({ ...draft, fromDate: event.target.value })} /></FilterField>
          <FilterField label="To" htmlFor="call-slips-to"><Input id="call-slips-to" type="date" value={draft.toDate} onChange={(event) => setDraft({ ...draft, toDate: event.target.value })} /></FilterField>
          {access.canManageOperational ? (
            <div className="flex min-h-11 items-center gap-3 self-end">
              <input id="call-slips-include-voided" className="h-4 w-4 accent-brand" type="checkbox" checked={draft.includeVoided} onChange={(event) => setDraft({ ...draft, includeVoided: event.target.checked })} />
              <Label htmlFor="call-slips-include-voided">Include voided</Label>
            </div>
          ) : null}
          {draftRangeInvalid ? <p role="alert" className="text-sm text-danger sm:col-span-full">From date must not be after To date.</p> : null}
            </>
          }
        >
          <ListSearchField id="call-slips-search" label="Search Call Slips" maxLength={160} placeholder="Search Student or Referral reference" value={draft.search} onChange={(event) => setDraft({ ...draft, search: event.target.value })} />
        </FloatingListTools>
      </form>
      {slips.isError && data ? <RefreshFailureNotice onRetry={() => void slips.refetch()} retrying={slips.isFetching} /> : null}

      <Panel aria-labelledby="call-slips-results">
        <PanelHeader
          title="Call Slips"
          titleId="call-slips-results"
          context={data && items.length > 0 ? `Showing ${items.length} ${items.length === 1 ? "Call Slip" : "Call Slips"} on page ${data.page}.` : null}
        />
        {!data && slips.isError ? (
          <PanelMessage role="alert" tone="danger" action={<Button variant="secondary" onClick={() => void slips.refetch()}>Retry</Button>}>
            {callSlipErrorMessage(slips.error, "Call Slips could not be loaded.")}
          </PanelMessage>
        ) : slips.isPending ? (
          <CallSlipListSkeleton framed={false} />
        ) : items.length === 0 ? (
          <PanelMessage action={hasFilters ? <Link href="/portal/call-slips" className={buttonVariants({ variant: "secondary" })}>Clear filters</Link> : undefined}>
            {hasFilters ? "No Call Slips match these filters." : "No Call Slips have been recorded."}
          </PanelMessage>
        ) : (
          <>
            <ul className="divide-y divide-border md:hidden">
              {items.map((slip) => (
                <li key={slip.id} className="space-y-2 px-4 py-4">
                  <Link href={`/portal/call-slips/${slip.id}`} className="font-semibold text-brand underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">{slip.student_name_snapshot}</Link>
                  {slip.student_institutional_id ? <p className="text-xs text-muted">{slip.student_institutional_id}</p> : null}
                  <p className="text-sm text-ink">{slip.course_year_snapshot}</p>
                  <p className="text-sm text-muted">Report {formatInstitutionalDateTime(slip.report_at)} · {callSlipDestinationLabel(slip.destination_type, slip.other_destination)}</p>
                  <p className="text-sm text-muted">Issued by {slip.issued_by_name_snapshot} · {callSlipStateLabel(slip.state)}</p>
                  {slip.referral ? <p className="text-sm text-muted">Referral {referralAccess.canView ? <Link href={`/portal/referrals/${slip.referral.id}`} className="font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">{slip.referral.reference_code}</Link> : slip.referral.reference_code}</p> : null}
                </li>
              ))}
            </ul>
            <div className={`${dataTable.scroll} hidden md:block`}>
              <table className={`${dataTable.table} min-w-[850px]`}>
                <caption className="sr-only">Call Slips</caption>
                <thead className={dataTable.head}><tr>
                  <th scope="col" className={dataTable.headerCell}>Student</th><th scope="col" className={dataTable.headerCell}>Course / Year</th><th scope="col" className={dataTable.headerCell}>Report</th><th scope="col" className={dataTable.headerCell}>Destination</th><th scope="col" className={dataTable.headerCell}>Issuer</th><th scope="col" className={dataTable.headerCell}>State</th><th scope="col" className={dataTable.headerCell}>Referral</th>
                </tr></thead>
                <tbody className={dataTable.body}>{items.map((slip) => (
                  <tr key={slip.id} className={dataTable.row}>
                    <th scope="row" className={`${dataTable.cell} font-normal`}><Link href={`/portal/call-slips/${slip.id}`} className="font-semibold text-brand underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">{slip.student_name_snapshot}</Link>{slip.student_institutional_id ? <span className="mt-1 block text-xs text-muted">{slip.student_institutional_id}</span> : null}</th>
                    <td className={`${dataTable.cell} text-ink`}>{slip.course_year_snapshot}</td><td className={`${dataTable.cell} text-ink`}>{formatInstitutionalDateTime(slip.report_at)}</td><td className={`${dataTable.cell} text-ink`}>{callSlipDestinationLabel(slip.destination_type, slip.other_destination)}</td><td className={`${dataTable.cell} text-ink`}>{slip.issued_by_name_snapshot}</td><td className={`${dataTable.cell} text-ink`}>{callSlipStateLabel(slip.state)}</td>
                    <td className={`${dataTable.cell} text-ink`}>{slip.referral ? referralAccess.canView ? <Link href={`/portal/referrals/${slip.referral.id}`} className="font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">{slip.referral.reference_code}</Link> : slip.referral.reference_code : <span className="text-muted">—</span>}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          </>
        )}
        {data ? <CanonicalPagination className="border-brand-line px-4 py-3 sm:px-5" page={data.page ?? filters.page} hasNext={data.has_next ?? false} onPageChange={(page) => router.push(operationalFiltersToUrl({ ...effectiveFilters, page }), { scroll: false })} label="Call Slip results" /> : null}
      </Panel>
    </div>
  );
}
