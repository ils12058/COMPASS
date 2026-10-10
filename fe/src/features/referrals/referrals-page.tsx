"use client";

import { NotebookPen } from "lucide-react";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { PageActionLink } from "@/components/ui/page-action";
import { Button, buttonVariants } from "@/components/ui/button";
import { dataTable } from "@/components/ui/data-table";
import { FormRevisionFilter } from "@/features/institutional-forms/form-revision-filter";
import { FilterField } from "@/components/ui/filter-toolbar";
import { FloatingListTools, ListSearchField } from "@/components/ui/floating-list-tools";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { SortField } from "@/components/ui/sort-field";
import { SortableColumnHeader } from "@/components/ui/sortable-column-header";
import { ReferralOrdering } from "@/lib/api/generated/model";
import { getReferralAccess } from "@/features/referrals/referrals-access";
import {
  ReferralAccessUnavailable,
  ReferralHeading,
  ReferralListSkeleton,
  referralErrorMessage, referralOrderingOptions } from "@/features/referrals/referrals-shared";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { useReferralsList } from "@/lib/api/generated/referrals/referrals";
import { formatDateOnly, formatInstitutionalDateTime } from "@/lib/institutional-time";

export type ReferralListFilters = {
  search: string;
  formRevisionId: string;
  fromDate: string;
  toDate: string;
  includeVoided: boolean;
  // A chosen order; absent means the newest referred first (ADR-090).
  ordering?: ReferralOrdering;
  page: number;
};

