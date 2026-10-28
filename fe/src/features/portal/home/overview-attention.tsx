import Link from "next/link";
import { TaskLink } from "@/components/ui/task-link";

import { Button } from "@/components/ui/button";
import { Panel, PanelHeader } from "@/components/ui/panel";
import { Skeleton } from "@/components/ui/skeleton";
import type { OverviewAttentionData } from "@/features/portal/home/overview-work";

export function OverviewAttention({ data }: { data: OverviewAttentionData }) {
  if (!data.isVisible) return null;

  return (
    <Panel aria-labelledby="overview-attention-heading">
      <PanelHeader title="Needs your attention" titleId="overview-attention-heading" />
      {data.viewAllWork ? <div className="border-b border-border px-4 sm:px-5"><Link href="/portal/work" className="inline-flex min-h-11 items-center text-sm font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">View all work</Link></div> : null}
      {data.viewAllActions ? <div className="border-b border-border px-4 sm:px-5"><Link href="/portal/actions" className="inline-flex min-h-11 items-center text-sm font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">View all actions</Link></div> : null}
      {data.isCaughtUp ? <p className="px-4 py-4 text-sm text-muted sm:px-5">{data.viewAllActions ? "You're all caught up." : "You’re caught up."}</p> : null}

      {data.staleNotices.map((notice) => (
        <p key={notice} role="status" className="border-b border-border px-4 py-3 text-sm text-muted sm:px-5">
          {notice}
        </p>
      ))}

      {data.items.length > 0 ? (
        <ul className="divide-y divide-border">
          {data.items.map((item) => (
            <li
              key={item.id}
              role={item.isError ? "alert" : undefined}
            >
              <TaskLink href={item.href} actionLabel={item.actionLabel} title={item.title} subject={item.subject} detail={item.detail} />
              {item.onRetry ? <div className="px-4 pb-3 sm:px-5"><Button variant="secondary" onClick={item.onRetry}>Retry</Button></div> : null}
            </li>
          ))}
          {data.isPending ? (
            <li aria-busy="true" aria-hidden="true" className="space-y-2 px-4 py-4 sm:px-5">
              <Skeleton className="h-4 w-44" />
              <Skeleton className="h-4 w-2/3" />
            </li>
          ) : null}
        </ul>
      ) : data.isPending ? (
        <div aria-busy="true" className="space-y-3 px-4 py-4 sm:px-5">
          <Skeleton className="h-4 w-44" />
          <Skeleton className="h-4 w-2/3" />
          <p className="sr-only">Checking for items that need attention…</p>
        </div>
      ) : null}
    </Panel>
  );
}
