"use client";

import { useSearchParams } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Notice } from "@/components/ui/notice";
import { RowsSkeleton } from "@/components/ui/rows-skeleton";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";
import {
  parseStudentProfileFilters,
} from "@/features/reports/report-filters";
import { canAttemptReports } from "@/features/reports/reports-access";
import {
  isReportScopeDenied,
  ReportNavigation,
  ReportQueryError,
  ReportsPageHeading,
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
      <WorkspaceUnavailable title="Student Profiling unavailable">
        Reports are unavailable to this account.
      </WorkspaceUnavailable>
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
          "Campus choices could not be loaded. Retry before applying the report filters.";
      } else if (
        !campusChoices.some((campus) => campus.id === applied.params.campus_id)
      ) {
        appliedFilterIssue =
          "The selected campus is unavailable for your reporting area.";
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
          "College choices could not be loaded. Retry before applying the report filters.";
      } else if (!appliedCollege) {
        appliedFilterIssue =
          "The selected college is unavailable for your reporting area.";
      } else if (
        applied.params.campus_id &&
        appliedCollege.campus.id !== applied.params.campus_id
      ) {
        appliedFilterIssue =
          "The selected college does not belong to the selected campus.";
      }
    }
    if (!appliedFilterIssue && applied.params.program_id) {
      if (!applied.params.college_id) {
        appliedFilterIssue = "Choose a college before choosing a program.";
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
      <section aria-label="Checking Student Profiling access">
        <ReportsPageHeading title="Student Profiling" />
        <RowsSkeleton label="Checking your report access…" rows={2} framed />
      </section>
    );
  }
  if (scopeQuery.isError) {
    if (isReportScopeDenied(scopeQuery.error)) {
      return (
        <section>
          <ReportsPageHeading title="Student Profiling unavailable" />
         <Notice role="status">
           No reporting area is currently assigned to your account.
         </Notice>
        </section>
      );
    }
    return (
      <section>
        <ReportsPageHeading title="Student Profiling" />
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
        <ReportsPageHeading title="Student Profiling unavailable" />
       <Notice role="status">
         No reporting area is currently assigned to your account.
       </Notice>
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
      <ReportsPageHeading
        title="Student Profiling"
        headingId="student-profile-heading"
        actions={
          report ? (
          <StudentProfileDownloads
            academicYearLabel={report.report_context.academic_year.label}
            key={JSON.stringify({
              ...applied.params,
              academic_year_id: report.report_context.academic_year.id,
            })}
            params={{
              ...applied.params,
              academic_year_id: report.report_context.academic_year.id,
            }}
          />
          ) : null
        }
      />

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
        <Notice
          role="alert"
          tone="danger"
          className="mt-5"
          action={
            appliedProgramsQuery.isError && !appliedProgramsQuery.data ? (
              <Button
                variant="secondary"
                onClick={() => void appliedProgramsQuery.refetch()}
              >
                Retry Program choices
              </Button>
            ) : undefined
          }
        >
          {appliedFilterIssue}
        </Notice>
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
        <div className="mt-5 space-y-5" aria-busy="true"><span className="sr-only">Loading Student Profiling report…</span>
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
