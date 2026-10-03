"use client";

import { CalendarPlus } from "lucide-react";
import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
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
  // OverviewSummary renders nothing for an account without counts; then Announcements is alone.
  const hasSummary =
    summaryQuery.isPending || summaryQuery.isError || metrics.length > 0 || emailStatus !== null;
  const greeting = getOverviewGreeting(user);
  const roleContext = getOverviewRoleContext(user);

  return (
    <section aria-labelledby="portal-overview-heading">
      <PageHeader
        title="Overview"
        headingId="portal-overview-heading"
        description={greeting || roleContext ? (
          <>
            {greeting ? <span className="block text-base text-ink">{greeting}</span> : null}
            {roleContext ? <span className="block">{roleContext}</span> : null}
          </>
        ) : undefined}
        actions={primaryAction ? (
          <Link
            href={primaryAction.href}
            className={buttonVariants({ variant: "primary" })}
          >
            <CalendarPlus size={17} aria-hidden="true" />
            {primaryAction.label}
          </Link>
        ) : undefined}
      />

      {/* What needs doing comes first; counts and announcements are context. On wide screens they
          sit side by side. */}
      <div
        className={
          hasActionColumn
            ? "grid items-start gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,24rem)]"
            : hasSummary
              ? "grid items-start gap-5 lg:grid-cols-2"
              : "grid gap-5"
        }
      >
        {hasActionColumn ? <OverviewAttention data={attention} /> : null}
        <div className={hasActionColumn ? "grid min-w-0 gap-5" : "contents"}>
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
