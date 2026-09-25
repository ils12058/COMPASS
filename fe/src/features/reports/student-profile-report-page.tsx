"use client";

import { useSearchParams } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { usePortalSession } from "@/features/portal/components/portal-session";
import {
  parseStudentProfileFilters,
} from "@/features/reports/report-filters";
import { canAttemptReports } from "@/features/reports/reports-access";
import {
  isReportScopeDenied,
  ReportNavigation,
  ReportQueryError,
  ReportStaleNotice,
} from "@/features/reports/reports-shared";
import {
  StudentProfileFilters,
} from "@/features/reports/student-profile-filters";
import { StudentProfileDownloads } from "@/features/reports/student-profile-downloads";
import { StudentProfileReportContent } from "@/features/reports/student-profile-report-content";
import { useAcademicYearsList } from "@/lib/api/generated/academic-years/academic-years";
import {
  useReportsGetScope,
  useReportsGetStudentProfile,
} from "@/lib/api/generated/reports/reports";
import {
  useOrganizationListCampuses,
  useOrganizationListColleges,
  useOrganizationListPrograms,
} from "@/lib/api/generated/organization/organization";

export function StudentProfileReportPage() {
  const { user } = usePortalSession();
  if (!canAttemptReports(user)) {
    return (
      <section className="max-w-2xl border-y border-border py-7">
        <h1 className="font-heading text-3xl font-bold text-ink">
          Student Profiling unavailable
        </h1>
        <p className="mt-3 text-sm leading-6 text-muted">
          Your current access does not include Reports.
        </p>
      </section>
    );
  }
  return <StudentProfileReportWorkspace />;
}

