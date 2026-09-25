import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { ExitInterviewWorkspacePage } from "@/features/exit-interviews/exit-interview-workspace-page";
import type { ExitInterviewOperationalFilters } from "@/features/exit-interviews/exit-interview-operational-list";
import { ExitInterviewStatusValue } from "@/lib/api/generated/model";

type SearchValue = string | string[] | undefined;

function singleValue(value: SearchValue): string {
  return Array.isArray(value) ? value[0] ?? "" : value ?? "";
}

function positiveInteger(value: string): number | undefined {
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : undefined;
}

function pageNumber(value: string): number {
  return positiveInteger(value) ?? 1;
}

function pageSize(value: string): number | undefined {
  const parsed = positiveInteger(value);
  return parsed !== undefined && parsed <= 100 ? parsed : undefined;
}

export default async function Page({
  searchParams,
}: {
  searchParams: Promise<Record<string, SearchValue>>;
}) {
  const query = await searchParams;
  const statusValue = singleValue(query.status);
  const filters: ExitInterviewOperationalFilters = {
    search: singleValue(query.search),
    status:
      statusValue === ExitInterviewStatusValue.DRAFT ||
      statusValue === ExitInterviewStatusValue.SUBMITTED
        ? statusValue
        : "",
    page: pageNumber(singleValue(query.page)),
    pageSize: pageSize(singleValue(query.page_size)),
  };
  const notice = singleValue(query.notice) === "reopened" ? "reopened" : undefined;

  return (
    <Suspense fallback={<Skeleton className="h-96 w-full" />}>
      <ExitInterviewWorkspacePage
        key={JSON.stringify(filters)}
        filters={filters}
        notice={notice}
      />
    </Suspense>
  );
}
