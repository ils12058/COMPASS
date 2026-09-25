"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { Skeleton } from "@/components/ui/skeleton";
import { usePortalSession } from "@/features/portal/components/portal-session";
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
      <section className="max-w-2xl border-y border-border py-7">
        <h1 className="font-heading text-3xl font-bold text-ink">
          Graduate Tracer unavailable
        </h1>
        <p className="mt-3 text-sm leading-6 text-muted">
          Your current access does not include Reports.
        </p>
      </section>
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
      <section aria-busy="true" aria-label="Resolving Graduate Tracer scope">
        <h1 className="font-heading text-3xl font-bold text-ink sm:text-4xl">
          Graduate Tracer
        </h1>
        <div className="mt-7 space-y-4">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-28 w-full" />
        </div>
        <p className="sr-only">Resolving your Reports scope…</p>
      </section>
    );
  }
  if (scopeQuery.isError) {
    if (isReportScopeDenied(scopeQuery.error)) {
      return (
        <section>
          <h1 className="font-heading text-3xl font-bold text-ink">
            Graduate Tracer unavailable
          </h1>
          <p role="status" className="mt-5 border-y border-border py-5 text-sm text-muted">
            No active report scope is currently assigned to your account.
          </p>
        </section>
      );
    }
    return (
      <section>
        <h1 className="font-heading text-3xl font-bold text-ink">
          Graduate Tracer
        </h1>
        <div className="mt-5">
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
        <h1 className="font-heading text-3xl font-bold text-ink">
          Graduate Tracer unavailable
        </h1>
        <p role="status" className="mt-5 border-y border-border py-5 text-sm text-muted">
          No active report scope is currently assigned to your account.
        </p>
      </section>
    );
  }
  if (!scope.is_global) {
    return (
      <section>
        <ReportNavigation current="graduate-tracer" showGraduateTracer={false} />
        <h1 className="font-heading text-3xl font-bold text-ink">
          Graduate Tracer unavailable
        </h1>
        <p className="mt-5 border-y border-border py-5 text-sm leading-6 text-muted">
          Graduate Tracer aggregate reporting requires institution-wide Reports scope.
        </p>
        <Link
          href="/portal/reports/student-profile"
          className="mt-4 inline-flex min-h-10 items-center font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
        >
          Open Student Profiling
        </Link>
      </section>
    );
  }

  return (
    <section aria-labelledby="graduate-tracer-heading">
      <ReportNavigation current="graduate-tracer" showGraduateTracer />
      <div className="flex flex-wrap items-start justify-between gap-4">
        <h1
          id="graduate-tracer-heading"
          className="font-heading text-3xl font-bold text-ink sm:text-4xl"
        >
          Graduate Tracer
        </h1>
        {report ? (
          <GraduateTracerDownload
            key={JSON.stringify(applied.params)}
            params={applied.params}
          />
        ) : null}
      </div>

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
        <div className="mt-7 space-y-5" aria-busy="true" aria-label="Loading Graduate Tracer report">
          <Skeleton className="h-28 w-full" />
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-52 w-full" />
          <p className="sr-only">Loading aggregate report sections…</p>
        </div>
      ) : null}
      {canQueryReport && reportQuery.isError && !report ? (
        <div className="mt-6">
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
