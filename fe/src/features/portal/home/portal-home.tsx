"use client";

import { CalendarPlus } from "lucide-react";
import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";
import { OverviewAnnouncements } from "@/features/portal/home/overview-announcements";
import { OverviewAttention } from "@/features/portal/home/overview-attention";
import { OverviewSummary } from "@/features/portal/home/overview-summary";
import {
  getEmailDeliveryStatus,
  getOverviewGreeting,
  getOverviewMetrics,
  getOverviewPrimaryAction,
  getOverviewRoleContext,
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
  const emailStatus = summary ? getEmailDeliveryStatus(summary, user) : null;
  const primaryAction = getOverviewPrimaryAction(user);
  // Some roles have nothing to act on here; then the context column takes the full width.
  const hasActionColumn = attention.isVisible;
  const greeting = getOverviewGreeting(user);
  const roleContext = getOverviewRoleContext(user);

  return (
    <section aria-labelledby="portal-overview-heading">
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-4">
        <div>
          <h1
            id="portal-overview-heading"
            className="font-heading text-3xl font-bold tracking-tight text-ink"
          >
            Overview
          </h1>
          {greeting ? <p className="mt-3 text-lg text-ink">{greeting}</p> : null}
          {roleContext ? <p className="mt-1 text-sm text-muted">{roleContext}</p> : null}
        </div>
        {primaryAction ? (
          <Link
            href={primaryAction.href}
            className={buttonVariants({ variant: "primary" })}
          >
            <CalendarPlus size={17} aria-hidden="true" />
            {primaryAction.label}
          </Link>
        ) : null}
      </div>

      {/* What needs doing comes first; counts and announcements are context. On wide screens they
          sit side by side. */}
      <div
        className={
          hasActionColumn ? "grid gap-x-10 xl:grid-cols-[minmax(0,1fr)_minmax(0,24rem)]" : undefined
        }
      >
        {hasActionColumn ? (
          <div className="min-w-0">
            <OverviewAttention data={attention} />
          </div>
        ) : null}
        <div className="min-w-0">
          <OverviewSummary
            metrics={metrics}
            emailStatus={emailStatus}
            isPending={summaryQuery.isPending}
            isError={summaryQuery.isError}
            errorMessage={overviewErrorMessage(summaryQuery.error)}
            onRetry={() => void summaryQuery.refetch()}
          />
          <OverviewAnnouncements />
        </div>
      </div>
    </section>
  );
}
