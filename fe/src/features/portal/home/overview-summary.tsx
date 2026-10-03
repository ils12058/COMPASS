import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { Skeleton } from "@/components/ui/skeleton";
import type {
  EmailDeliveryStatus,
  OverviewMetric,
} from "@/features/portal/home/overview-presentation";

function EmailDeliveryLine({ status }: { status: EmailDeliveryStatus }) {
  return (
    <div className="border-t border-brand-line px-4 py-3.5 sm:px-5">
      <p className="text-sm font-semibold text-ink">Email delivery</p>
      <p className="mt-1 text-sm leading-6 text-muted">
        <span className={status.failed > 0 ? "font-semibold text-danger" : undefined}>
          {status.failed} failed
        </span>
        <span aria-hidden="true"> · </span>
        {status.pending} pending
        {status.duePending > 0 ? ` (${status.duePending} due for a delivery attempt)` : null}
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

// Counts are a compact grid inside one surface: lines between them, no separate tiles or icons.
const metricGrid = "grid grid-cols-2 gap-px bg-border";

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
    <Panel className="overflow-hidden" aria-labelledby="overview-summary-heading">
      <PanelHeader title="Summary" titleId="overview-summary-heading" />

      {isPending ? (
        <div className={metricGrid} aria-busy="true">
          {[0, 1, 2, 3].map((item) => (
            <div key={item} className="bg-surface-raised px-4 py-3.5 sm:px-5">
              <Skeleton className="h-4 w-2/3" />
              <Skeleton className="mt-3 h-7 w-12" />
            </div>
          ))}
          <p className="sr-only">Loading Overview summary metrics…</p>
        </div>
      ) : null}

      {isError && !hasContent ? (
        <PanelMessage
          role="alert"
          tone="danger"
          action={
            <Button variant="secondary" onClick={onRetry}>
              Retry
            </Button>
          }
        >
          {errorMessage}
        </PanelMessage>
      ) : null}

      {isError && hasContent ? (
        <p role="status" className="border-b border-border px-4 py-3 text-sm text-muted sm:px-5">
          The summary could not be refreshed. Showing the last confirmed counts.
        </p>
      ) : null}

      {!isPending && metrics.length > 0 ? (
        <dl className={metricGrid}>
          {metrics.map((metric, index) => (
            // The label link stretches over the whole cell, so the count is clickable too.
            <div
              key={metric.label + "-" + index}
              className="relative min-w-0 bg-surface-raised px-4 py-3.5 transition-colors last:odd:col-span-2 has-[a:hover]:bg-surface-subtle sm:px-5"
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
    </Panel>
  );
}
