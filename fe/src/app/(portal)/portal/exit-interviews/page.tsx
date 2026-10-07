import type { Metadata } from "next";
import { Suspense } from "react";

import { ExitInterviewListSkeleton } from "@/features/exit-interviews/exit-interview-shared";
import { ExitInterviewWorkspacePage } from "@/features/exit-interviews/exit-interview-workspace-page";
import type { ExitInterviewOperationalFilters } from "@/features/exit-interviews/exit-interview-operational-list";
import type { ExitInterviewsListOpportunitiesParams } from "@/lib/api/generated/model";
import { ExitInterviewOrdering, ExitInterviewStatusValue } from "@/lib/api/generated/model";
import { readOrdering } from "@/features/portal/components/list-ordering-params";

type SearchValue = string | string[] | undefined;

function singleValue(value: SearchValue): string {
  return Array.isArray(value) ? value[0] ?? "" : value ?? "";
}

function positiveInteger(value: string): number | undefined {
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : undefined;
}

const UUID_PATTERN = /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i;

function pageNumber(value: string): number {
  return positiveInteger(value) ?? 1;
}

function pageSize(value: string): number | undefined {
  const parsed = positiveInteger(value);
  return parsed !== undefined && parsed <= 100 ? parsed : undefined;
}

export const metadata: Metadata = { title: "Exit Interviews" };

export default async function Page({
  searchParams,
}: {
  searchParams: Promise<Record<string, SearchValue>>;
}) {
  const query = await searchParams;
  const statusValue = singleValue(query.status);
  const academicYearValue = singleValue(query.academic_year_id);
  const filters: ExitInterviewOperationalFilters = {
    search: singleValue(query.search),
    status:
      statusValue === ExitInterviewStatusValue.DRAFT ||
      statusValue === ExitInterviewStatusValue.SUBMITTED
        ? statusValue
        : "",
    academicYearId: UUID_PATTERN.test(academicYearValue) ? academicYearValue : "",
    ordering: readOrdering(singleValue(query.ordering), ExitInterviewOrdering),
    page: pageNumber(singleValue(query.page)),
    pageSize: pageSize(singleValue(query.page_size)),
  };
  const opportunityStatus = singleValue(query.opportunity_status);
  const studentId = singleValue(query.student_id);
  const opportunities: ExitInterviewsListOpportunitiesParams | undefined = singleValue(query.workspace) === "opportunities" ? {
    search: filters.search || undefined,
    academic_year_id: filters.academicYearId || undefined,
    student_id: UUID_PATTERN.test(studentId) ? studentId : undefined,
    status: opportunityStatus === "OPEN" || opportunityStatus === "COMPLETED" || opportunityStatus === "REVOKED" ? opportunityStatus : undefined,
    page: filters.page, page_size: filters.pageSize,
  } : undefined;
  const notice = singleValue(query.notice) === "reopened" ? "reopened" : undefined;

  return (
    <Suspense fallback={<ExitInterviewListSkeleton />}>
      <ExitInterviewWorkspacePage
        key={JSON.stringify({ filters, opportunities })}
        filters={filters}
        notice={notice}
        opportunities={opportunities}
      />
    </Suspense>
  );
}
