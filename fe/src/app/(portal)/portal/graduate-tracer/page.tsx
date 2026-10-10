import type { Metadata } from "next";
import { Suspense } from "react";

import { GraduateTracerStudentWorkspaceSkeleton } from "@/features/graduate-tracer/graduate-tracer-student-workspace";
import { GraduateTracerWorkspacePage } from "@/features/graduate-tracer/graduate-tracer-workspace-page";
import type { GraduateTracerOperationalFilters } from "@/features/graduate-tracer/graduate-tracer-operational-list";
import { GraduateTracerOrdering, GTSEmploymentStateValue } from "@/lib/api/generated/model";
import { readOrdering } from "@/features/portal/components/list-ordering-params";

type SearchValue = string | string[] | undefined;

function singleValue(value: SearchValue): string {
  return Array.isArray(value) ? value[0] ?? "" : value ?? "";
}

function positiveInteger(value: string): number | undefined {
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : undefined;
}

function pageSize(value: string): number | undefined {
  const parsed = positiveInteger(value);
  return parsed !== undefined && parsed <= 100 ? parsed : undefined;
}

function validCalendarDate(value: string): string {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return "";
  const parsed = new Date(`${value}T00:00:00.000Z`);
  return !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value ? value : "";
}

export const metadata: Metadata = { title: "Graduate Tracer" };

export default async function Page({
  searchParams,
}: {
  searchParams: Promise<Record<string, SearchValue>>;
}) {
  const query = await searchParams;
  const employmentValue = singleValue(query.current_employment_state);
  const filters: GraduateTracerOperationalFilters = {
    search: singleValue(query.search),
    submittedFrom: validCalendarDate(singleValue(query.submitted_from)),
    submittedTo: validCalendarDate(singleValue(query.submitted_to)),
    employmentState: Object.values(GTSEmploymentStateValue).find((value) => value === employmentValue) ?? "",
    ordering: readOrdering(singleValue(query.ordering), GraduateTracerOrdering),
    page: positiveInteger(singleValue(query.page)) ?? 1,
    pageSize: pageSize(singleValue(query.page_size)),
  };

  return (
    <Suspense fallback={<GraduateTracerStudentWorkspaceSkeleton />}>
      <GraduateTracerWorkspacePage key={JSON.stringify(filters)} filters={filters} />
    </Suspense>
  );
}
