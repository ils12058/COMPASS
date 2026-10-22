"use client";

import { CalendarPlus } from "lucide-react";
import { useEffect, useState } from "react";

import { PageActionLink } from "@/components/ui/page-action";
import { PageHeader } from "@/components/ui/page-header";
import { pageSheetWidth } from "@/components/ui/page-width";
import { OverviewAnnouncements } from "@/features/portal/home/overview-announcements";
import { OverviewAttention } from "@/features/portal/home/overview-attention";
import { OverviewSummary } from "@/features/portal/home/overview-summary";
import { CounselorHome } from "@/features/portal/home/counselor-home";
import { StudentHome } from "@/features/portal/home/student-home";
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

// Queries and primary commands remain shared. Student and Counselor Home branches change
// presentation only; source projections, summary metrics, and role access remain authoritative.
export function PortalHome() {
  const { user } = usePortalSession();
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    if (user.role !== "COUNSELOR") return;
    const interval = window.setInterval(() => setNow(new Date()), 60_000);
    return () => window.clearInterval(interval);
  }, [user.role]);
  const summaryQuery = useOverviewGetSummary({
    query: { retry: false },
  });
  const projectedSummary = isAuthorizationFailure(summaryQuery.error)
    ? undefined
    : summaryQuery.data?.data;
  // Student Home consumes only its own summary section, even if an unexpected response includes
  // professional sections. The backend still owns all counts and authorization.
  const summary = projectedSummary && user.role === "STUDENT"
    ? { ...projectedSummary, guidance: null, platform: null }
    : projectedSummary;
  const attention = useOverviewAttention(user, summary);
  const metrics = summary ? getOverviewMetrics(summary, user) : [];
  const emailStatus = summary ? getEmailDeliveryStatus(summary, user) : null;
  const primaryAction = getOverviewPrimaryAction(user);
  // OverviewSummary renders nothing for an account without counts; then the work column is alone.
  const hasSummary =
    summaryQuery.isPending || summaryQuery.isError || metrics.length > 0 || emailStatus !== null;
  const roleContext = getOverviewRoleContext(user);
  const summaryPanel = (
    <OverviewSummary
      metrics={metrics}
      emailStatus={emailStatus}
      isPending={summaryQuery.isPending}
      isError={summaryQuery.isError}
      errorMessage={overviewErrorMessage(summaryQuery.error)}
      onRetry={() => void summaryQuery.refetch()}
    />
  );

  return (
    <section aria-labelledby="portal-overview-heading" className={pageSheetWidth}>
      <PageHeader
        title={getOverviewGreeting(user, now)}
        headingId="portal-overview-heading"
        context={user.role === "STUDENT" ? "Overview" : undefined}
        description={[formatOverviewDate(now), roleContext].filter(Boolean).join(" · ")}
        actions={primaryAction ? (
          <PageActionLink
            href={primaryAction.href}
            icon={CalendarPlus}
            label={user.role === "STUDENT" ? "Book appointment" : primaryAction.shortLabel}
            labelDetail={user.role === "STUDENT" ? undefined : primaryAction.labelDetail}
          />
        ) : undefined}
      />

      {user.role === "STUDENT" ? (
        <StudentHome user={user} attention={attention} summary={summaryPanel} />
      ) : user.role === "COUNSELOR" ? (
        <CounselorHome user={user} attention={attention} summary={summaryPanel} now={now} />
      ) : (
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
          {summaryPanel}
        </div>
      )}
    </section>
  );
}
