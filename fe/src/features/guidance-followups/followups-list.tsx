"use client";

import { useFollowupsFreshness, followupQueryFreshness } from "./followups-data";
import Link from "next/link";
import { useState } from "react";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { dataTable } from "@/components/ui/data-table";
import { FloatingListTools, ListToolField } from "@/components/ui/floating-list-tools";
import { FilterField } from "@/components/ui/filter-toolbar";
import { FollowupsHelp } from "./followups-help";
import { PageHeader } from "@/components/ui/page-header";
import { PageActionLink } from "@/components/ui/page-action";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { Select } from "@/components/ui/select";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { PersonAvatar } from "@/features/account/components/person-avatar";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { useGuidanceFollowupsList, useGuidanceFollowupsReport } from "@/lib/api/generated/guidance-followups/guidance-followups";
import { DueWindow, StatusValue, type FollowUpQuery } from "@/lib/api/generated/model";
import { formatInstitutionalDateTime } from "@/lib/institutional-time";
import { categoryLabel, statusLabel, followupAccess, FollowupRestricted, FollowupFailure } from "./followups-shared";

export function FollowupsList() {
  const { user } = usePortalSession();
  const access = followupAccess(user);
  useFollowupsFreshness(access.view);
  const [filters, setFilters] = useState<FollowUpQuery>({ status: StatusValue.PENDING, page: 1 });
  const query = useGuidanceFollowupsList(filters, { query: { ...followupQueryFreshness, enabled: access.view, refetchOnWindowFocus: "always" } });
  const report = useGuidanceFollowupsReport({ horizon_days: 7 }, { query: { ...followupQueryFreshness, enabled: access.view, retry: false } });
  const data = query.data?.data;
  const workload = report.data?.data;
  const workloadTotal = workload ? workload.pending + workload.completed + workload.cancelled : null;
  function change(next: Partial<FollowUpQuery>) { setFilters(previous => ({ ...previous, ...next, page: 1 })); }
  const activeFilterCount = Number(filters.status !== StatusValue.PENDING)
    + Number(Boolean(filters.due_window))
    + Number(Boolean(filters.assigned_to_id));
  const emptyTitle = activeFilterCount ? "No matching follow-ups" : workloadTotal === 0 ? "No follow-ups assigned" : workload?.pending === 0 ? "No Pending follow-ups" : "No follow-ups on this page";
  const emptyCopy = activeFilterCount ? "Change Status or open Filters to adjust the due date and responsibility filters." : workloadTotal === 0 ? "Follow-ups appear here when a next action is assigned to you." : workload?.pending === 0 ? "Choose another Status to review completed or cancelled work." : "Try another page or adjust the filters to find the Pending follow-up you need.";
  const hasActiveFilters = activeFilterCount > 0;
  function clearFilters() {
    setFilters(previous => ({
      ...previous,
      status: StatusValue.PENDING,
      due_window: undefined,
      assigned_to_id: undefined,
      page: 1,
    }));
  }
  if (!access.view) return <FollowupRestricted />;
  return <>
    <PageHeader help={<FollowupsHelp />} title="Follow-Ups" description="Track the next actions assigned to Guidance staff." actions={<>
      {access.manage ? <PageActionLink href="/portal/follow-ups/new" icon={Plus} label="Create" labelDetail="follow-up" /> : null}
    </>} />
    <section aria-labelledby="followup-workload-heading" className="mb-4">
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1">
        <h2 id="followup-workload-heading" className="text-sm font-semibold text-ink">Workload overview</h2>
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
          {access.manage ? <Link className="font-semibold text-brand underline underline-offset-4" href="/portal/follow-ups/reassignment">Recover assignments</Link> : null}
          <Link className="font-semibold text-brand underline underline-offset-4" href="/portal/follow-ups/report">Follow-Up report</Link>
        </div>
      </div>
      {report.isError ? <p role="alert" className="mt-2 text-sm text-muted">The workload overview could not be loaded. <Button variant="quiet" onClick={() => void report.refetch()}>Retry</Button></p> : workload ? <>
        <dl className="mt-2 flex flex-wrap gap-x-8 gap-y-2 border-y border-brand-line py-2">
          <div className="flex items-baseline gap-2"><dt>Pending</dt><dd className="font-semibold">{workload.pending}</dd></div>
          <div className="flex items-baseline gap-2"><dt>Overdue</dt><dd className="font-semibold">{workload.overdue}</dd></div>
          <div className="flex items-baseline gap-2"><dt>Due soon</dt><dd className="font-semibold">{workload.due_soon}</dd></div>
        </dl>
        <p className="mt-1 text-sm text-muted">Counts include only follow-ups you can currently access. Due soon means the next {workload.horizon_days} days.</p>
      </> : <p role="status" className="mt-2 text-sm text-muted">Loading workload overview…</p>}
    </section>
    <FloatingListTools
      compact
      label="Follow-up filters"
      filterCount={activeFilterCount}
      clear={hasActiveFilters ? (
        <Button type="button" variant="quiet" onClick={clearFilters}>Clear filters</Button>
      ) : undefined}
      filtersClassName="sm:grid-cols-2"
      filters={
        <>
          <fieldset className="grid min-w-0 content-start gap-2">
            <legend className="text-sm font-semibold text-ink">Progress &amp; timing</legend>
            <FilterField
              label="Due date"
              htmlFor="followup-due-filter"
              hint={<p id="followup-due-filter-hint" className="text-xs text-muted">For Pending follow-ups only.</p>}
            >
              <Select
                id="followup-due-filter"
                aria-describedby="followup-due-filter-hint"
                value={filters.due_window ?? ""}
                onChange={event => change({ due_window: event.target.value as DueWindow || undefined })}
              >
                <option value="">Any date</option>
                <option value="OVERDUE">Overdue</option>
                <option value="UPCOMING">Upcoming</option>
              </Select>
            </FilterField>
          </fieldset>
          <fieldset className="grid min-w-0 content-start gap-2">
            <legend className="text-sm font-semibold text-ink">Responsibility</legend>
            <FilterField label="Assignee" htmlFor="followup-assignee-filter">
              <Select
                id="followup-assignee-filter"
                value={filters.assigned_to_id ?? ""}
                onChange={event => change({ assigned_to_id: event.target.value || undefined })}
              >
                <option value="">All assignments available to me</option>
                <option value={user.id}>Assigned to me</option>
              </Select>
            </FilterField>
          </fieldset>
          <fieldset className="grid min-w-0 content-start gap-2 border-t border-brand-line pt-3 sm:col-span-2">
            <legend className="text-sm font-semibold text-ink">Display order</legend>
            <FilterField label="Sort by" htmlFor="followup-order">
              <Select
                id="followup-order"
                value={filters.ordering ?? "EARLIEST_DUE"}
                onChange={event => change({ ordering: event.target.value as FollowUpQuery["ordering"] })}
              >
                <option value="EARLIEST_DUE">Earliest due</option>
                <option value="LATEST_DUE">Latest due</option>
              </Select>
            </FilterField>
          </fieldset>
        </>
      }
    >
      <ListToolField label="Status" htmlFor="followup-status">
        <Select
          id="followup-status"
          className="h-10 min-h-10"
          value={filters.status ?? ""}
          aria-describedby="followup-status-description"
          onChange={event => change({ status: event.target.value as StatusValue || undefined, due_window: undefined })}
        >
          <option value="">All statuses</option>
          {Object.values(StatusValue).map(value => <option key={value} value={value}>{statusLabel(value)}</option>)}
        </Select>
      </ListToolField>
    </FloatingListTools>
    <span id="followup-status-description" className="sr-only">
      {filters.status === StatusValue.PENDING
        ? "Pending is the default status filter. Changing status updates the list immediately."
        : "The selected status filter is active and updates the list immediately."}
    </span>
    <Panel>
      <PanelHeader title="Follow-up tasks" context={data ? `${data.items.length} on this page` : "Loading…"} />
      {query.isPending ? <p role="status" className="p-5">Loading follow-ups…</p> : query.isError ? <FollowupFailure error={query.error} retry={() => void query.refetch()} /> : data ? <>
        {data.items.length ? <div className={dataTable.scroll}><table className={dataTable.table}><thead className={dataTable.head}><tr>{["Student", "Category", "Due", "Responsible staff member", "Status"].map(label => <th key={label} scope="col" className={dataTable.headerCell}>{label}</th>)}</tr></thead><tbody>{data.items.map(row => {
          const dueAt = Date.parse(row.due_at);
          const reportAt = workload ? Date.parse(workload.generated_at) : Number.NaN;
          const dueSoon = Boolean(workload && row.status === StatusValue.PENDING && !row.overdue && Number.isFinite(dueAt) && Number.isFinite(reportAt)
            && dueAt >= reportAt && dueAt <= reportAt + workload.horizon_days * 24 * 60 * 60 * 1000);
          return <tr key={row.id} className={dataTable.row}>
          <th scope="row" className={dataTable.cell}><span className="inline-flex items-center gap-2"><PersonAvatar displayName={row.student_name} photoUrl={row.student_profile_photo_url} photoUpdatedAt={row.student_profile_photo_updated_at} size="compact" /><Link className="font-semibold text-brand underline underline-offset-4" href={`/portal/follow-ups/${row.id}`}>{row.student_name}</Link></span></th>
          <td className={dataTable.cell}>{categoryLabel(row.category)}</td><td className={dataTable.cell}>{formatInstitutionalDateTime(row.due_at)}{row.overdue ? <span className="block font-semibold text-danger">Overdue</span> : dueSoon ? <span className="block font-semibold">Due soon</span> : null}</td><td className={dataTable.cell}><span className="inline-flex items-center gap-2"><PersonAvatar displayName={row.assigned_to_name} photoUrl={row.assigned_to_profile_photo_url} photoUpdatedAt={row.assigned_to_profile_photo_updated_at} size="compact" />{row.assigned_to_name}</span></td><td className={dataTable.cell}>{statusLabel(row.status)}</td>
        </tr>;
        })}</tbody></table></div> : <PanelMessage>
          <span className="font-semibold text-ink">{emptyTitle}.</span> {emptyCopy}
        </PanelMessage>}
        <div className="px-5"><CanonicalPagination page={data.page} hasNext={data.has_next} disabled={query.isFetching} onPageChange={page => setFilters(previous => ({ ...previous, page }))} /></div>
      </> : null}
    </Panel>
  </>;
}
