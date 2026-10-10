"use client";

import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelMessage } from "@/components/ui/panel";
import { safeQueryData } from "@/features/freshness/query-freshness";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";
import { hasWorkQueue } from "@/features/work-queue/work-queue-access";
import { useWorkQueue } from "@/features/work-queue/work-queue-data";
import { presentWork } from "@/features/work-queue/work-queue-presentation";
import { CompassApiError } from "@/lib/api/errors";
import type { UserSummary } from "@/lib/api/generated/model";

export function WorkQueuePage() {
  const { user } = usePortalSession();
  if (!hasWorkQueue(user)) return <WorkspaceUnavailable title="My work unavailable">My work is available to Guidance staff.</WorkspaceUnavailable>;
  return <WorkList key={user.id} user={user} />;
}

function WorkList({ user }: { user: UserSummary }) {
  const [page, setPage] = useState(1);
  const query = useWorkQueue(user, page);
  const data = safeQueryData(query)?.data;
  const forbidden = query.error instanceof CompassApiError && query.error.status === 403;
  return (
    <section aria-labelledby="my-work-heading" className="min-w-0">
      <PageHeader title="My work" headingId="my-work-heading" description="Work that needs your attention now. Open an item to act in its workspace." />
      {query.isError && data ? <RefreshFailureNotice onRetry={() => void query.refetch()} retrying={query.isFetching} /> : null}
      <Panel>
        {query.isPending ? <PanelMessage role="status">Loading your work…</PanelMessage> : null}
        {query.isError && !data ? <Notice role="alert" tone="warning" action={<Button variant="secondary" onClick={() => void query.refetch()}>Retry</Button>}>
          {forbidden ? "You don't have access to My work." : "Your work could not be loaded. Try again."}
        </Notice> : null}
        {data?.items.length === 0 ? <PanelMessage>{query.isError ? "Your last confirmed result had no work items." : data.page === 1 ? "You’re caught up." : "No items on this page. Return to the previous page to check your work."}</PanelMessage> : null}
        {data && data.items.length > 0 ? <ul className="divide-y divide-border">
          {data.items.map((item) => {
            const row = presentWork(item);
            return <li key={item.id} className="grid min-w-0 gap-3 px-4 py-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center sm:px-5">
              <div className="min-w-0 [overflow-wrap:anywhere]">
                <p className="font-semibold text-ink">{row.title}</p>
                <p className="mt-1 text-sm text-ink">{item.student.display_name}</p>
                <p className="mt-1 text-sm leading-6 text-muted">{row.detail}</p>
              </div>
              <Link href={row.href} className="inline-flex min-h-11 min-w-0 items-center rounded-sm text-sm font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus [overflow-wrap:anywhere]">{row.actionLabel} <span aria-hidden="true" className="ml-1">→</span></Link>
            </li>;
          })}
        </ul> : null}
        {data && data.page < 100 ? <CanonicalPagination page={data.page} hasNext={data.has_next} disabled={query.isFetching} onPageChange={setPage} label="My work pages" className="px-4 sm:px-5" /> : null}
        {data?.page === 100 ? <div className="px-4 py-4 sm:px-5"><Button variant="secondary" disabled={query.isFetching} onClick={() => setPage(99)}>Previous</Button></div> : null}
        {data?.page === 100 && data.has_next ? <PanelMessage>More work remains. Open the source workspaces to review items beyond this queue’s page limit.</PanelMessage> : null}
      </Panel>
    </section>
  );
}
