"use client";

import Link from "next/link";
import { useState } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelMessage } from "@/components/ui/panel";
import { safeQueryData } from "@/features/freshness/query-freshness";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";
import { hasStudentActions } from "@/features/student-actions/student-actions-access";
import { useStudentActions } from "@/features/student-actions/student-actions-data";
import { presentStudentAction } from "@/features/student-actions/student-actions-presentation";
import { CompassApiError } from "@/lib/api/errors";
import type { UserSummary } from "@/lib/api/generated/model";

export function StudentActionsPage() {
  const { user } = usePortalSession();
  if (!hasStudentActions(user)) return <WorkspaceUnavailable title="My actions unavailable">Only students can use My actions.</WorkspaceUnavailable>;
  return <ActionList key={user.id} user={user} />;
}

function ActionList({ user }: { user: UserSummary }) {
  const [page, setPage] = useState(1);
  const query = useStudentActions(user, page);
  const data = safeQueryData(query)?.data;
  const forbidden = query.error instanceof CompassApiError && query.error.status === 403;
  return (
    <section aria-labelledby="my-actions-heading" className="min-w-0">
      <PageHeader title="My actions" headingId="my-actions-heading" description="Tasks that need your attention." />
      {query.isError && data ? <RefreshFailureNotice onRetry={() => void query.refetch()} retrying={query.isFetching} /> : null}
      <Panel>
        {query.isPending ? <PanelMessage role="status">Loading your actions…</PanelMessage> : null}
        {query.isError && !data ? <Notice role="alert" tone="warning" action={<Button variant="secondary" onClick={() => void query.refetch()}>Retry</Button>}>
          {forbidden ? "You don't have access to My actions." : "Your actions could not be loaded. Try again."}
        </Notice> : null}
        {data?.items.length === 0 ? <PanelMessage>{query.isError ? "Your last confirmed result had no actions." : data.page === 1 ? "You're all caught up." : "No items on this page. Return to the previous page to check your actions."}</PanelMessage> : null}
        {data && data.items.length > 0 ? <ul className="divide-y divide-border">
          {data.items.map((item) => {
            const row = presentStudentAction(item);
            return <li key={item.id} className="grid min-w-0 gap-3 px-4 py-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center sm:px-5">
              <div className="min-w-0 [overflow-wrap:anywhere]">
                <p className="font-semibold text-ink">{row.title}</p>
                {row.priorityLabel ? <p className="mt-1 text-sm font-semibold text-warning">{row.priorityLabel}</p> : null}
                <p className="mt-1 text-sm leading-6 text-muted">{row.detail}</p>
                {row.timing ? <p className="mt-1 text-sm leading-6 text-muted">{row.timing}</p> : null}
              </div>
              <Link href={row.href} className={buttonVariants({ variant: "secondary", className: "min-h-11 h-auto min-w-0 whitespace-normal text-left [overflow-wrap:anywhere]" })}>{row.actionLabel} <span aria-hidden="true" className="ml-1">→</span></Link>
            </li>;
          })}
        </ul> : null}
        {data && data.page < 100 ? <CanonicalPagination page={data.page} hasNext={data.has_next} disabled={query.isFetching} onPageChange={setPage} label="My actions pages" className="px-4 sm:px-5" /> : null}
        {data?.page === 100 ? <div className="px-4 py-4 sm:px-5"><Button variant="secondary" disabled={query.isFetching} onClick={() => setPage(99)}>Previous</Button></div> : null}
        {data?.page === 100 && data.has_next ? <PanelMessage>More actions remain. Open the source workspaces to review items beyond this page limit.</PanelMessage> : null}
      </Panel>
    </section>
  );
}
