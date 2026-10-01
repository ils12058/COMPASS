import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type {
  EmailDeliveryStatus,
  OverviewMetric,
} from "@/features/portal/home/overview-presentation";

function EmailDeliveryLine({ status }: { status: EmailDeliveryStatus }) {
  return (
    <div className="mt-4 border-y border-border py-4">
      <p className="text-sm font-semibold text-ink">Email delivery</p>
      <p className="mt-1 text-sm leading-6 text-muted">
        <span className={status.failed > 0 ? "font-semibold text-danger" : undefined}>
          {status.failed} failed
        </span>
        <span aria-hidden="true"> · </span>
        {status.pending} pending
        {status.duePending > 0 ? ` (${status.duePending} due now)` : null}
        <span aria-hidden="true"> · </span>
        {status.sentToday} sent today
      </p>
      {status.href ? (
        <Link
          href={status.href}
          className="mt-1 inline-flex min-h-10 items-center rounded-sm text-sm font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
        >
          Open Email Delivery <span aria-hidden="true" className="ml-1">→</span>
        </Link>
      ) : null}
    </div>
  );
}

export function OverviewSummary({
  metrics,
  emailStatus,
  isPending,
  isError,
  errorMessage,
  onRetry,
}: {
  metrics: OverviewMetric[];
  emailStatus: EmailDeliveryStatus | null;
  isPending: boolean;
  isError: boolean;
  errorMessage: string;
  onRetry: () => void;
}) {
  const hasContent = metrics.length > 0 || emailStatus !== null;
  if (!isPending && !isError && !hasContent) return null;

  return (
    <section className="mt-8 border-t border-border pt-6" aria-labelledby="overview-summary-heading">
      <h2 id="overview-summary-heading" className="font-heading text-xl font-semibold text-ink">
        Summary
      </h2>

      {isPending ? (
        <div className="mt-4 grid grid-cols-2 border-l border-t border-border" aria-busy="true">
          {[0, 1, 2, 3].map((item) => (
            <div key={item} className="border-b border-r border-border px-4 py-4">
              <Skeleton className="h-4 w-2/3" />
              <Skeleton className="mt-3 h-8 w-12" />
            </div>
          ))}
          <p className="sr-only">Loading Overview summary metrics…</p>
        </div>
      ) : null}

      {isError && !hasContent ? (
        <div role="alert" className="mt-4 border-y border-danger/30 py-5">
          <p className="text-sm leading-6 text-danger">{errorMessage}</p>
          <Button className="mt-3" variant="secondary" onClick={onRetry}>
            Retry
          </Button>
        </div>
      ) : null}

      {isError && hasContent ? (
        <p role="status" className="mt-3 text-sm text-muted">
          The summary could not be refreshed. Showing the last confirmed counts.
        </p>
      ) : null}

      {!isPending && metrics.length > 0 ? (
        <dl className="mt-4 grid grid-cols-2 border-l border-t border-border">
          {metrics.map((metric, index) => (
            // The label link stretches over the whole tile, so the count is clickable too.
            <div
              key={metric.label + "-" + index}
              className="relative min-w-0 border-b border-r border-border px-4 py-4 transition-colors last:odd:col-span-2 has-[a:hover]:bg-surface-muted"
            >
              <dt className="text-sm font-medium leading-5 text-muted">
                {metric.href ? (
                  <Link
                    href={metric.href}
                    className="after:absolute after:inset-0 hover:text-brand focus-visible:outline-none focus-visible:after:ring-2 focus-visible:after:ring-inset focus-visible:after:ring-focus"
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

      {!isPending && emailStatus ? <EmailDeliveryLine status={emailStatus} /> : null}
    </section>
  );
}