function filtersToUrl(filters: ReferralListFilters): string {
  const params = new URLSearchParams();
  if (filters.formRevisionId) params.set("form_revision_id", filters.formRevisionId);
  if (filters.search.trim()) params.set("search", filters.search.trim());
  if (filters.fromDate) params.set("from_date", filters.fromDate);
  if (filters.toDate) params.set("to_date", filters.toDate);
  if (filters.includeVoided) params.set("include_voided", "true");
  if (filters.ordering) params.set("ordering", filters.ordering);
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
      ...(filters.formRevisionId ? { form_revision_id: filters.formRevisionId } : {}),
      ...(filters.fromDate ? { from_date: filters.fromDate } : {}),
      ...(filters.toDate ? { to_date: filters.toDate } : {}),
      ...(filters.includeVoided ? { include_voided: true } : {}),
      ...(filters.ordering ? { ordering: filters.ordering } : {}),
      page: filters.page,
      page_size: 20,
    },
    { query: { enabled: access.canView, retry: false } },
  );

  if (!access.hasWorkspace) return <ReferralAccessUnavailable />;

  const data = referrals.data?.data;
  const items = data?.items ?? [];
  const filtered = Boolean(
    filters.formRevisionId || filters.search || filters.fromDate || filters.toDate || filters.includeVoided || filters.page > 1,
  );

  const advancedCount = [filters.formRevisionId, filters.fromDate, filters.toDate, filters.includeVoided].filter(Boolean).length;
  const draftRangeInvalid = Boolean(draft.fromDate && draft.toDate && draft.fromDate > draft.toDate);
  // The order the rows are in: the reader's choice, or the default the backend applied.
  const ordering = filters.ordering ?? data?.ordering;
  const setOrdering = (next: ReferralOrdering) =>
    router.push(filtersToUrl({ ...filters, ordering: next, page: 1 }), { scroll: false });
  // Clearing the filters keeps the chosen order; sorting is not a filter.
  const clearHref = filters.ordering ? `/portal/referrals?ordering=${filters.ordering}` : "/portal/referrals";

  function submitFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (draft.fromDate && draft.toDate && draft.fromDate > draft.toDate) return;
    router.push(filtersToUrl({ ...draft, page: 1 }), { scroll: false });
  }

  return (
    <div className="space-y-5">
      <ReferralHeading
        title="Referrals"
        action={access.canManage ? (
          <PageActionLink href="/portal/referrals/new" icon={NotebookPen} label="Record" labelDetail="referral" />
        ) : null}
      />

      <form onSubmit={submitFilters} role="search" aria-label="Referrals">
        <FloatingListTools
          submits
          invalid={draftRangeInvalid}
          filterCount={advancedCount}
          clear={filtered ? <Link href={clearHref} className={buttonVariants({ variant: "quiet" })}>Clear filters</Link> : undefined}
          filters={
            <>
          <FormRevisionFilter id="referrals-revision" selectedId={draft.formRevisionId} value={draft.formRevisionId} options={data?.filter_options.form_revisions} onChange={(event) => setDraft({ ...draft, formRevisionId: event.target.value })} />
          <FilterField label="From" htmlFor="referrals-from">
            <Input id="referrals-from" type="date" value={draft.fromDate} onChange={(event) => setDraft({ ...draft, fromDate: event.target.value })} />
          </FilterField>
          <FilterField label="To" htmlFor="referrals-to">
            <Input id="referrals-to" type="date" value={draft.toDate} onChange={(event) => setDraft({ ...draft, toDate: event.target.value })} />
          </FilterField>
          <div className="flex min-h-11 items-center gap-3 self-end">
            <input
              id="referrals-include-voided"
              className="h-4 w-4 accent-brand"
              type="checkbox"
              checked={draft.includeVoided}
              onChange={(event) => setDraft({ ...draft, includeVoided: event.target.checked })}
            />
            <Label htmlFor="referrals-include-voided">Include voided</Label>
          </div>
          {draftRangeInvalid ? (
            <p role="alert" className="text-sm text-danger sm:col-span-full">From date must not be after To date.</p>
          ) : null}
            </>
          }
        >
          <ListSearchField
            id="referrals-search"
            label="Search referrals"
            maxLength={160}
            placeholder="Search reference, Student name, or Institutional ID"
            value={draft.search}
            onChange={(event) => setDraft({ ...draft, search: event.target.value })}
          />
        </FloatingListTools>
      </form>

      <Panel aria-labelledby="referrals-results-heading">
        <PanelHeader
          title="Referrals"
          titleId="referrals-results-heading"
          actions={
            <SortField
              id="referrals-sort"
              value={ordering}
              options={referralOrderingOptions}
              onChange={setOrdering}
            />
          }
          context={data && items.length > 0 ? `Showing ${items.length} ${items.length === 1 ? "Referral" : "Referrals"} on page ${data.page}.` : null}
        />
        {referrals.isError ? (
          <PanelMessage role="alert" tone="danger" action={<Button variant="secondary" onClick={() => void referrals.refetch()}>Retry</Button>}>
            {referralErrorMessage(referrals.error, "Referrals could not be loaded.")}
          </PanelMessage>
        ) : referrals.isPending ? (
          <ReferralListSkeleton framed={false} />
        ) : items.length === 0 ? (
          <PanelMessage action={filtered ? <Link href={clearHref} className={buttonVariants({ variant: "secondary" })}>Clear filters</Link> : undefined}>
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
                    <SortableColumnHeader
                      label="Referral / Student"
                      ascending={ReferralOrdering.STUDENT_ASC}
                      descending={ReferralOrdering.STUDENT_DESC}
                      ascendingLabel="Student A–Z"
                      descendingLabel="Student Z–A"
                      current={ordering}
                      onSort={setOrdering}
                      className={dataTable.headerCell}
                    />
                    <th scope="col" className={dataTable.headerCell}>Course / Year / Block</th>
                    <SortableColumnHeader
                      label="Referred"
                      ascending={ReferralOrdering.OLDEST_REFERRED}
                      descending={ReferralOrdering.NEWEST_REFERRED}
                      ascendingLabel="Oldest referred first"
                      descendingLabel="Newest referred first"
                      firstDirection="descending"
                      current={ordering}
                      onSort={setOrdering}
                      className={dataTable.headerCell}
                    />
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
