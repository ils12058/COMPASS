import Link from "next/link";

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
              className="grid gap-3 px-4 py-3.5 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center sm:px-5"
            >
              <div className="min-w-0 [overflow-wrap:anywhere]">
                <p className="font-semibold text-ink">{item.title}</p>
                {item.subject ? <p className="mt-0.5 text-sm text-ink">{item.subject}</p> : null}
                <p className="mt-0.5 text-sm leading-6 text-muted">{item.detail}</p>
              </div>
              <div className="flex flex-wrap items-center gap-x-4 gap-y-2 sm:justify-end">
                <Link
                  href={item.href}
                  className="inline-flex min-h-11 items-center rounded-sm text-sm font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                >
                  {item.actionLabel} <span aria-hidden="true" className="ml-1">→</span>
                </Link>
                {item.onRetry ? (
                  <Button variant="secondary" onClick={item.onRetry}>
                    Retry
                  </Button>
                ) : null}
              </div>
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
