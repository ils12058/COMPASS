"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { dataTable } from "@/components/ui/data-table";
import { FilterField } from "@/components/ui/filter-toolbar";
import { FloatingListTools, ListSearchField } from "@/components/ui/floating-list-tools";
import { Notice } from "@/components/ui/notice";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { Select } from "@/components/ui/select";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { describeResultPage } from "@/features/portal/components/result-context";
import { usePortalSession } from "@/features/portal/components/portal-session";
import {
  ExitInterviewListSkeleton,
  ExitInterviewError,
  ExitInterviewHeading,
  ExitInterviewStatus,
  exitInterviewErrorMessage,
  shouldHideExitInterviewCachedData,
} from "@/features/exit-interviews/exit-interview-shared";
import { formatExitInterviewDateTime } from "@/features/exit-interviews/exit-interview-presentation";
import { useAcademicYearsList } from "@/lib/api/generated/academic-years/academic-years";
import { useExitInterviewsList } from "@/lib/api/generated/exit-interviews/exit-interviews";
import { ExitInterviewStatusValue } from "@/lib/api/generated/model";
import type { ExitInterviewStatusValue as ExitInterviewStatusCode } from "@/lib/api/generated/model";

export type ExitInterviewOperationalFilters = {
  search: string;
  status: ExitInterviewStatusCode | "";
  academicYearId: string;
  page: number;
  pageSize?: number;
};

function pageHref(filters: ExitInterviewOperationalFilters, page: number): string {
  const params = new URLSearchParams();
  if (filters.search) params.set("search", filters.search);
  if (filters.status) params.set("status", filters.status);
  if (filters.academicYearId) params.set("academic_year_id", filters.academicYearId);
  if (filters.pageSize) params.set("page_size", String(filters.pageSize));
  if (page > 1) params.set("page", String(page));
  const query = params.toString();
  return query ? `/portal/exit-interviews?${query}` : "/portal/exit-interviews";
}

