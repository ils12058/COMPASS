"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { Skeleton } from "@/components/ui/skeleton";
import { Notice } from "@/components/ui/notice";
import { RowsSkeleton } from "@/components/ui/rows-skeleton";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";
import { canAttemptReports } from "@/features/reports/reports-access";
import {
  parseGraduateTracerFilters,
} from "@/features/reports/report-filters";
import { GraduateTracerFilters } from "@/features/reports/graduate-tracer-filters";
import { GraduateTracerDownload } from "@/features/reports/graduate-tracer-download";
import { GraduateTracerReportContent } from "@/features/reports/graduate-tracer-report-content";
import {
  isReportScopeDenied,
  ReportNavigation,
  ReportQueryError,
  ReportsPageHeading,
  ReportStaleNotice,
} from "@/features/reports/reports-shared";
import {
  useReportsGetGraduateTracer,
  useReportsGetScope,
} from "@/lib/api/generated/reports/reports";
export function GraduateTracerReportPage() {
  const { user } = usePortalSession();
  if (!canAttemptReports(user)) {
    return (
      <WorkspaceUnavailable title="Graduate Tracer unavailable">
        You don’t have access to reports.
      </WorkspaceUnavailable>
    );
  }
  return <GraduateTracerReportWorkspace />;
}

function GraduateTracerReportWorkspace() {
  const searchParams = useSearchParams();
  const applied = parseGraduateTracerFilters(searchParams);
  const scopeQuery = useReportsGetScope({ query: { retry: false } });
  const scope = scopeQuery.data?.data;
  const scopeReady = Boolean(scope && (scope.is_global || scope.colleges.length > 0));
  const canQueryReport = Boolean(scopeReady && scope?.is_global && applied.valid);
  const reportQuery = useReportsGetGraduateTracer(applied.params, {
    query: {
      enabled: canQueryReport,
      retry: false,
    },
  });
  const report = canQueryReport ? reportQuery.data?.data : undefined;

  if (scopeQuery.isPending) {
    return (
      <section aria-label="Checking Graduate Tracer report access">
        <ReportsPageHeading title="Graduate Tracer" />
        <RowsSkeleton label="Checking your report access…" rows={2} framed />
      </section>
    );
  }
  if (scopeQuery.isError) {
    if (isReportScopeDenied(scopeQuery.error)) {
      return (
        <section>
          <ReportsPageHeading title="Graduate Tracer unavailable" />
         <Notice role="status">
           No reporting area is currently assigned to your account.
         </Notice>
        </section>
      );
    }
    return (
      <section>
        <ReportsPageHeading title="Graduate Tracer" />
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
        <ReportsPageHeading title="Graduate Tracer unavailable" />
       <Notice role="status">
         No reporting area is currently assigned to your account.
       </Notice>
      </section>
    );
  }
  if (!scope.is_global) {
    return (
      <section>
        <ReportNavigation current="graduate-tracer" showGraduateTracer={false} />
        <ReportsPageHeading title="Graduate Tracer unavailable" />
        <Notice
          action={
            <Link
              href="/portal/reports/student-profile"
              className="inline-flex min-h-10 items-center font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
            >
              Open Student Profiling
            </Link>
          }
        >
          Graduate Tracer reports are available only with institution-wide report access.
        </Notice>
      </section>
    );
  }

  return (
    <section aria-labelledby="graduate-tracer-heading">
      <ReportNavigation current="graduate-tracer" showGraduateTracer />
      <ReportsPageHeading
        title="Graduate Tracer"
        headingId="graduate-tracer-heading"
        actions={
          report ? (
            <GraduateTracerDownload
              key={JSON.stringify(applied.params)}
              params={applied.params}
            />
          ) : null
        }
      />

      <GraduateTracerFilters
        key={searchParams.toString()}
        initialDraft={applied.draft}
        initialErrors={applied.errors}
      />

      {canQueryReport && reportQuery.isError && report ? (
        <div className="mt-5">
          <ReportStaleNotice onRetry={() => void reportQuery.refetch()}>
            The report could not be refreshed. The last confirmed report remains visible.
          </ReportStaleNotice>
        </div>
      ) : null}
      {canQueryReport && reportQuery.isFetching && !reportQuery.isPending ? (
        <p role="status" className="mt-4 text-xs text-muted">
          Refreshing Graduate Tracer report…
        </p>
      ) : null}

      {reportQuery.isPending && applied.valid ? (
        <div className="mt-5 space-y-5" aria-busy="true"><span className="sr-only">Loading Graduate Tracer report…</span>
          <Skeleton className="h-28 w-full rounded-sm" />
          <Skeleton className="h-20 w-full rounded-sm" />
          <Skeleton className="h-52 w-full rounded-sm" />
          <p className="sr-only">Loading aggregate report sections…</p>
        </div>
      ) : null}
      {canQueryReport && reportQuery.isError && !report ? (
        <div className="mt-5">
          <ReportQueryError
            error={reportQuery.error}
            fallback="Graduate Tracer report could not be loaded."
            onRetry={() => void reportQuery.refetch()}
          />
        </div>
      ) : null}

      {report ? (
        <GraduateTracerReportContent
          report={report}
          isFetching={reportQuery.isFetching}
        />
      ) : null}
    </section>
  );
}
