"use client";

import Link from "next/link";
import { useState } from "react";
import { Plus, ChartColumn } from "lucide-react";
import { PageHeader } from "@/components/ui/page-header";
import { PageActionLink } from "@/components/ui/page-action";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { dataTable } from "@/components/ui/data-table";
import { FloatingListTools } from "@/components/ui/floating-list-tools";
import { FilterField } from "@/components/ui/filter-toolbar";
import { Select } from "@/components/ui/select";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { useGuidanceFollowupsList } from "@/lib/api/generated/guidance-followups/guidance-followups";
import { DueWindow, StatusValue, type FollowUpQuery } from "@/lib/api/generated/model";
import { formatInstitutionalDateTime } from "@/lib/institutional-time";
import { categoryLabel, statusLabel, followupAccess, FollowupRestricted, FollowupFailure } from "./followups-shared";

export function FollowupsList() {
  const { user } = usePortalSession();
  const access = followupAccess(user);
  const [filters, setFilters] = useState<FollowUpQuery>({ status: StatusValue.PENDING, page: 1 });
  const query = useGuidanceFollowupsList(filters, { query: { enabled: access.view, refetchOnWindowFocus: true } });
  const data = query.data?.data;
  function change(next: Partial<FollowUpQuery>) { setFilters(previous => ({ ...previous, ...next, page: 1 })); }
  if (!access.view) return <FollowupRestricted />;
  return <>
    <PageHeader title="Follow-Ups" description="Your assigned Guidance follow-ups. Due dates use Philippine Time." actions={<>
      {access.manage ? <PageActionLink href="/portal/follow-ups/new" icon={Plus} label="Create" labelDetail="follow-up" /> : null}
      <PageActionLink href="/portal/follow-ups/report" icon={ChartColumn} label="Report" variant="secondary" />
    </>} />
    <FloatingListTools compact label="Follow-up filters" filters={<>
      <FilterField label="Due date" htmlFor="followup-due-filter"><Select id="followup-due-filter" value={filters.due_window ?? ""} onChange={event => change({ due_window: event.target.value as DueWindow || undefined })}><option value="">Any date</option><option value="OVERDUE">Overdue</option><option value="UPCOMING">Upcoming</option></Select></FilterField>
      <FilterField label="Sort by" htmlFor="followup-order"><Select id="followup-order" value={filters.ordering ?? "EARLIEST_DUE"} onChange={event => change({ ordering: event.target.value as FollowUpQuery["ordering"] })}><option value="EARLIEST_DUE">Earliest due</option><option value="LATEST_DUE">Latest due</option></Select></FilterField>
      <FilterField label="Assignee" htmlFor="followup-assignee-filter"><Select id="followup-assignee-filter" value={filters.assigned_to_id ?? ""} onChange={event => change({ assigned_to_id: event.target.value || undefined })}><option value="">All assignments available to me</option><option value={user.id}>Assigned to me</option></Select></FilterField>
    </>} filterCount={Number(Boolean(filters.due_window)) + Number(Boolean(filters.assigned_to_id))}>
      <FilterField label="Status" htmlFor="followup-status"><Select id="followup-status" value={filters.status ?? ""} onChange={event => change({ status: event.target.value as StatusValue || undefined, due_window: undefined })}><option value="">All statuses</option>{Object.values(StatusValue).map(value => <option key={value} value={value}>{statusLabel(value)}</option>)}</Select></FilterField>
    </FloatingListTools>
    <Panel>
      <PanelHeader title="Follow-Ups" context={data ? `${data.items.length} on this page` : "Loading…"} />
      {query.isPending ? <p role="status" className="p-5">Loading follow-ups…</p> : query.isError ? <FollowupFailure error={query.error} retry={() => void query.refetch()} /> : data ? <>
        {data.items.length ? <div className={dataTable.scroll}><table className={dataTable.table}><thead className={dataTable.head}><tr>{["Student", "Category", "Due", "Assignee", "Status"].map(label => <th key={label} scope="col" className={dataTable.headerCell}>{label}</th>)}</tr></thead><tbody>{data.items.map(row => <tr key={row.id} className={dataTable.row}>
          <th scope="row" className={dataTable.cell}><Link className="font-semibold text-brand underline underline-offset-4" href={`/portal/follow-ups/${row.id}`}>{row.student_name}</Link></th>
          <td className={dataTable.cell}>{categoryLabel(row.category)}</td><td className={dataTable.cell}>{formatInstitutionalDateTime(row.due_at)}{row.overdue ? <span className="block font-semibold text-danger">Overdue</span> : null}</td><td className={dataTable.cell}>{row.assigned_to_name}</td><td className={dataTable.cell}>{statusLabel(row.status)}</td>
        </tr>)}</tbody></table></div> : <PanelMessage title="No follow-ups">No follow-ups match these filters.</PanelMessage>}
        <div className="px-5"><CanonicalPagination page={data.page} hasNext={data.has_next} disabled={query.isFetching} onPageChange={page => setFilters(previous => ({ ...previous, page }))} /></div>
      </> : null}
    </Panel>
  </>;
}