export function ExitInterviewOperationalList({
  filters,
  notice,
}: {
  filters: ExitInterviewOperationalFilters;
  notice?: "reopened";
}) {
  const router = useRouter();
  const { user } = usePortalSession();
  // Exit Interviews are annual, so reviewers narrow the queue by Academic Year.
  const canFilterYear = user.capabilities.includes("academic_years.view");
  const academicYears = useAcademicYearsList({
    query: { enabled: canFilterYear, retry: false, staleTime: 5 * 60_000 },
  });
  const years = academicYears.data?.data.items ?? [];
  const academicYearId = canFilterYear ? filters.academicYearId : "";
  const selectedYearKnown = years.some((year) => year.id === academicYearId);
  // Controlled so the applied year stays selected when the choices finish
  // loading; the page remounts this list whenever the applied filters change.
  const [yearChoice, setYearChoice] = useState(academicYearId);
  const params = {
    ...(filters.search ? { search: filters.search } : {}),
    ...(filters.status ? { status: filters.status } : {}),
    ...(academicYearId ? { academic_year_id: academicYearId } : {}),
    page: filters.page,
    ...(filters.pageSize ? { page_size: filters.pageSize } : {}),
  };
  const queue = useExitInterviewsList(params, { query: { retry: false } });
  const page = queue.data?.data;
  const hasFilters = Boolean(filters.search || filters.status || academicYearId);
  const hideStaleQueue =
    queue.isError && shouldHideExitInterviewCachedData(queue.error);

  const clearHref = pageHref({ ...filters, search: "", status: "", academicYearId: "" }, 1);

  return (
    <section className="space-y-5" aria-labelledby="exit-interview-operational-heading">
      <ExitInterviewHeading
        id="exit-interview-operational-heading"
        title="Exit Interviews"
        description="Draft answers are not shown here. Answers can be read once the Student submits."
      />
      {notice === "reopened" ? (
        <Notice role="status" tone="success">
          <span className="text-ink">The Exit Interview was reopened for Student correction.</span>
        </Notice>
      ) : null}

      <form
        action="/portal/exit-interviews"
        method="get"
        role="search"
        aria-label="Exit Interviews"
        key={JSON.stringify(filters)}
      >
        {filters.pageSize ? <input type="hidden" name="page_size" value={filters.pageSize} /> : null}
        <FloatingListTools
          submits
          filterCount={[filters.status, academicYearId].filter(Boolean).length}
          clear={hasFilters ? <Link href={clearHref} className={buttonVariants({ variant: "quiet" })}>Clear filters</Link> : undefined}
          filters={<>
          <FilterField label="Status" htmlFor="exit-interview-status">
            <Select id="exit-interview-status" name="status" defaultValue={filters.status}>
              <option value="">All statuses</option>
              <option value={ExitInterviewStatusValue.DRAFT}>Draft</option>
              <option value={ExitInterviewStatusValue.SUBMITTED}>Submitted</option>
            </Select>
          </FilterField>
          {canFilterYear ? (
            <FilterField
              label="Academic Year"
              htmlFor="exit-interview-year"
              hint={academicYears.isError ? (
                <p id="exit-interview-year-error" className="text-xs text-warning">Academic Year choices could not be loaded.</p>
              ) : null}
            >
              <Select
                id="exit-interview-year"
                name="academic_year_id"
                value={yearChoice}
                aria-describedby={academicYears.isError ? "exit-interview-year-error" : undefined}
                onChange={(event) => setYearChoice(event.target.value)}
              >
                <option value="">All Academic Years</option>
                {academicYearId && !selectedYearKnown ? (
                  <option value={academicYearId}>
                    {academicYears.isPending ? "Loading Academic Year…" : "Selected Academic Year"}
                  </option>
                ) : null}
                {years.map((year) => (
                  <option key={year.id} value={year.id}>
                    {year.label}{year.is_current ? " · Current" : ""}
                  </option>
                ))}
              </Select>
            </FilterField>
          ) : null}
          </>}
        >
          <ListSearchField
            id="exit-interview-search"
            name="search"
            label="Search Student name or Institutional ID"
            placeholder="Search Student name or Institutional ID"
            defaultValue={filters.search}
          />
        </FloatingListTools>
      </form>

      {queue.isError && page && !hideStaleQueue ? (
        <ExitInterviewError
          error={queue.error}
          fallback="The Exit Interview queue could not be refreshed. Showing the last confirmed results."
          onRetry={() => void queue.refetch()}
        />
      ) : null}

      <Panel aria-labelledby="exit-interview-queue-heading">
        <PanelHeader
          title="Exit Interview queue"
          titleId="exit-interview-queue-heading"
          context={queue.isFetching && !queue.isPending
            ? "Refreshing Exit Interview results…"
            : page && !queue.isError
              ? describeResultPage({
                  count: page.items.length,
                  page: page.page,
                  hasNext: page.has_next,
                  noun: { one: "Exit Interview", other: "Exit Interviews" },
                  filtered: hasFilters,
                })
              : null}
        />
        {queue.isPending ? (
          <ExitInterviewListSkeleton label="Loading Exit Interview queue…" framed={false} />
        ) : queue.isError && (!page || hideStaleQueue) ? (
          <PanelMessage role="alert" tone="danger" action={<Button variant="secondary" onClick={() => void queue.refetch()}>Retry</Button>}>
            {exitInterviewErrorMessage(queue.error, "The Exit Interview queue could not be loaded.")}
          </PanelMessage>
        ) : !page ? null : page.items.length === 0 && page.page > 1 ? (
          <PanelMessage
            action={
              <Button
                variant="secondary"
                onClick={() => router.push(pageHref({ ...filters, pageSize: page.page_size }, page.page - 1))}
              >
                Previous page
              </Button>
            }
          >
            No Exit Interviews are available on this page.
          </PanelMessage>
        ) : page.items.length === 0 ? (
          <PanelMessage action={hasFilters ? <Link href={clearHref} className={buttonVariants({ variant: "secondary" })}>Clear filters</Link> : undefined}>
            {hasFilters
              ? "No Exit Interviews match the current search or filters."
              : "No Exit Interviews have been started."}
          </PanelMessage>
        ) : (
          <>
            <div className={dataTable.scroll}>
              <table className={`${dataTable.table} min-w-[700px]`}>
                <caption className="sr-only">Head Guidance Exit Interview review queue</caption>
                <thead className={dataTable.head}>
                  <tr>
                    <th scope="col" className={`${dataTable.headerCell} ${dataTable.stickyHeaderCell} min-w-56`}>Student</th>
                    <th scope="col" className={dataTable.headerCell}>Academic Year</th>
                    <th scope="col" className={dataTable.headerCell}>Status</th>
                    <th scope="col" className={dataTable.headerCell}>Submitted</th>
                    <th scope="col" className={dataTable.headerCell}>Updated</th>
                  </tr>
                </thead>
                <tbody className={dataTable.body}>
                  {page.items.map((item) => {
                    const studentName = item.student_name || item.student.display_name;
                    return (
                      <tr key={item.id} className={dataTable.row}>
                        <th scope="row" className={`${dataTable.cell} ${dataTable.stickyCell} font-semibold text-ink`}>
                          {item.status === "SUBMITTED" ? (
                            <Link
                              href={`/portal/exit-interviews/${item.id}`}
                              className="text-brand underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                            >
                              {studentName}
                            </Link>
                          ) : (
                            <span>{studentName}</span>
                          )}
                          {item.student.institutional_id ? (
                            <span className="mt-1 block text-xs font-normal text-muted">{item.student.institutional_id}</span>
                          ) : null}
                        </th>
                        <td className={`${dataTable.cell} whitespace-nowrap text-muted`}>{item.academic_year.label}</td>
                        <td className={dataTable.cell}><ExitInterviewStatus status={item.status} /></td>
                        <td className={`${dataTable.cell} whitespace-nowrap text-muted`}>
                          {formatExitInterviewDateTime(item.last_submitted_at ?? item.first_submitted_at)}
                        </td>
                        <td className={`${dataTable.cell} whitespace-nowrap text-muted`}>{formatExitInterviewDateTime(item.updated_at)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <CanonicalPagination
              className="border-brand-line px-4 py-3 sm:px-5"
              page={page.page}
              hasNext={page.has_next}
              label="Exit Interview queue pages"
              onPageChange={(nextPage) => router.push(pageHref({ ...filters, pageSize: page.page_size }, nextPage))}
            />
          </>
        )}
      </Panel>
    </section>
  );
}
