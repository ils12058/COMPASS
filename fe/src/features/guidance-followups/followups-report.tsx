"use client";
import { useFollowupsFreshness, followupQueryFreshness } from "./followups-data";
import Link from "next/link";
import { useState } from "react";
import { PageHeader, pageBackLinkClass } from "@/components/ui/page-header";
import { Panel, PanelSection } from "@/components/ui/panel";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { useGuidanceFollowupsReport } from "@/lib/api/generated/guidance-followups/guidance-followups";
import { formatInstitutionalDateTime, institutionalDateTimeInputToISO } from "@/lib/institutional-time";
import { categoryLabel, followupAccess, FollowupRestricted, FollowupFailure } from "./followups-shared";
export function FollowupsReport() {
  const { user } = usePortalSession();
  useFollowupsFreshness(followupAccess(user).view);
  const [start, setStart] = useState(""); const [end, setEnd] = useState("");
  const [horizon, setHorizon] = useState(7);
  const invalid = Boolean(start && end && start >= end);
  const query = useGuidanceFollowupsReport({ period_start: institutionalDateTimeInputToISO(start) || undefined, period_end: institutionalDateTimeInputToISO(end) || undefined, horizon_days: horizon }, { query: { ...followupQueryFreshness, enabled: followupAccess(user).view && !invalid, retry: false } });
  if (!followupAccess(user).view) return <FollowupRestricted />;
  const report = query.data?.data;
  return <><PageHeader title="Follow-Up report" description="Counts cover only follow-ups you can currently access. Descriptions and outcomes are excluded." back={<Link className={pageBackLinkClass} href="/portal/follow-ups">Back to Follow-Ups</Link>} /><Panel>
    <PanelSection title="Reporting period" titleId="followup-report-period"><div className="grid gap-4 sm:grid-cols-3"><div><Label htmlFor="followup-report-start">Completed from (Philippine Time)</Label><Input id="followup-report-start" type="datetime-local" value={start} onChange={event => setStart(event.target.value)} /></div><div><Label htmlFor="followup-report-end">Completed before (Philippine Time)</Label><Input id="followup-report-end" type="datetime-local" value={end} onChange={event => setEnd(event.target.value)} /></div><div><Label htmlFor="followup-report-horizon">Due soon window (days)</Label><Input id="followup-report-horizon" type="number" min={1} max={90} value={horizon} onChange={event => setHorizon(Number(event.target.value))} /></div></div>{invalid ? <p role="alert">Choose an end after the start.</p> : null}</PanelSection>
    {query.isPending ? <p role="status" className="p-5">Loading report…</p> : query.isError ? <FollowupFailure error={query.error} retry={() => void query.refetch()} /> : report && !invalid ? <>
      <PanelSection title="Workload" titleId="followup-report-workload"><dl className="grid gap-3 sm:grid-cols-2">{[["Pending", report.pending], ["Overdue", report.overdue], [`Due in the next ${report.horizon_days} days`, report.due_soon], ["Completed", report.completed], ["Cancelled", report.cancelled], ["Completed in selected period", report.completed_in_period]].map(([label, value]) => <div key={label} className="flex justify-between gap-4 border-b border-border py-2"><dt>{label}</dt><dd className="font-semibold">{value}</dd></div>)}</dl><p className="mt-3 text-sm text-muted">Period: {formatInstitutionalDateTime(report.period_start)} to {formatInstitutionalDateTime(report.period_end)}.</p></PanelSection>
      <PanelSection title="Categories" titleId="followup-report-categories"><dl>{report.categories.map(row => <div className="flex justify-between gap-4 border-b border-border py-2" key={row.category}><dt>{categoryLabel(row.category)}</dt><dd>{row.count}</dd></div>)}</dl></PanelSection>
    </> : null}
  </Panel></>;
}
