import Link from "next/link";
import { Mail } from "lucide-react";
import { SectionLink } from "@/components/ui/section-link";

import { Button } from "@/components/ui/button";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { Skeleton } from "@/components/ui/skeleton";
import type {
  EmailDeliveryStatus,
  OverviewMetric,
} from "@/features/portal/home/overview-presentation";

function EmailDeliveryLine({ status }: { status: EmailDeliveryStatus }) {
  return (
    <div className="border-t border-border px-4 py-3.5 sm:px-5 [[data-panel-header]+&]:border-t-0">
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
        <SectionLink href={status.href} label="Delivery details" accessibleLabel="Open Email Delivery" icon={Mail} />
      ) : null}
    </div>
  );
}

// Counts are context beside the work: one compact list with the number at the end of each line,
// not a grid of tiles.
const countRow = "relative flex items-baseline justify-between min-h-11 gap-4 py-2.5";

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
    <Panel className="@container overflow-hidden border-border bg-surface-subtle" aria-labelledby="overview-summary-heading">
      <PanelHeader className="border-b-0 pb-1" title="At a glance" titleId="overview-summary-heading" />

      {isPending ? (
        <div className="divide-y divide-border px-4 sm:px-5" aria-busy="true">
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
        <dl className="grid gap-x-5 px-4 pb-2 @min-[24rem]:grid-cols-2 sm:px-5">
          {metrics.map((metric, index) => (
            // The label link stretches over the whole line, so the count is clickable too.
            <div
              key={metric.label + "-" + index}
              className={`${countRow} transition-colors has-[a:hover]:bg-surface-subtle`}
            >
              <dt className="min-w-0 [overflow-wrap:anywhere] text-sm leading-6 text-ink">
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
              <dd className="shrink-0 font-heading text-xl font-semibold tabular-nums text-ink">
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
