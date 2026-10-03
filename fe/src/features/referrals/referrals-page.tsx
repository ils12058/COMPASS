"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { dataTable } from "@/components/ui/data-table";
import { FilterField, FilterToolbar } from "@/components/ui/filter-toolbar";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { getReferralAccess } from "@/features/referrals/referrals-access";
import {
  ReferralAccessUnavailable,
  ReferralHeading,
  ReferralListSkeleton,
  referralErrorMessage,
} from "@/features/referrals/referrals-shared";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { useReferralsList } from "@/lib/api/generated/referrals/referrals";
import { formatDateOnly, formatInstitutionalDateTime } from "@/lib/institutional-time";

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
    <div className="space-y-5">
      <ReferralHeading
        title="Referrals"
        description="Record and review student referrals for your guidance area."
        action={access.canManage ? (
          <Link href="/portal/referrals/new" className={buttonVariants({ variant: "primary" })}>
            Record referral
          </Link>
        ) : null}
      />

      <form onSubmit={submitFilters} role="search" aria-label="Referrals">
        <FilterToolbar
          fieldsClassName="lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_minmax(0,1fr)]"
          actions={
            <>
              {filtered ? <Link href="/portal/referrals" className={buttonVariants({ variant: "quiet" })}>Clear filters</Link> : null}
              <Button type="submit">Apply filters</Button>
            </>
          }
        >
          <FilterField label="Search" htmlFor="referrals-search" className="sm:col-span-2 lg:col-span-1">
            <Input
              id="referrals-search"
              type="search"
              maxLength={160}
              placeholder="Search reference, Student name, or Institutional ID"
              value={draft.search}
              onChange={(event) => setDraft({ ...draft, search: event.target.value })}
            />
          </FilterField>
          <FilterField label="From" htmlFor="referrals-from">
            <Input id="referrals-from" type="date" value={draft.fromDate} onChange={(event) => setDraft({ ...draft, fromDate: event.target.value })} />
          </FilterField>
          <FilterField label="To" htmlFor="referrals-to">
            <Input id="referrals-to" type="date" value={draft.toDate} onChange={(event) => setDraft({ ...draft, toDate: event.target.value })} />
          </FilterField>
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
          {draft.fromDate && draft.toDate && draft.fromDate > draft.toDate ? (
            <p role="alert" className="text-sm text-danger sm:col-span-2 lg:col-span-3">From date must not be after To date.</p>
          ) : null}
        </FilterToolbar>
      </form>

      <Panel aria-labelledby="referrals-results-heading">
        <PanelHeader
          title="Referrals"
          titleId="referrals-results-heading"
          context={data && items.length > 0 ? `Showing ${items.length} ${items.length === 1 ? "Referral" : "Referrals"} on page ${data.page}.` : null}
        />
        {referrals.isError ? (
          <PanelMessage role="alert" tone="danger" action={<Button variant="secondary" onClick={() => void referrals.refetch()}>Retry</Button>}>
            {referralErrorMessage(referrals.error, "Referrals could not be loaded.")}
          </PanelMessage>
        ) : referrals.isPending ? (
          <ReferralListSkeleton framed={false} />
        ) : items.length === 0 ? (
          <PanelMessage action={filtered ? <Link href="/portal/referrals" className={buttonVariants({ variant: "secondary" })}>Clear filters</Link> : undefined}>
            {filtered ? "No referrals match these filters." : "No referrals have been recorded."}
          </PanelMessage>
        ) : (
          <>
            <ul className="divide-y divide-border md:hidden">
              {items.map((referral) => (
                <li key={referral.id} className="space-y-2 px-4 py-4">
                  <Link href={`/portal/referrals/${referral.id}`} className="font-semibold text-brand underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
                    {referral.reference_code}
                  </Link>
                  <p className="text-sm font-medium text-ink">{referral.student_name_snapshot}</p>
                  {referral.student.institutional_id ? <p className="text-xs text-muted">{referral.student.institutional_id}</p> : null}
                  <p className="text-sm text-muted">{referral.course_year_block_snapshot}</p>
                  <p className="text-sm text-muted">Referred {formatDateOnly(referral.referred_on)}{referral.received_at ? ` · Received ${formatInstitutionalDateTime(referral.received_at)}` : ""}</p>
                  {referral.status_note ? <p className="whitespace-pre-wrap break-words text-sm text-ink"><span className="font-semibold">Status note:</span> {referral.status_note}</p> : <p className="text-sm text-muted">No status note</p>}
                  {referral.voided_at ? <p className="text-sm font-semibold text-warning">Voided</p> : null}
                </li>
              ))}
            </ul>
            <div className={`${dataTable.scroll} hidden md:block`}>
              <table className={`${dataTable.table} min-w-[760px]`}>
                <caption className="sr-only">Referrals</caption>
                <thead className={dataTable.head}>
                  <tr>
                    <th scope="col" className={dataTable.headerCell}>Referral / Student</th>
                    <th scope="col" className={dataTable.headerCell}>Course / Year / Block</th>
                    <th scope="col" className={dataTable.headerCell}>Referred</th>
                    <th scope="col" className={dataTable.headerCell}>Received</th>
                    <th scope="col" className={dataTable.headerCell}>Status note</th>
                    {filters.includeVoided ? <th scope="col" className={dataTable.headerCell}>Record state</th> : null}
                  </tr>
                </thead>
                <tbody className={dataTable.body}>
                  {items.map((referral) => (
                    <tr key={referral.id} className={dataTable.row}>
                      <th scope="row" className={`${dataTable.cell} font-normal`}>
                        <Link href={`/portal/referrals/${referral.id}`} className="font-semibold text-brand underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">{referral.reference_code}</Link>
                        <span className="mt-1 block text-ink">{referral.student_name_snapshot}</span>
                        {referral.student.institutional_id ? <span className="mt-1 block text-xs text-muted">{referral.student.institutional_id}</span> : null}
                      </th>
                      <td className={`${dataTable.cell} text-ink`}>{referral.course_year_block_snapshot}</td>
                      <td className={`${dataTable.cell} text-ink`}>{formatDateOnly(referral.referred_on)}</td>
                      <td className={`${dataTable.cell} text-ink`}>{formatInstitutionalDateTime(referral.received_at)}</td>
                      <td className={`${dataTable.cell} max-w-64 text-ink`}>
                        {referral.status_note ? <p className="line-clamp-2 whitespace-pre-wrap">{referral.status_note}</p> : <span className="text-muted">—</span>}
                      </td>
                      {filters.includeVoided ? <td className={dataTable.cell}>{referral.voided_at ? <span className="font-semibold text-warning">Voided</span> : <span className="text-muted">—</span>}</td> : null}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
        {data && !referrals.isError ? (
              <CanonicalPagination
                className="border-brand-line px-4 py-3 sm:px-5"
                page={data.page ?? filters.page}
                hasNext={data.has_next ?? false}
                onPageChange={(page) => router.push(filtersToUrl({ ...filters, page }), { scroll: false })}
                label="Referral results"
              />
        ) : null}
      </Panel>
    </div>
  );
}
