import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { OverviewAttentionData } from "@/features/portal/home/overview-work";

export function OverviewAttention({ data }: { data: OverviewAttentionData }) {
  if (!data.isVisible) return null;

  return (
    <section className="mt-8 border-t border-border pt-6" aria-labelledby="overview-attention-heading">
      <h2 id="overview-attention-heading" className="font-heading text-xl font-semibold text-ink">
        Needs your attention
      </h2>

      {data.staleNotices.map((notice) => (
        <p key={notice} role="status" className="mt-3 text-sm text-muted">
          {notice}
        </p>
      ))}

      {data.items.length > 0 ? (
        <ul className="mt-3 divide-y divide-border border-y border-border">
          {data.items.map((item) => (
            <li
              key={item.id}
              role={item.isError ? "alert" : undefined}
              className="grid gap-3 py-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center"
            >
              <div className="min-w-0">
                <p className="font-semibold text-ink">{item.title}</p>
                {item.subject ? <p className="mt-1 text-sm text-ink">{item.subject}</p> : null}
                <p className="mt-1 text-sm leading-6 text-muted">{item.detail}</p>
              </div>
              <div className="flex flex-wrap items-center gap-x-4 gap-y-2 sm:justify-end">
                <Link
                  href={item.href}
                  className="inline-flex min-h-10 items-center rounded-sm text-sm font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
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
            <li aria-busy="true" aria-hidden="true" className="space-y-2 py-4">
              <Skeleton className="h-4 w-44" />
              <Skeleton className="h-4 w-2/3" />
            </li>
          ) : null}
        </ul>
      ) : data.isPending ? (
        <div aria-busy="true" className="mt-3 space-y-3 border-y border-border py-4">
          <Skeleton className="h-4 w-44" />
          <Skeleton className="h-4 w-2/3" />
          <p className="sr-only">Checking for items that need attention…</p>
        </div>
      ) : (
        <p className="mt-3 border-y border-border py-4 text-sm text-muted">
          {data.emptyMessage}
        </p>
      )}
    </section>
  );
}
