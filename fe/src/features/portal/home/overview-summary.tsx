import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { OverviewMetric } from "@/features/portal/home/overview-presentation";

export function OverviewSummary({
  metrics,
  isPending,
  isError,
  errorMessage,
  onRetry,
}: {
  metrics: OverviewMetric[];
  isPending: boolean;
  isError: boolean;
  errorMessage: string;
  onRetry: () => void;
}) {
  if (!isPending && !isError && metrics.length === 0) return null;

  return (
    <section className="mt-8 border-t border-border pt-6" aria-labelledby="overview-summary-heading">
      <h2 id="overview-summary-heading" className="font-heading text-xl font-semibold text-ink">
        Summary
      </h2>

      {isPending ? (
        <div className="mt-4 grid grid-cols-1 gap-x-6 sm:grid-cols-2 xl:grid-cols-4" aria-busy="true">
          {[0, 1, 2, 3].map((item) => (
            <div key={item} className="border-b border-border py-4">
              <Skeleton className="h-4 w-2/3" />
              <Skeleton className="mt-3 h-8 w-12" />
            </div>
          ))}
          <p className="sr-only">Loading Overview summary metrics…</p>
        </div>
      ) : null}

      {isError && metrics.length === 0 ? (
        <div role="alert" className="mt-4 border-y border-danger/30 py-5">
          <p className="text-sm leading-6 text-danger">{errorMessage}</p>
          <Button className="mt-3" variant="secondary" onClick={onRetry}>
            Retry
          </Button>
        </div>
      ) : null}

      {isError && metrics.length > 0 ? (
        <p role="status" className="mt-3 text-sm text-muted">
          The summary could not be refreshed. Showing the last confirmed counts.
        </p>
      ) : null}

      {!isPending && metrics.length > 0 ? (
        <dl className="mt-4 grid grid-cols-1 border-y border-border sm:grid-cols-2 xl:grid-cols-4">
          {metrics.map((metric, index) => (
            <div
              key={metric.label + "-" + index}
              className="min-w-0 border-b border-border px-3 py-4 last:border-b-0 sm:px-5 xl:border-r xl:last:border-r-0"
            >
              <dt className="text-sm font-medium leading-5 text-muted">
                {metric.href ? (
                  <Link
                    href={metric.href}
                    className="rounded-sm hover:text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                  >
                    {metric.label}
                  </Link>
                ) : (
                  metric.label
                )}
              </dt>
              <dd className="mt-1 font-heading text-2xl font-semibold tabular-nums text-ink">
                {metric.value}
              </dd>
            </div>
          ))}
        </dl>
      ) : null}
    </section>
  );
}
