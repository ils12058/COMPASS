"use client";

import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { PageHeader } from "@/components/ui/page-header";
import { pageSheetWidth } from "@/components/ui/page-width";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { safeQueryData } from "@/features/freshness/query-freshness";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
import { hasGuidanceOperations } from "@/features/guidance-operations/guidance-operations-access";
import { useGuidanceOperations } from "@/features/guidance-operations/guidance-operations-data";
import { presentOperations, type OperationsMetric } from "@/features/guidance-operations/guidance-operations-presentation";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";
import { CompassApiError } from "@/lib/api/errors";
import type { UserSummary } from "@/lib/api/generated/model";
import { formatInstitutionalDateTime } from "@/lib/institutional-time";

const metricLink = "inline-flex min-h-11 min-w-0 items-center text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus rounded-sm";

export function GuidanceOperationsPage() {
  const { user } = usePortalSession();
  if (!hasGuidanceOperations(user)) return <WorkspaceUnavailable title="Guidance operations unavailable">Guidance operations is available to Guidance staff.</WorkspaceUnavailable>;
  return <OperationsSummary key={user.id} user={user} />;
}

function MetricList({ metrics, label }: { metrics: OperationsMetric[]; label: string }) {
  return <dl aria-label={label} className="divide-y divide-border">
    {metrics.map((metric) => <div key={metric.label} className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] items-start gap-x-4 px-4 py-3 sm:px-5">
      <dt className="min-w-0 text-sm font-semibold leading-6 [overflow-wrap:anywhere]">
        {metric.href ? <Link className={metricLink} href={metric.href}>{metric.label}</Link> : <span className="block py-2.5">{metric.label}</span>}
        {metric.oldest ? <span className="mt-0.5 block text-sm font-normal leading-6 text-muted">{metric.oldest.label}: <time dateTime={metric.oldest.instant}>{formatInstitutionalDateTime(metric.oldest.instant)}</time></span> : null}
      </dt>
      <dd className="py-2.5 text-base font-semibold tabular-nums text-ink">{metric.count.toLocaleString()}</dd>
    </div>)}
  </dl>;
}

function OperationsSummary({ user }: { user: UserSummary }) {
  const query = useGuidanceOperations(user);
  const data = safeQueryData(query)?.data;
  const forbidden = query.error instanceof CompassApiError && query.error.status === 403;
  const metrics = data ? presentOperations(data, user) : null;
  const empty = metrics && metrics.backlog.length > 0 && metrics.backlog.every((metric) => metric.count === 0);
  return <section aria-labelledby="guidance-operations-heading" className={`${pageSheetWidth} min-w-0`}>
    <PageHeader title="Guidance operations" headingId="guidance-operations-heading" description="Current operational workload and schedule within your authorized scope." />
    {query.isError && data ? <RefreshFailureNotice onRetry={() => void query.refetch()} retrying={query.isFetching} /> : null}
    {query.isPending || !data ? <Panel>
      {query.isPending ? <PanelMessage role="status">Loading Guidance operations…</PanelMessage> : null}
      {query.isError ? <Notice role="alert" tone="warning" action={<Button variant="secondary" disabled={query.isFetching} onClick={() => void query.refetch()}>Retry</Button>}>
        {forbidden ? "Your account can no longer open Guidance operations." : "Guidance operations could not be loaded. Try again."}
      </Notice> : null}
    </Panel> : null}
    {metrics && data ? <>
      <div className="grid min-w-0 items-start gap-5 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <Panel aria-labelledby="operations-backlog-heading">
          <PanelHeader title="Actionable backlog" titleId="operations-backlog-heading" />
          {metrics.backlog.length > 0 ? <MetricList metrics={metrics.backlog} label="Actionable backlog metrics" /> : <PanelMessage>No actionable workflows are available for your account.</PanelMessage>}
          {empty ? <PanelMessage>{query.isError ? "The last confirmed result showed no actionable backlog in the workflows available to you." : "No actionable backlog is currently waiting in the workflows available to you."}</PanelMessage> : null}
        </Panel>
        {metrics.schedule.length > 0 ? <Panel aria-labelledby="operations-schedule-heading">
          <PanelHeader title="Schedule" titleId="operations-schedule-heading" />
          <MetricList metrics={metrics.schedule} label="Schedule metrics" />
        </Panel> : null}
      </div>
      <div className="mt-4 flex min-w-0 flex-wrap items-center justify-between gap-x-5 gap-y-2">
        <Link href="/portal/work" className={`${metricLink} text-sm font-semibold`}>Open My work <span aria-hidden="true" className="ml-1">→</span></Link>
        <p className="text-sm leading-6 text-muted">{query.isError ? "Last confirmed" : "As of"} <time dateTime={data.generated_at}>{formatInstitutionalDateTime(data.generated_at)}</time> · Philippine Time</p>
      </div>
    </> : null}
  </section>;
}
