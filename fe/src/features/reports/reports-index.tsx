"use client";

import Link from "next/link";

import { Notice } from "@/components/ui/notice";
import { Panel } from "@/components/ui/panel";
import { RowsSkeleton } from "@/components/ui/rows-skeleton";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";
import { canAttemptReports } from "@/features/reports/reports-access";
import {
  isReportScopeDenied,
  ReportNavigation,
  ReportQueryError,
  ReportsPageHeading,
} from "@/features/reports/reports-shared";
import { useReportsGetScope } from "@/lib/api/generated/reports/reports";

export function ReportsIndex() {
  const { user } = usePortalSession();
  if (!canAttemptReports(user)) {
    return (
      <WorkspaceUnavailable title="Reports unavailable">
        Reports are unavailable to this account.
      </WorkspaceUnavailable>
    );
  }

  return <ReportsIndexWorkspace />;
}

function ReportsIndexWorkspace() {
  const scopeQuery = useReportsGetScope({ query: { retry: false } });
  const scope = scopeQuery.data?.data;

  if (scopeQuery.isPending) {
    return (
      <section aria-busy="true" aria-label="Loading Reports">
        <ReportsPageHeading title="Reports" />
        <RowsSkeleton label="Checking your report access…" rows={2} framed />
      </section>
    );
  }

  if (scopeQuery.isError) {
    if (isReportScopeDenied(scopeQuery.error)) {
      return (
        <section>
          <ReportsPageHeading title="Reports" />
          <Notice role="status">
            No reporting area is currently assigned to your account.
          </Notice>
        </section>
      );
    }
    return (
      <section>
        <ReportsPageHeading title="Reports" />
        <ReportQueryError
          error={scopeQuery.error}
          fallback="Your report access could not be checked."
          onRetry={() => void scopeQuery.refetch()}
        />
      </section>
    );
  }

  if (!scope || (!scope.is_global && scope.colleges.length === 0)) {
    return (
      <section>
        <ReportsPageHeading title="Reports" />
        <Notice role="status">
          No reporting area is currently assigned to your account.
        </Notice>
      </section>
    );
  }

  const reportRows = [
    {
      href: "/portal/reports/student-profile",
      title: "Student Profiling",
      description:
        "Aggregate profile statistics from submitted Individual Inventories.",
    },
    ...(scope.is_global
      ? [
          {
            href: "/portal/reports/graduate-tracer",
            title: "Graduate Tracer",
            description:
              "Aggregate graduate outcome statistics from submitted Graduate Tracer responses.",
          },
        ]
      : []),
  ];

  return (
    <section aria-labelledby="reports-heading">
      <ReportNavigation current="index" showGraduateTracer={scope.is_global} />
      <ReportsPageHeading title="Reports" headingId="reports-heading" />
      <Panel as="div">
      <ul className="divide-y divide-border">
        {reportRows.map((report) => (
          <li key={report.href}>
            <Link
              href={report.href}
              className="group flex min-h-20 flex-wrap items-center justify-between gap-3 px-4 py-4 transition-colors first:rounded-t-sm hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-focus sm:px-5"
            >
              <span>
                <span className="block font-semibold text-ink group-hover:underline">
                  {report.title}
                </span>
                <span className="mt-1 block text-sm leading-6 text-muted">
                  {report.description}
                </span>
              </span>
              <span
                className="text-sm font-semibold text-brand"
                aria-hidden="true"
              >
                View report →
              </span>
            </Link>
          </li>
        ))}
      </ul>
      </Panel>
    </section>
  );
}
