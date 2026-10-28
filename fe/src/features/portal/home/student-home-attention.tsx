import Link from "next/link";

import { Button, buttonVariants } from "@/components/ui/button";
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
        actions={<Link href="/portal/actions" className="inline-flex min-h-11 items-center rounded-sm text-sm font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">View all actions <span aria-hidden="true" className="ml-1">→</span></Link>}
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
            <li key={item.id} className="grid min-w-0 gap-3 px-4 py-4 @min-[38rem]:grid-cols-[minmax(0,1fr)_minmax(0,13rem)] @min-[38rem]:items-center sm:px-5">
              <div className="min-w-0" role={item.isError ? "alert" : undefined}>
                <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                  <h3 className="font-semibold text-ink">{item.title}</h3>
                  {item.priorityLabel ? <p className="text-sm font-semibold text-warning">{item.priorityLabel}</p> : null}
                </div>
                <p className="mt-1 text-sm leading-6 text-muted">{item.detail}</p>
              </div>
              <div className="flex min-w-0 flex-wrap items-center gap-2 @min-[38rem]:justify-end">
                <Link href={item.href} className={buttonVariants({ variant: "secondary", className: "h-auto min-h-11 min-w-0 max-w-full whitespace-normal text-left [overflow-wrap:anywhere]" })}>
                  {item.actionLabel}
                </Link>
                {item.onRetry ? <Button variant="secondary" onClick={item.onRetry}>Retry</Button> : null}
              </div>
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
