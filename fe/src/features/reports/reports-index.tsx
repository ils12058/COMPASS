"use client";

import Link from "next/link";

import { Skeleton } from "@/components/ui/skeleton";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { canAttemptReports } from "@/features/reports/reports-access";
import {
  isReportScopeDenied,
  ReportNavigation,
  ReportQueryError,
} from "@/features/reports/reports-shared";
import { useReportsGetScope } from "@/lib/api/generated/reports/reports";

export function ReportsIndex() {
  const { user } = usePortalSession();
  if (!canAttemptReports(user)) {
    return (
      <section className="max-w-2xl border-y border-border py-7">
        <h1 className="font-heading text-3xl font-bold text-ink">
          Reports unavailable
        </h1>
        <p className="mt-3 text-sm leading-6 text-muted">
          Your current access does not include Reports.
        </p>
      </section>
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
        <h1 className="font-heading text-3xl font-bold text-ink sm:text-4xl">
          Reports
        </h1>
        <div className="mt-7 space-y-4">
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
        </div>
        <p className="sr-only">Resolving your Reports scope…</p>
      </section>
    );
  }

  if (scopeQuery.isError) {
    if (isReportScopeDenied(scopeQuery.error)) {
      return (
        <section>
          <h1 className="font-heading text-3xl font-bold text-ink sm:text-4xl">
            Reports
          </h1>
          <p
            role="status"
            className="mt-6 border-y border-border py-5 text-sm leading-6 text-muted"
          >
            No active report scope is currently assigned to your account.
          </p>
        </section>
      );
    }
    return (
      <section>
        <h1 className="font-heading text-3xl font-bold text-ink sm:text-4xl">
          Reports
        </h1>
        <div className="mt-6">
          <ReportQueryError
            error={scopeQuery.error}
            fallback="Reports scope could not be resolved."
            onRetry={() => void scopeQuery.refetch()}
          />
        </div>
      </section>
    );
  }

  if (!scope || (!scope.is_global && scope.colleges.length === 0)) {
    return (
      <section>
        <h1 className="font-heading text-3xl font-bold text-ink sm:text-4xl">
          Reports
        </h1>
        <p
          role="status"
          className="mt-6 border-y border-border py-5 text-sm leading-6 text-muted"
        >
          No active report scope is currently assigned to your account.
        </p>
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
      <h1
        id="reports-heading"
        className="font-heading text-3xl font-bold text-ink sm:text-4xl"
      >
        Reports
      </h1>
      <ul className="mt-7 divide-y divide-border border-y border-border">
        {reportRows.map((report) => (
          <li key={report.href}>
            <Link
              href={report.href}
              className="group flex min-h-20 flex-wrap items-center justify-between gap-3 py-5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
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
    </section>
  );
}
