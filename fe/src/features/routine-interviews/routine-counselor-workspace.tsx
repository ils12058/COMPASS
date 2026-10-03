"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { dataTable } from "@/components/ui/data-table";
import { FilterField, FilterToolbar } from "@/components/ui/filter-toolbar";
import { Input } from "@/components/ui/input";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { Select } from "@/components/ui/select";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { describeResultPage } from "@/features/portal/components/result-context";
import type { RoutineInterviewAccess } from "@/features/routine-interviews/routine-interviews-access";
import { RoutineDirectCreateDialog } from "@/features/routine-interviews/routine-direct-create-dialog";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import {
  formatRoutineDateTime,
  formatRoutineDateTimeRange,
  routineDeliveryModeLabel,
  routineEntryModeLabel,
  routineErrorMessage,
  routineEvaluationStatusLabel,
  routineIntakeStatusLabel,
  RoutineInterviewListSkeleton,
  RoutinePageHeading,
  RoutineStatus,
} from "@/features/routine-interviews/routine-interviews-shared";
import {
  DeliveryMode,
  RoutineEvaluationStatus,
  RoutineIntakeStatus,
  type AcademicYearResponse,
} from "@/lib/api/generated/model";
import { useAcademicYearsList } from "@/lib/api/generated/academic-years/academic-years";
import { useRoutineInterviewsListAssigned } from "@/lib/api/generated/routine-interviews/routine-interviews";

const UUID_PATTERN = /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i;

function positivePage(value: string | null): number {
  const parsed = Number.parseInt(value ?? "1", 10);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : 1;
}

function enumParam<T extends string>(
  value: string | null,
  allowed: Record<string, T>,
): T | undefined {
  return value && Object.values(allowed).includes(value as T)
    ? value as T
    : undefined;
}

function updateQuery(
  pathname: string,
  current: URLSearchParams,
  updates: Record<string, string>,
  resetPage = true,
) {
  const next = new URLSearchParams(current);
  for (const [name, value] of Object.entries(updates)) {
    if (value) next.set(name, value);
    else next.delete(name);
  }
  if (resetPage && !("page" in updates)) next.set("page", "1");
  if (!next.get("page") || next.get("page") === "1") next.delete("page");
  const query = next.toString();
  return query ? `${pathname}?${query}` : pathname;
}

type QueueFilters = {
  search: string;
  academicYearId: string;
  deliveryMode: string;
  intakeStatus: string;
  evaluationStatus: string;
};