function StudentProfileReportWorkspace() {
  const searchParams = useSearchParams();
  const applied = parseStudentProfileFilters(searchParams);
  const scopeQuery = useReportsGetScope({ query: { retry: false } });
  const scope = scopeQuery.data?.data;
  const scopeReady = Boolean(scope && (scope.is_global || scope.colleges.length > 0));

  const academicYearsQuery = useAcademicYearsList({
    query: { enabled: scopeReady, retry: false },
  });
  const campusesQuery = useOrganizationListCampuses(
    {},
    {
      query: {
        enabled: scope?.is_global === true,
        retry: false,
      },
    },
  );
  const collegesQuery = useOrganizationListColleges(
    {},
    {
      query: {
        enabled: scope?.is_global === true,
        retry: false,
      },
    },
  );

  const scopedCampuses = [
    ...new Map(
      (scope?.colleges ?? []).map((college) => [
        college.campus.id,
        college.campus,
      ]),
    ).values(),
  ];
  const campusChoices =
    scope?.is_global === true
      ? campusesQuery.data?.data.items ?? []
      : scopedCampuses;
  const collegeChoices =
    scope?.is_global === true
      ? collegesQuery.data?.data.items ?? []
      : scope?.colleges ?? [];
  const appliedCollege = collegeChoices.find(
    (college) => college.id === applied.params.college_id,
  );
  const appliedProgramsQuery = useOrganizationListPrograms(
    applied.params.college_id
      ? { college_id: applied.params.college_id }
      : {},
    {
      query: {
        enabled: Boolean(
          scopeReady &&
            applied.valid &&
            applied.params.program_id &&
            appliedCollege,
        ),
        retry: false,
      },
    },
  );

  let appliedFilterIssue: string | null = null;
  let appliedFilterPending = false;
  if (scopeReady && applied.valid) {
    if (applied.params.campus_id) {
      if (scope?.is_global && campusesQuery.isPending) {
        appliedFilterPending = true;
      } else if (
        scope?.is_global &&
        campusesQuery.isError &&
        !campusesQuery.data
      ) {
        appliedFilterIssue =
          "Campus choices could not be loaded to validate the applied report filter.";
      } else if (
        !campusChoices.some((campus) => campus.id === applied.params.campus_id)
      ) {
        appliedFilterIssue =
          "The applied Campus is not available in your Reports scope.";
      }
    }
    if (!appliedFilterIssue && applied.params.college_id) {
      if (scope?.is_global && collegesQuery.isPending) {
        appliedFilterPending = true;
      } else if (
        scope?.is_global &&
        collegesQuery.isError &&
        !collegesQuery.data
      ) {
        appliedFilterIssue =
          "College choices could not be loaded to validate the applied report filter.";
      } else if (!appliedCollege) {
        appliedFilterIssue =
          "The applied College is not available in your Reports scope.";
      } else if (
        applied.params.campus_id &&
        appliedCollege.campus.id !== applied.params.campus_id
      ) {
        appliedFilterIssue =
          "The applied College does not belong to the selected Campus.";
      }
    }
    if (!appliedFilterIssue && applied.params.program_id) {
      if (!applied.params.college_id) {
        appliedFilterIssue = "A Program filter requires a College filter.";
      } else if (appliedProgramsQuery.isPending) {
        appliedFilterPending = true;
      } else if (
        appliedProgramsQuery.isError &&
        !appliedProgramsQuery.data
      ) {
        appliedFilterIssue =
          "Program choices could not be loaded to validate the applied report filter.";
      } else if (
        !appliedProgramsQuery.data?.data.items.some(
          (program) =>
            program.id === applied.params.program_id &&
            program.college.id === applied.params.college_id,
        )
      ) {
        appliedFilterIssue =
          "The applied Program is not available in the selected College.";
      }
    }
  }

  const canQueryReport =
    scopeReady &&
    applied.valid &&
    !appliedFilterIssue &&
    !appliedFilterPending;
  const reportQuery = useReportsGetStudentProfile(applied.params, {
    query: { enabled: canQueryReport, retry: false },
  });
  const report = canQueryReport ? reportQuery.data?.data : undefined;

  if (scopeQuery.isPending) {
    return (
      <section aria-busy="true" aria-label="Resolving Student Profiling scope">
        <h1 className="font-heading text-3xl font-bold text-ink sm:text-4xl">
          Student Profiling
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
            Student Profiling unavailable
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
          Student Profiling
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
          Student Profiling unavailable
        </h1>
        <p role="status" className="mt-5 border-y border-border py-5 text-sm text-muted">
          No active report scope is currently assigned to your account.
        </p>
      </section>
    );
  }

  const academicYears = academicYearsQuery.data?.data.items ?? [];
  return (
    <section aria-labelledby="student-profile-heading">
      <ReportNavigation
        current="student-profile"
        showGraduateTracer={scope.is_global}
      />
      <div className="flex flex-wrap items-start justify-between gap-4">
        <h1
          id="student-profile-heading"
          className="font-heading text-3xl font-bold text-ink sm:text-4xl"
        >
          Student Profiling
        </h1>
        {report ? (
          <StudentProfileDownloads
            key={JSON.stringify({
              ...applied.params,
              academic_year_id: report.report_context.academic_year.id,
            })}
            params={{
              ...applied.params,
              academic_year_id: report.report_context.academic_year.id,
            }}
          />
        ) : null}
      </div>

      <StudentProfileFilters
        key={searchParams.toString()}
        scope={scope}
        initialDraft={applied.draft}
        initialErrors={applied.errors}
        academicYears={academicYears}
        academicYearsLoading={academicYearsQuery.isPending}
        academicYearsError={academicYearsQuery.isError && !academicYearsQuery.data}
        retryAcademicYears={() => void academicYearsQuery.refetch()}
        campuses={campusesQuery.data?.data.items ?? []}
        campusesLoading={scope.is_global && campusesQuery.isPending}
        campusesError={scope.is_global && campusesQuery.isError && !campusesQuery.data}
        retryCampuses={() => void campusesQuery.refetch()}
        colleges={collegesQuery.data?.data.items ?? []}
        collegesLoading={scope.is_global && collegesQuery.isPending}
        collegesError={scope.is_global && collegesQuery.isError && !collegesQuery.data}
        retryColleges={() => void collegesQuery.refetch()}
      />

      {appliedFilterIssue ? (
        <p role="alert" className="mt-5 border-y border-danger/30 py-4 text-sm leading-6 text-danger">
          {appliedFilterIssue}
          {appliedProgramsQuery.isError && !appliedProgramsQuery.data ? (
            <Button
              className="ml-3 min-h-8 px-2 text-xs"
              variant="secondary"
              onClick={() => void appliedProgramsQuery.refetch()}
            >
              Retry Program choices
            </Button>
          ) : null}
        </p>
      ) : appliedFilterPending ? (
        <p role="status" className="mt-5 text-sm text-muted">
          Validating the applied organization filters…
        </p>
      ) : null}

      {canQueryReport && reportQuery.isError && report ? (
        <div className="mt-5">
          <ReportStaleNotice onRetry={() => void reportQuery.refetch()}>
            The report could not be refreshed. The last confirmed report remains visible.
          </ReportStaleNotice>
        </div>
      ) : null}
      {canQueryReport && reportQuery.isFetching && !reportQuery.isPending ? (
        <p role="status" className="mt-4 text-xs text-muted">
          Refreshing Student Profiling report…
        </p>
      ) : null}

      {reportQuery.isPending && canQueryReport ? (
        <div className="mt-7 space-y-5" aria-busy="true"><span className="sr-only">Loading Student Profiling report…</span>
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
            fallback="Student Profiling report could not be loaded."
            onRetry={() => void reportQuery.refetch()}
          />
        </div>
      ) : null}

      {report ? (
        <StudentProfileReportContent
          report={report}
          isGlobal={scope.is_global}
          isFetching={reportQuery.isFetching}
        />
      ) : null}
    </section>
  );
}
