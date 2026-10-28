import { ClipboardList } from "lucide-react";
import { TaskLink } from "@/components/ui/task-link";
import { SectionLink } from "@/components/ui/section-link";

import { Button } from "@/components/ui/button";
import { LoadingRegion } from "@/components/ui/loading-region";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { Skeleton } from "@/components/ui/skeleton";
import type { OverviewAttentionData } from "@/features/portal/home/overview-work";

// Presentation of the existing first-five projection. The server supplies every row and its
// order. Only a successful empty read can establish that no current actions need attention.
export function StudentHomeAttention({ data }: { data: OverviewAttentionData }) {
  return (
    <Panel className="@container [overflow-wrap:anywhere]" aria-labelledby="overview-attention-heading">
      <PanelHeader
        title="Needs your attention"
        titleId="overview-attention-heading"
        actions={<SectionLink href="/portal/actions" label="All actions" accessibleLabel="View all actions" icon={ClipboardList} />}
      />

      {data.staleNotices.length > 0 ? (
        <div className="border-b border-border px-4 py-3 sm:px-5">
          {data.staleNotices.map((notice) => <p key={notice} role="status" className="text-sm leading-6 text-muted">{notice}</p>)}
          {data.retryActions ? <Button variant="secondary" className="mt-3" onClick={data.retryActions}>Retry</Button> : null}
        </div>
      ) : null}

      {data.isCaughtUp ? (
        <PanelMessage>You&apos;re all caught up. No current actions need your attention.</PanelMessage>
      ) : null}

      {data.items.length > 0 ? (
        <ul className="divide-y divide-border">
          {data.items.map((item) => (
            <li key={item.id} role={item.isError ? "alert" : undefined}>
              <TaskLink href={item.href} actionLabel={item.actionLabel} title={item.title} detail={item.detail} priority={item.priorityLabel} />
              {item.onRetry ? <div className="px-4 pb-3 sm:px-5"><Button variant="secondary" onClick={item.onRetry}>Retry</Button></div> : null}
            </li>
          ))}
        </ul>
      ) : null}

      {data.isPending ? (
        <LoadingRegion label="Checking your actions…" className="space-y-3 px-4 py-4 sm:px-5">
          <Skeleton className="h-5 w-2/3" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-1/2" />
        </LoadingRegion>
      ) : null}

      {!data.isPending && !data.isCaughtUp && data.items.length === 0 && data.staleNotices.length > 0 ? (
        <PanelMessage>Your last confirmed result had no actions.</PanelMessage>
      ) : null}
    </Panel>
  );
}