// The queue's search and filters apply together through one Apply action, so the search field no
// longer has its own button while the selects apply on change. The parent remounts this form when
// the URL changes, so the fields always start from the applied filters.
function RoutineQueueFilters({
  applied,
  hasFilters,
  canFilterYear,
  years,
  yearsPending,
  yearsFailed,
  onApply,
  onClear,
}: {
  applied: QueueFilters;
  hasFilters: boolean;
  canFilterYear: boolean;
  years: AcademicYearResponse[];
  yearsPending: boolean;
  yearsFailed: boolean;
  onApply: (filters: QueueFilters) => void;
  onClear: () => void;
}) {
  const [draft, setDraft] = useState(applied);
  const appliedYearKnown = years.some((year) => year.id === applied.academicYearId);

  function set(name: keyof QueueFilters, value: string) {
    setDraft((current) => ({ ...current, [name]: value }));
  }

  return (
    <form
      role="search"
      aria-label="Assigned Routine Interviews"
      className="mb-5"
      onSubmit={(event) => {
        event.preventDefault();
        onApply({ ...draft, search: draft.search.trim() });
      }}
    >
      <FilterToolbar
        fieldsClassName={canFilterYear ? "lg:grid-cols-3" : "lg:grid-cols-2 xl:grid-cols-4"}
        actions={
          <>
            {hasFilters ? (
              <Button variant="quiet" onClick={onClear}>
                Clear filters
              </Button>
            ) : null}
            <Button type="submit">Apply filters</Button>
          </>
        }
      >
        <FilterField label="Search Students" htmlFor="routine-queue-search">
          <Input
            id="routine-queue-search"
            type="search"
            value={draft.search}
            onChange={(event) => set("search", event.target.value)}
            placeholder="Name or Institutional ID"
          />
        </FilterField>
        {canFilterYear ? (
          <FilterField
            label="Academic Year"
            htmlFor="routine-queue-year"
            hint={
              yearsFailed ? (
                <p id="routine-queue-year-error" className="text-xs text-warning">
                  Academic Year choices could not be loaded.
                </p>
              ) : null
            }
          >
            <Select
              id="routine-queue-year"
              value={draft.academicYearId}
              disabled={yearsPending && !applied.academicYearId}
              aria-describedby={yearsFailed ? "routine-queue-year-error" : undefined}
              onChange={(event) => set("academicYearId", event.target.value)}
            >
              <option value="">All Academic Years</option>
              {applied.academicYearId && !appliedYearKnown ? (
                <option value={applied.academicYearId}>
                  {yearsPending ? "Loading Academic Year…" : "Selected Academic Year"}
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
        <FilterField label="Delivery mode" htmlFor="routine-queue-delivery">
          <Select
            id="routine-queue-delivery"
            value={draft.deliveryMode}
            onChange={(event) => set("deliveryMode", event.target.value)}
          >
            <option value="">All delivery modes</option>
            <option value={DeliveryMode.IN_PERSON}>In person</option>
            <option value={DeliveryMode.ONLINE}>Online</option>
          </Select>
        </FilterField>
        <FilterField label="Student Intake" htmlFor="routine-queue-intake">
          <Select
            id="routine-queue-intake"
            value={draft.intakeStatus}
            onChange={(event) => set("intakeStatus", event.target.value)}
          >
            <option value="">All statuses</option>
            <option value={RoutineIntakeStatus.DRAFT}>Draft</option>
            <option value={RoutineIntakeStatus.SUBMITTED}>Submitted</option>
          </Select>
        </FilterField>
        <FilterField label="Counselor Evaluation" htmlFor="routine-queue-evaluation">
          <Select
            id="routine-queue-evaluation"
            value={draft.evaluationStatus}
            onChange={(event) => set("evaluationStatus", event.target.value)}
          >
            <option value="">All statuses</option>
            <option value={RoutineEvaluationStatus.DRAFT}>Draft</option>
            <option value={RoutineEvaluationStatus.FINALIZED}>Finalized</option>
          </Select>
        </FilterField>
      </FilterToolbar>
    </form>
  );
}

export function CounselorRoutineWorkspace({
  access,
}: {
  access: RoutineInterviewAccess;
}) {
  const { user } = usePortalSession();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [createOpen, setCreateOpen] = useState(false);
  // Routine Interviews are annual; Counselors narrow the queue with the same
  // Academic Year list the Inventory roster uses.
  const canFilterYear = user.capabilities.includes("academic_years.view");
  const yearParam = searchParams.get("academic_year_id") ?? "";
  const academicYearId = canFilterYear && UUID_PATTERN.test(yearParam) ? yearParam : undefined;
  const academicYears = useAcademicYearsList({
    query: { enabled: canFilterYear && access.canViewAssigned, retry: false, staleTime: 5 * 60_000 },
  });
  const years = academicYears.data?.data.items ?? [];

  const search = searchParams.get("search") ?? "";
  const deliveryParam = enumParam(searchParams.get("delivery_mode"), DeliveryMode);
  const intakeParam = enumParam(searchParams.get("intake_status"), RoutineIntakeStatus);
  const evaluationParam = enumParam(searchParams.get("evaluation_status"), RoutineEvaluationStatus);
  const page = positivePage(searchParams.get("page"));
  const filters = {
    ...(search.trim() ? { search: search.trim() } : {}),
    ...(academicYearId ? { academic_year_id: academicYearId } : {}),
    ...(deliveryParam ? { delivery_mode: deliveryParam } : {}),
    ...(intakeParam ? { intake_status: intakeParam } : {}),
    ...(evaluationParam ? { evaluation_status: evaluationParam } : {}),
    page,
    page_size: 20,
  };
  const queue = useRoutineInterviewsListAssigned(filters, {
    query: { enabled: access.canViewAssigned, retry: false },
  });
  const pageData = queue.data?.data;
  const items = pageData?.items ?? [];
  const hasFilters = Boolean(search || academicYearId || deliveryParam || intakeParam || evaluationParam);
  const resultContext = pageData && !queue.isError
    ? describeResultPage({
        count: items.length,
        page: pageData.page,
        hasNext: pageData.has_next,
        noun: { one: "Routine Interview", other: "Routine Interviews" },
        filtered: hasFilters,
      })
    : null;

  function applyFilters(next: QueueFilters) {
    router.replace(
      updateQuery(pathname, new URLSearchParams(searchParams.toString()), {
        search: next.search,
        academic_year_id: canFilterYear ? next.academicYearId : "",
        delivery_mode: next.deliveryMode,
        intake_status: next.intakeStatus,
        evaluation_status: next.evaluationStatus,
      }),
      { scroll: false },
    );
  }

  function movePage(nextPage: number) {
    router.push(
      updateQuery(pathname, new URLSearchParams(searchParams.toString()), { page: String(nextPage) }, false),
      { scroll: false },
    );
  }

  return (
    <div>
      <RoutinePageHeading
        title="Routine Interviews"
        description="View Routine Interviews assigned to you and manage Counselor Evaluations after Students submit their Intake."
        action={access.canManageAssigned ? (
          <Button onClick={() => setCreateOpen(true)}>Start Routine Interview</Button>
        ) : undefined}
      />

      <RoutineDirectCreateDialog open={createOpen} onOpenChange={setCreateOpen} />

      <RoutineQueueFilters
        key={searchParams.toString()}
        applied={{
          search,
          academicYearId: academicYearId ?? "",
          deliveryMode: deliveryParam ?? "",
          intakeStatus: intakeParam ?? "",
          evaluationStatus: evaluationParam ?? "",
        }}
        hasFilters={hasFilters}
        canFilterYear={canFilterYear}
        years={years}
        yearsPending={academicYears.isPending}
        yearsFailed={academicYears.isError}
        onApply={applyFilters}
        onClear={() => router.replace(pathname, { scroll: false })}
      />

      <Panel aria-labelledby="assigned-routine-interviews">
        <PanelHeader
          title="Assigned Routine Interviews"
          titleId="assigned-routine-interviews"
          context={resultContext}
        />
        {queue.isPending ? (
          <RoutineInterviewListSkeleton label="Loading assigned Routine Interviews…" framed={false} />
        ) : queue.isError ? (
          <PanelMessage
            role="alert"
            tone="danger"
            action={
              <Button variant="secondary" onClick={() => void queue.refetch()}>
                Retry
              </Button>
            }
          >
            Assigned Routine Interviews could not be loaded. {routineErrorMessage(queue.error, "Try again in a moment.")}
          </PanelMessage>
        ) : items.length === 0 ? (
          <PanelMessage
            action={hasFilters ? (
              <Button variant="secondary" onClick={() => router.replace(pathname, { scroll: false })}>
                Clear filters
              </Button>
            ) : undefined}
          >
            {hasFilters
              ? "No assigned Routine Interviews match the current search and filters. Clear or adjust the filters to broaden the results."
              : "There are no Routine Interviews assigned to you yet."}
          </PanelMessage>
        ) : (
          <div className={dataTable.scroll}>
            <table className={`${dataTable.table} min-w-[900px]`}>
              <caption className="sr-only">Routine Interviews assigned to you</caption>
              <thead className={dataTable.head}>
                <tr>
                  <th scope="col" className={`${dataTable.headerCell} ${dataTable.stickyHeaderCell}`}>Student</th>
                  <th scope="col" className={dataTable.headerCell}>Academic Year / Program</th>
                  <th scope="col" className={dataTable.headerCell}>Visit / delivery</th>
                  <th scope="col" className={dataTable.headerCell}>Student Intake</th>
                  <th scope="col" className={dataTable.headerCell}>Counselor Evaluation</th>
                  <th scope="col" className={dataTable.headerCell}>Appointment</th>
                </tr>
              </thead>
              <tbody className={dataTable.body}>
                {items.map((routine) => (
                  <tr key={routine.id} className={dataTable.row}>
                    <th scope="row" className={`${dataTable.cell} ${dataTable.stickyCell} min-w-48 font-normal`}>
                      <Link href={`/portal/routine-interviews/${routine.id}`} className="font-semibold text-brand underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
                        {routine.student.display_name}
                      </Link>
                      <span className="mt-1 block text-xs text-muted">Created {formatRoutineDateTime(routine.created_at)}</span>
                      {routine.intake_submitted_at ? <span className="block text-xs text-muted">Intake submitted {formatRoutineDateTime(routine.intake_submitted_at)}</span> : null}
                    </th>
                    <td className={dataTable.cell}>{routine.inventory_context.academic_year.label}<span className="mt-1 block text-muted">{routine.inventory_context.course}{routine.inventory_context.major.trim() ? ` · ${routine.inventory_context.major}` : ""}</span></td>
                    <td className={dataTable.cell}>{routineEntryModeLabel(routine.entry_mode)}<span className="mt-1 block text-muted">{routineDeliveryModeLabel(routine.delivery_mode)}</span></td>
                    <td className={dataTable.cell}><RoutineStatus complete={routine.intake_status === "SUBMITTED"}>{routineIntakeStatusLabel(routine.intake_status)}</RoutineStatus></td>
                    <td className={dataTable.cell}><RoutineStatus complete={routine.evaluation_status === "FINALIZED"}>{routineEvaluationStatusLabel(routine.evaluation_status)}</RoutineStatus>{routine.evaluation_finalized_at ? <span className="mt-1 block text-xs text-muted">{formatRoutineDateTime(routine.evaluation_finalized_at)}</span> : null}</td>
                    <td className={dataTable.cell}>{routine.appointment ? <><span className="font-medium text-ink">{routine.appointment.reference_code}</span><span className="mt-1 block text-muted">{formatRoutineDateTimeRange(routine.appointment.starts_at, routine.appointment.ends_at)}</span></> : <span className="text-muted">—</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {!queue.isError && pageData ? (
          <CanonicalPagination
            className="border-brand-line px-4 py-3 sm:px-5"
            page={pageData.page}
            hasNext={pageData.has_next}
            label="Assigned Routine Interviews pages"
            onPageChange={movePage}
          />
        ) : null}
      </Panel>
    </div>
  );
}
