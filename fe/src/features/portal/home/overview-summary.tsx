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
    <div className="border-t border-brand-line px-4 py-3.5 sm:px-5 [[data-panel-header]+&]:border-t-0">
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

// Counts are context beside the work: one compact list with the number at the end of each line,
// not a grid of tiles.
const countRow = "relative flex items-baseline justify-between gap-4 px-4 py-2.5 sm:px-5";

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
      <PanelHeader title="At a glance" titleId="overview-summary-heading" />

      {isPending ? (
        <div className="divide-y divide-border" aria-busy="true">
          {[0, 1, 2].map((item) => (
            <div key={item} className={countRow}>
              <Skeleton className="h-4 w-2/3" />
              <Skeleton className="h-4 w-6" />
            </div>
          ))}
          <p className="sr-only">Loading Overview summary counts…</p>
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
        <dl className="divide-y divide-border">
          {metrics.map((metric, index) => (
            // The label link stretches over the whole line, so the count is clickable too.
            <div
              key={metric.label + "-" + index}
              className={`${countRow} transition-colors has-[a:hover]:bg-surface-subtle`}
            >
              <dt className="min-w-0 text-sm leading-6 text-ink">
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
              <dd className="shrink-0 font-heading text-lg font-semibold tabular-nums text-ink">
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
