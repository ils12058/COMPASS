"use client";

import { TaskLink } from "@/components/ui/task-link";
import { GuardedPortalLink as Link } from "@/features/form-safety/guarded-portal-link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { Button } from "@/components/ui/button";
import { RowsSkeleton } from "@/components/ui/rows-skeleton";
import { Notice } from "@/components/ui/notice";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelMessage } from "@/components/ui/panel";
import { safeQueryData } from "@/features/freshness/query-freshness";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";
import { hasWorkQueue } from "@/features/work-queue/work-queue-access";
import { followupAccess } from "@/features/guidance-followups/followups-access";
import { withWorkflowReturn } from "@/features/portal/workflow-navigation";
import { useWorkQueue } from "@/features/work-queue/work-queue-data";
import { presentWork } from "@/features/work-queue/work-queue-presentation";
import { CompassApiError } from "@/lib/api/errors";
import type { UserSummary } from "@/lib/api/generated/model";

export function WorkQueueLoading() {
  return <><PageHeader title="My work" /><Panel><RowsSkeleton label="Loading your work…" framed={false} /></Panel></>;
}

export function WorkQueuePage() {
  const { user } = usePortalSession();
  if (!hasWorkQueue(user)) return <WorkspaceUnavailable title="My work">My work is available to Guidance staff.</WorkspaceUnavailable>;
  return <WorkList key={user.id} user={user} />;
}

function WorkList({ user }: { user: UserSummary }) {
  const pathname = usePathname();
  const params = useSearchParams();
  const router = useRouter();
  const requestedPage = Number(params.get("page") ?? 1);
  const page = Number.isInteger(requestedPage) && requestedPage >= 1 && requestedPage <= 100 ? requestedPage : 1;
  const here = `${pathname}${params.size ? `?${params}` : ""}`;
  function setPage(next: number) {
    const query = new URLSearchParams(params.toString());
    query.set("page", String(next));
    router.replace(`${pathname}?${query}`, { scroll: false });
  }
  const query = useWorkQueue(user, page);
  const data = safeQueryData(query)?.data;
  const forbidden = query.error instanceof CompassApiError && query.error.status === 403;
  return (
    <section aria-labelledby="my-work-heading" className="min-w-0">
      <PageHeader title="My work" headingId="my-work-heading" description="Work that needs your attention." />
      {user.capabilities.includes("counseling.continuity.request") && (user.role === "GUIDANCE_OFFICE_ASSISTANT" || user.designations.includes("HEAD_GUIDANCE_COUNSELOR")) ? <p className="mb-4 text-sm"><Link className="font-semibold text-brand underline underline-offset-4" href={withWorkflowReturn("/portal/counseling/continuity", here)}>Arrange case continuity</Link></p> : null}
      {followupAccess(user).view ? <p className="mb-4 text-sm"><Link className="font-semibold text-brand underline underline-offset-4" href={withWorkflowReturn("/portal/follow-ups", here)}>View all Follow-Ups</Link></p> : null}
      {query.isError && data ? <RefreshFailureNotice onRetry={() => void query.refetch()} retrying={query.isFetching} /> : null}
      <Panel>
        {query.isPending ? <PanelMessage role="status">Loading your work…</PanelMessage> : null}
        {query.isError && !data ? <Notice role="alert" tone="warning" action={<Button variant="secondary" onClick={() => void query.refetch()}>Retry</Button>}>
          {forbidden ? "You don't have access to My work." : "Couldn't load your work. Try again."}
        </Notice> : null}
        {data?.items.length === 0 ? <PanelMessage>{query.isError ? "Your last confirmed result had no work items." : data.page === 1 ? "You’re caught up." : "No items on this page. Return to the previous page to check your work."}</PanelMessage> : null}
        {data && data.items.length > 0 ? <ul className="divide-y divide-border">
          {data.items.map((item) => {
            const row = presentWork(item, data.generated_at);
            return <li key={item.id}><TaskLink href={row.href.startsWith("/portal/follow-ups/") ? withWorkflowReturn(row.href, here) : row.href} actionLabel={row.actionLabel} title={row.title} subject={item.student.display_name} detail={row.detail} /></li>;
          })}
        </ul> : null}
        {data && data.page < 100 ? <CanonicalPagination page={data.page} hasNext={data.has_next} disabled={query.isFetching} onPageChange={setPage} label="My work pages" className="px-4 sm:px-5" /> : null}
        {data?.page === 100 ? <div className="px-4 py-4 sm:px-5"><Button variant="secondary" disabled={query.isFetching} onClick={() => setPage(99)}>Previous</Button></div> : null}
        {data?.page === 100 && data.has_next ? <PanelMessage>More work remains. Check the relevant pages for items beyond this list.</PanelMessage> : null}
      </Panel>
    </section>
  );
}
