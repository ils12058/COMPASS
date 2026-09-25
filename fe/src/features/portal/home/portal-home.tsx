"use client";

import { OverviewAttention } from "@/features/portal/home/overview-attention";
import { OverviewQuickAccess } from "@/features/portal/home/overview-quick-access";
import { OverviewSummary } from "@/features/portal/home/overview-summary";
import { OverviewUpcoming } from "@/features/portal/home/overview-upcoming";
import {
  getOverviewGreeting,
  getOverviewMetrics,
  getOverviewQuickAccess,
  getOverviewRoleContext,
  getOverviewUpcomingItems,
} from "@/features/portal/home/overview-presentation";
import { useOverviewAttention } from "@/features/portal/home/overview-work";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { CompassApiError } from "@/lib/api/errors";
import { useOverviewGetSummary } from "@/lib/api/generated/overview/overview";

function isAuthorizationFailure(error: unknown): boolean {
  return error instanceof CompassApiError && (error.status === 401 || error.status === 403);
}

function overviewErrorMessage(error: unknown): string {
  if (error instanceof CompassApiError && error.status === 403) {
    return "Overview is not available for this account.";
  }
  return "The Overview summary could not be loaded. Try again in a moment.";
}

export function PortalHome() {
  const { user } = usePortalSession();
  const summaryQuery = useOverviewGetSummary({
    query: { retry: false },
  });
  const summary = isAuthorizationFailure(summaryQuery.error)
    ? undefined
    : summaryQuery.data?.data;
  const attention = useOverviewAttention(user, summary);
  const metrics = summary ? getOverviewMetrics(summary, user) : [];
  const upcoming = summary ? getOverviewUpcomingItems(summary, user) : [];
  const quickAccess = getOverviewQuickAccess(user);
  const greeting = getOverviewGreeting(user);
  const roleContext = getOverviewRoleContext(user);

  return (
    <section aria-labelledby="portal-overview-heading">
      <h1
        id="portal-overview-heading"
        className="font-heading text-3xl font-bold tracking-tight text-ink"
      >
        Overview
      </h1>
      {greeting ? <p className="mt-3 text-lg text-ink">{greeting}</p> : null}
      {roleContext ? <p className="mt-1 text-sm text-muted">{roleContext}</p> : null}

      <OverviewSummary
        metrics={metrics}
        isPending={summaryQuery.isPending}
        isError={summaryQuery.isError}
        errorMessage={overviewErrorMessage(summaryQuery.error)}
        onRetry={() => void summaryQuery.refetch()}
      />
      <OverviewAttention data={attention} />
      <OverviewUpcoming items={upcoming} />
      <OverviewQuickAccess links={quickAccess} />
    </section>
  );
}
