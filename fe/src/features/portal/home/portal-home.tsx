"use client";

import { CalendarPlus } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { buttonVariants } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
import { pageSheetWidth } from "@/components/ui/page-width";
import { OverviewAnnouncements } from "@/features/portal/home/overview-announcements";
import { OverviewAttention } from "@/features/portal/home/overview-attention";
import { OverviewSummary } from "@/features/portal/home/overview-summary";
import {
  formatOverviewDate,
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

// The portal's home: a greeting, then what needs doing, then the account's announcements. Counts are
// context beside the work, not a row of tiles above it.
export function PortalHome() {
  const { user } = usePortalSession();
  const [now] = useState(() => new Date());
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
  // OverviewSummary renders nothing for an account without counts; then the work column is alone.
  const hasSummary =
    summaryQuery.isPending || summaryQuery.isError || metrics.length > 0 || emailStatus !== null;
  const roleContext = getOverviewRoleContext(user);

  return (
    <section aria-labelledby="portal-overview-heading" className={pageSheetWidth}>
      <PageHeader
        title={getOverviewGreeting(user, now)}
        headingId="portal-overview-heading"
        description={[formatOverviewDate(now), roleContext].filter(Boolean).join(" · ")}
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

      {/* What needs doing comes first, then announcements; the counts sit beside them on wide
          screens and after them on narrow ones. */}
      <div
        className={
          hasSummary
            ? "grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,20rem)]"
            : "grid gap-5"
        }
      >
        <div className="grid min-w-0 gap-5">
          <OverviewAttention data={attention} />
          <OverviewAnnouncements />
        </div>
        <OverviewSummary
          metrics={metrics}
          emailStatus={emailStatus}
          isPending={summaryQuery.isPending}
          isError={summaryQuery.isError}
          errorMessage={overviewErrorMessage(summaryQuery.error)}
          onRetry={() => void summaryQuery.refetch()}
        />
      </div>
    </section>
  );
}
