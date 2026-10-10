"use client";

import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { DoorOpen } from "lucide-react";
import { Button, buttonVariants } from "@/components/ui/button";
import { PageAction } from "@/components/ui/page-action";
import { dataTable } from "@/components/ui/data-table";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { FloatingListTools, ListSearchField, ListToolField } from "@/components/ui/floating-list-tools";
import { Select } from "@/components/ui/select";
import { describeResultPage } from "@/features/portal/components/result-context";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { ExitInterviewHeading, ExitInterviewListSkeleton, exitInterviewErrorMessage, shouldHideExitInterviewCachedData } from "@/features/exit-interviews/exit-interview-shared";
import { ExitInterviewOpportunityOpening } from "@/features/exit-interviews/exit-interview-opportunity-opening";
import { ExitInterviewOpportunityDetails } from "@/features/exit-interviews/exit-interview-opportunity-details";
import { formatExitInterviewDateTime } from "@/features/exit-interviews/exit-interview-presentation";
import { useAcademicYearsList } from "@/lib/api/generated/academic-years/academic-years";
import { useExitInterviewsListOpportunities } from "@/lib/api/generated/exit-interviews/exit-interviews";
import type { ExitInterviewsListOpportunitiesParams } from "@/lib/api/generated/model";

export function ExitInterviewOpportunitiesPage({ filters }: { filters: ExitInterviewsListOpportunitiesParams }) {
  const router = useRouter();
  const { user } = usePortalSession();
  const [opening, setOpening] = useState(false);
  const [inspecting, setInspecting] = useState<string | null>(null);
  const canReadYears = user.capabilities.includes("academic_years.view");
  const years = useAcademicYearsList({ query: { enabled: canReadYears, retry: false } });
  const opportunities = useExitInterviewsListOpportunities(filters, { query: { retry: false } });
  const page = opportunities.data?.data;
  const filtered = Boolean(filters.search || filters.status || filters.academic_year_id || filters.student_id);
  const hideStale = opportunities.isError && shouldHideExitInterviewCachedData(opportunities.error);
  function href(nextPage: number) {
    const params = new URLSearchParams({ workspace: "opportunities", page: String(nextPage) });
    if (filters.search) params.set("search", filters.search);
    if (filters.status) params.set("opportunity_status", filters.status);
    if (filters.academic_year_id) params.set("academic_year_id", filters.academic_year_id);
    if (filters.student_id) params.set("student_id", filters.student_id);
    if (filters.page_size) params.set("page_size", String(filters.page_size));
    return `/portal/exit-interviews?${params}`;
  }
  return <section className="space-y-5">
    <ExitInterviewHeading id="exit-opportunities-heading" title="Exit Interview access" action={!opening ? <PageAction icon={DoorOpen} label="Open" labelDetail="Exit Interview access" onClick={() => setOpening(true)} /> : undefined} />
    {opening ? <ExitInterviewOpportunityOpening onDone={() => setOpening(false)} onOpened={() => void opportunities.refetch()} /> : null}
    {!opening ? <form action="/portal/exit-interviews" method="get" role="search" aria-label="Exit Interview access">
      <input type="hidden" name="workspace" value="opportunities" />
      {filters.student_id ? <input type="hidden" name="student_id" value={filters.student_id} /> : null}
      {filters.page_size ? <input type="hidden" name="page_size" value={filters.page_size} /> : null}
      <FloatingListTools submits filterCount={[filters.status, filters.academic_year_id, filters.student_id].filter(Boolean).length} clear={filters.search || filters.status || filters.academic_year_id || filters.student_id ? <Link href="/portal/exit-interviews?workspace=opportunities" className={buttonVariants({ variant: "quiet" })}>Clear filters</Link> : undefined} filters={<>
        <ListToolField label="Status" htmlFor="exit-opportunities-status"><Select id="exit-opportunities-status" name="opportunity_status" defaultValue={filters.status ?? ""}><option value="">All statuses</option><option value="OPEN">Open</option><option value="COMPLETED">Completed</option><option value="REVOKED">Revoked</option></Select></ListToolField>
        {canReadYears ? <ListToolField label="Academic Year" htmlFor="exit-opportunities-year"><Select id="exit-opportunities-year" name="academic_year_id" defaultValue={filters.academic_year_id ?? ""}><option value="">All Academic Years</option>{filters.academic_year_id && !years.data?.data.items.some((year) => year.id === filters.academic_year_id) ? <option value={filters.academic_year_id}>Selected Academic Year</option> : null}{(years.data?.data.items ?? []).map((year) => <option key={year.id} value={year.id}>{year.label}</option>)}</Select>{years.isError ? <p role="alert" className="mt-2 text-sm text-danger">Academic Years could not be loaded. <Button variant="quiet" onClick={() => void years.refetch()}>Retry</Button></p> : null}</ListToolField> : null}
      </>}><ListSearchField id="exit-opportunities-search" name="search" label="Search Student name or Institutional ID" defaultValue={filters.search ?? ""} /></FloatingListTools>
    </form> : null}
    <Panel><PanelHeader title="Results" context={opportunities.isFetching && !opportunities.isPending ? "Refreshing access…" : page && !opportunities.isError ? describeResultPage({ count: page.items.length, page: page.page, hasNext: page.has_next, noun: { one: "access record", other: "access records" }, filtered }) : null} />
      {opportunities.isPending ? <ExitInterviewListSkeleton label="Loading Exit Interview access…" framed={false} /> : opportunities.isError && (!page || hideStale) ? <PanelMessage role="alert" tone="danger" action={<Button variant="secondary" onClick={() => void opportunities.refetch()}>Retry</Button>}>{exitInterviewErrorMessage(opportunities.error, "Exit Interview access could not be loaded.")}</PanelMessage> : page ? <>
        {opportunities.isError ? <PanelMessage role="alert" tone="danger" action={<Button variant="secondary" onClick={() => void opportunities.refetch()}>Retry</Button>}>Access could not be refreshed. Showing the last confirmed records; actions are unavailable.</PanelMessage> : null}
        {page.items.length === 0 ? <PanelMessage>{page.page > 1 ? "No Exit Interview access records are available on this page." : filtered ? "No Exit Interview access records match the current search or filters." : "No Exit Interview access records have been opened."}</PanelMessage> : <div className={dataTable.scroll}><table className={`${dataTable.table} min-w-[650px]`}><caption className="sr-only">Exit Interview access</caption><thead className={dataTable.head}><tr>{["Student", "Academic Year", "Reason", "Status", "Workflow", "Opened", "Details"].map((label) => <th key={label} scope="col" className={dataTable.headerCell}>{label}</th>)}</tr></thead><tbody className={dataTable.body}>{page.items.map((item) => <tr key={item.id} className={dataTable.row}>
          <th scope="row" className={`${dataTable.cell} ${dataTable.stickyCell} text-left font-semibold`}>{item.student.display_name}<span className="mt-1 block text-xs font-normal text-muted">{item.student.institutional_id}</span></th>
          <td className={dataTable.cell}>{item.academic_year.label}</td><td className={dataTable.cell}>{item.source === "GRADUATION" ? "Graduation" : "Manual"}</td><td className={dataTable.cell}>{item.status === "OPEN" ? "Open" : item.status === "COMPLETED" ? "Completed" : "Revoked"}</td><td className={dataTable.cell}>{item.workflow_status === "SUBMITTED" ? "Submitted" : item.workflow_status === "DRAFT" ? "Draft" : "Not started"}</td><td className={dataTable.cell}>{formatExitInterviewDateTime(item.opened_at)}</td><td className={dataTable.cell}><Button variant="quiet" disabled={opportunities.isError} onClick={() => setInspecting(item.id)} aria-label={`Inspect Exit Interview access for ${item.student.display_name}`}>Inspect</Button></td>
        </tr>)}</tbody></table></div>}
        <CanonicalPagination page={page.page} hasNext={page.has_next} label="Exit Interview access pages" onPageChange={(next) => router.push(href(next))} className="px-4 py-3 sm:px-5" />
      </> : null}
    </Panel>
    {inspecting ? <ExitInterviewOpportunityDetails opportunityId={inspecting} onClose={() => setInspecting(null)} onChanged={() => void opportunities.refetch()} /> : null}
  </section>;
}
