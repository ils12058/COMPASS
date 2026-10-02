"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { usePortalSession } from "@/features/portal/components/portal-session";
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
  RoutineQueryError,
  RoutineStatus,
} from "@/features/routine-interviews/routine-interviews-shared";
import {
  DeliveryMode,
  RoutineEvaluationStatus,
  RoutineIntakeStatus,
} from "@/lib/api/generated/model";
import { useAcademicYearsList } from "@/lib/api/generated/academic-years/academic-years";
import { useRoutineInterviewsListAssigned } from "@/lib/api/generated/routine-interviews/routine-interviews";

const tableCell = "px-4 py-3 align-top text-sm";
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
  const selectedYearKnown = years.some((year) => year.id === academicYearId);

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

  function setFilter(name: string, value: string) {
    router.replace(
      updateQuery(pathname, new URLSearchParams(searchParams.toString()), { [name]: value }),
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
          <Button onClick={() => setCreateOpen(true)}>Start direct Routine Interview</Button>
        ) : undefined}
      />

      <RoutineDirectCreateDialog open={createOpen} onOpenChange={setCreateOpen} />

      <section aria-labelledby="assigned-routine-interviews">
          <h2 id="assigned-routine-interviews" className="sr-only">Assigned Routine Interviews</h2>
          <div className={`mb-5 grid gap-4 border-y border-border py-5 sm:grid-cols-2 ${canFilterYear ? "xl:grid-cols-5" : "xl:grid-cols-4"}`}>
            <form
              className="grid gap-2 sm:col-span-2 xl:col-span-1"
              onSubmit={(event) => {
                event.preventDefault();
                const formData = new FormData(event.currentTarget);
                setFilter("search", String(formData.get("search") ?? "").trim());
              }}
            >
              <Label htmlFor="routine-queue-search">Search Students</Label>
              <input
                key={search}
                id="routine-queue-search"
                name="search"
                type="search"
                defaultValue={search}
                className="min-h-10 rounded-md border border-border bg-surface-raised px-3 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                placeholder="Name or Institutional ID"
              />
              <Button type="submit" variant="secondary" className="justify-self-start">Search</Button>
            </form>
            {canFilterYear ? (
              <div className="grid gap-2">
                <Label htmlFor="routine-queue-year">Academic Year</Label>
                <Select
                  id="routine-queue-year"
                  value={academicYearId ?? ""}
                  disabled={academicYears.isPending && !academicYearId}
                  onChange={(event) => setFilter("academic_year_id", event.target.value)}
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
                {academicYears.isError ? (
                  <p className="text-xs text-warning">Academic Year choices could not be loaded.</p>
                ) : null}
              </div>
            ) : null}
            <div className="grid gap-2">
              <Label htmlFor="routine-queue-delivery">Delivery mode</Label>
              <Select
                id="routine-queue-delivery"
                value={deliveryParam ?? "ALL"}
                onChange={(event) => setFilter("delivery_mode", event.target.value === "ALL" ? "" : event.target.value)}
              >
                <option value="ALL">All delivery modes</option>
                <option value={DeliveryMode.IN_PERSON}>In person</option>
                <option value={DeliveryMode.ONLINE}>Online</option>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="routine-queue-intake">Student Intake</Label>
              <Select
                id="routine-queue-intake"
                value={intakeParam ?? "ALL"}
                onChange={(event) => setFilter("intake_status", event.target.value === "ALL" ? "" : event.target.value)}
              >
                <option value="ALL">All statuses</option>
                <option value={RoutineIntakeStatus.DRAFT}>Draft</option>
                <option value={RoutineIntakeStatus.SUBMITTED}>Submitted</option>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="routine-queue-evaluation">Counselor Evaluation</Label>
              <Select
                id="routine-queue-evaluation"
                value={evaluationParam ?? "ALL"}
                onChange={(event) => setFilter("evaluation_status", event.target.value === "ALL" ? "" : event.target.value)}
              >
                <option value="ALL">All statuses</option>
                <option value={RoutineEvaluationStatus.DRAFT}>Draft</option>
                <option value={RoutineEvaluationStatus.FINALIZED}>Finalized</option>
              </Select>
            </div>
            {hasFilters ? (
              <div className="sm:col-span-2 xl:col-span-full">
                <Button
                  variant="quiet"
                  onClick={() => router.replace(pathname, { scroll: false })}
                >
                  Clear filters
                </Button>
              </div>
            ) : null}
          </div>

          {queue.isPending ? (
            <RoutineInterviewListSkeleton label="Loading assigned Routine Interviews…" />
          ) : queue.isError ? (
            <RoutineQueryError
              message={routineErrorMessage(queue.error, "Try again in a moment.")}
              onRetry={() => void queue.refetch()}
            />
          ) : items.length === 0 ? (
            <p className="border-y border-border py-6 text-sm text-muted">
              {hasFilters
                ? "No assigned Routine Interviews match the current search and filters. Clear or adjust the filters to broaden the results."
                : "There are no Routine Interviews assigned to you yet."}
            </p>
          ) : (
            <>
              <div className="overflow-x-auto border-y border-border">
                <table className="w-full min-w-[900px] border-separate border-spacing-0 text-left">
                  <caption className="sr-only">Routine Interviews assigned to you</caption>
                  <thead className="bg-surface-muted text-xs font-semibold uppercase tracking-wide text-muted">
                    <tr>
                      <th scope="col" className={`${tableCell} sticky left-0 z-20 bg-surface-muted`}>Student</th>
                      <th scope="col" className={tableCell}>Academic Year / Program</th>
                      <th scope="col" className={tableCell}>Visit / delivery</th>
                      <th scope="col" className={tableCell}>Student Intake</th>
                      <th scope="col" className={tableCell}>Counselor Evaluation</th>
                      <th scope="col" className={tableCell}>Appointment</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {items.map((routine) => (
                      <tr key={routine.id} className="group hover:bg-surface-muted/50">
                        <th scope="row" className={`${tableCell} sticky left-0 z-10 min-w-48 bg-surface-raised font-normal group-hover:bg-surface-muted`}>
                          <Link href={`/portal/routine-interviews/${routine.id}`} className="font-semibold text-brand underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
                            {routine.student.display_name}
                          </Link>
                          <span className="mt-1 block text-xs text-muted">Created {formatRoutineDateTime(routine.created_at)}</span>
                          {routine.intake_submitted_at ? <span className="block text-xs text-muted">Intake submitted {formatRoutineDateTime(routine.intake_submitted_at)}</span> : null}
                        </th>
                        <td className={tableCell}>{routine.inventory_context.academic_year.label}<span className="mt-1 block text-muted">{routine.inventory_context.course}{routine.inventory_context.major.trim() ? ` · ${routine.inventory_context.major}` : ""}</span></td>
                        <td className={tableCell}>{routineEntryModeLabel(routine.entry_mode)}<span className="mt-1 block text-muted">{routineDeliveryModeLabel(routine.delivery_mode)}</span></td>
                        <td className={tableCell}><RoutineStatus complete={routine.intake_status === "SUBMITTED"}>{routineIntakeStatusLabel(routine.intake_status)}</RoutineStatus></td>
                        <td className={tableCell}><RoutineStatus complete={routine.evaluation_status === "FINALIZED"}>{routineEvaluationStatusLabel(routine.evaluation_status)}</RoutineStatus>{routine.evaluation_finalized_at ? <span className="mt-1 block text-xs text-muted">{formatRoutineDateTime(routine.evaluation_finalized_at)}</span> : null}</td>
                        <td className={tableCell}>{routine.appointment ? <><span className="font-medium text-ink">{routine.appointment.reference_code}</span><span className="mt-1 block text-muted">{formatRoutineDateTimeRange(routine.appointment.starts_at, routine.appointment.ends_at)}</span></> : <span className="text-muted">—</span>}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
          {!queue.isError && pageData ? (
            <CanonicalPagination
              page={pageData.page}
              hasNext={pageData.has_next}
              label="Assigned Routine Interviews pages"
              onPageChange={movePage}
            />
          ) : null}
      </section>
    </div>
  );
}
