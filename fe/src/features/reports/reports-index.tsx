"use client";

import { ClipboardList, GraduationCap, type LucideIcon } from "lucide-react";
import Link from "next/link";

import { Notice } from "@/components/ui/notice";
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

  const reportRows: { href: string; title: string; description: string; icon: LucideIcon }[] = [
    {
      href: "/portal/reports/student-profile",
      icon: ClipboardList,
      title: "Student Profiling",
      description:
        "Aggregate profile statistics from submitted Individual Inventories.",
    },
    ...(scope.is_global
      ? [
          {
            href: "/portal/reports/graduate-tracer",
            icon: GraduationCap,
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
      {/* Each report is its own product, so each is its own destination: side by side on wide
          screens, stacked on narrow ones. No counts or previews; the report pages hold the data. */}
      <ul className="grid max-w-4xl gap-4 md:grid-cols-2">
        {reportRows.map(({ href, title, description, icon: Icon }) => (
          <li key={href} className="flex">
            <Link
              href={href}
              className="group flex w-full items-start gap-3 rounded-sm border border-brand-line bg-surface-raised px-4 py-4 transition-colors hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus sm:px-5"
            >
              <Icon size={20} aria-hidden="true" className="mt-0.5 shrink-0 text-brand" />
              <span className="min-w-0 flex-1">
                <span className="block font-heading text-base font-semibold text-ink group-hover:underline">
                  {title}
                </span>
                <span className="mt-1 block text-sm leading-6 text-muted">{description}</span>
              </span>
              <span aria-hidden="true" className="mt-0.5 font-semibold text-brand">→</span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
