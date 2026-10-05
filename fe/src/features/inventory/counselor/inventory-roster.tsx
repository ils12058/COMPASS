"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, type FormEvent, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { dataTable } from "@/components/ui/data-table";
import { FormRevisionFilter } from "@/features/institutional-forms/form-revision-filter";
import type { FormRevisionFilterOption } from "@/lib/api/generated/model";
import { FilterField } from "@/components/ui/filter-toolbar";
import { FloatingListTools, ListSearchField } from "@/components/ui/floating-list-tools";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { RowsSkeleton } from "@/components/ui/rows-skeleton";
import { Select } from "@/components/ui/select";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { describeResultPage } from "@/features/portal/components/result-context";
import { getInventoryAccess } from "@/features/inventory/inventory-access";
import {
  formatInventoryDate,
  InventoryHeading,
  InventoryStatus,
  inventoryErrorMessage,
} from "@/features/inventory/inventory-shared";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { useAcademicYearsList } from "@/lib/api/generated/academic-years/academic-years";
import { useInventoryListStudents } from "@/lib/api/generated/inventory/inventory";
import { InventoryStatusValue, type AcademicYearResponse } from "@/lib/api/generated/model";

const pageSize = 20;

function validStatus(value: string | null): value is "MISSING" | "DRAFT" | "SUBMITTED" {
  return value === InventoryStatusValue.MISSING ||
    value === InventoryStatusValue.DRAFT ||
    value === InventoryStatusValue.SUBMITTED;
}

type RosterFilterDraft = {
  search: string;
  formRevisionId: string;
  academicYearId: string;
  status: string;
  yearLevel: string;
};

// Search and filters apply together through one Apply action. The parent remounts this form when
// the URL changes, so the fields always start from the applied filters. Missing applies only to
// the current Academic Year, so it is offered only while the chosen year is current.
function RosterFilters({
  applied,
  revisions,
  hasFilters,
  canFilterYear,
  years,
  yearsPending,
  yearsFailed,
  appliedYearKnown,
  onApply,
  onClear,
  notes,
}: {
  applied: RosterFilterDraft;
  revisions?: FormRevisionFilterOption[];
  hasFilters: boolean;
  canFilterYear: boolean;
  years: AcademicYearResponse[];
  yearsPending: boolean;
  yearsFailed: boolean;
  appliedYearKnown: boolean;
  onApply: (filters: RosterFilterDraft) => void;
  onClear: () => void;
  notes: ReactNode;
}) {
  const [draft, setDraft] = useState(applied);
  const draftYear = years.find((year) => year.id === draft.academicYearId);
  const draftHistorical = Boolean(draftYear && !draftYear.is_current);
  const advancedCount = [applied.formRevisionId, canFilterYear ? applied.academicYearId : "", applied.status, applied.yearLevel].filter(Boolean).length;

  return (
    <form
      role="search"
      aria-label="Individual Inventory roster"
      onSubmit={(event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        onApply({ ...draft, search: draft.search.trim() });
      }}
    >
      <FloatingListTools
        submits
        filterCount={advancedCount}
        clear={hasFilters ? <Button variant="quiet" onClick={onClear}>Clear filters</Button> : undefined}
        filters={
          <>
        {canFilterYear ? (
          <FilterField label="Academic Year" htmlFor="inventory-roster-year">
            <Select
              id="inventory-roster-year"
              value={draft.academicYearId}
              disabled={yearsPending || yearsFailed}
              onChange={(event) => {
                const academicYearId = event.target.value;
                const year = years.find((item) => item.id === academicYearId);
                setDraft((current) => ({
                  ...current,
                  academicYearId,
                  status: year && !year.is_current && current.status === InventoryStatusValue.MISSING ? "" : current.status,
                }));
              }}
            >
              <option value="">Current Academic Year</option>
              {applied.academicYearId && !appliedYearKnown ? (
                <option value={applied.academicYearId}>
                  {yearsFailed ? "Selected Academic Year" : "Loading Academic Year…"}
                </option>
              ) : null}
              {years.map((year) => (
                <option key={year.id} value={year.id}>{year.label}{year.is_current ? " · Current" : ""}</option>
              ))}
            </Select>
          </FilterField>
        ) : null}

        <FormRevisionFilter id="inventory-roster-revision" selectedId={draft.formRevisionId} value={draft.formRevisionId} options={revisions} onChange={(event) => setDraft((current) => ({ ...current, formRevisionId: event.target.value }))} />
        <FilterField label="Status" htmlFor="inventory-roster-status">
          <Select
            id="inventory-roster-status"
            value={draft.status}
            onChange={(event) => setDraft((current) => ({ ...current, status: event.target.value }))}
          >
            <option value="">All statuses</option>
            {!draftHistorical ? <option value={InventoryStatusValue.MISSING}>Missing</option> : null}
            <option value={InventoryStatusValue.DRAFT}>Draft</option>
            <option value={InventoryStatusValue.SUBMITTED}>Submitted</option>
          </Select>
        </FilterField>

        <FilterField label="Year Level" htmlFor="inventory-roster-year-level">
          <Select
            id="inventory-roster-year-level"
            value={draft.yearLevel}
            onChange={(event) => setDraft((current) => ({ ...current, yearLevel: event.target.value }))}
          >
            <option value="">All Year Levels</option>
            {Array.from({ length: 10 }, (_, index) => index + 1).map((year) => (
              <option key={year} value={year}>{year}{year === 1 ? "st" : year === 2 ? "nd" : year === 3 ? "rd" : "th"} year</option>
            ))}
          </Select>
        </FilterField>
          </>
        }
      >
        <ListSearchField
          id="inventory-roster-search"
          label="Search the roster"
          value={draft.search}
          onChange={(event) => setDraft((current) => ({ ...current, search: event.target.value }))}
          placeholder="Search by Student name or Institutional ID"
        />
      </FloatingListTools>
      {/* Notes about how the filters were applied stay on the page, above the results, while the
          filters are closed. */}
      {notes ? <div className="mb-5 space-y-2">{notes}</div> : null}
    </form>
  );
}

export function CounselorInventoryRoster() {
  const { user } = usePortalSession();
  const access = getInventoryAccess(user);
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const paramsString = searchParams.toString();
  const params = new URLSearchParams(paramsString);
  const academicYearId = params.get("academic_year_id") ?? "";
  const requestedStatus = params.get("status");
  const status = validStatus(requestedStatus) ? requestedStatus : undefined;
  const yearLevelValue = Number.parseInt(params.get("year_level") ?? "", 10);
  const yearLevel = Number.isInteger(yearLevelValue) && yearLevelValue >= 1 && yearLevelValue <= 10
    ? yearLevelValue
    : undefined;
  const search = (params.get("search") ?? "").trim();
  const formRevisionId = params.get("form_revision_id") ?? "";
  const requestedPage = Number.parseInt(params.get("page") ?? "1", 10);
  const page = Number.isInteger(requestedPage) && requestedPage > 0 ? requestedPage : 1;
  const canFilterYear = user.capabilities.includes("academic_years.view");
  const academicYears = useAcademicYearsList({
    query: { enabled: access.canViewRoster && canFilterYear, retry: false },
  });
  const years = academicYears.data?.data.items ?? [];
  const selectedYear = years.find((year) => year.id === academicYearId);
  const yearListResolved = Boolean(academicYears.data);
  const invalidYear = canFilterYear && yearListResolved && Boolean(academicYearId) && !selectedYear;
  const historicalYear = Boolean(selectedYear && !selectedYear.is_current);
  const suppressMissing = status === InventoryStatusValue.MISSING && historicalYear;
  const missingYearUnresolved = status === InventoryStatusValue.MISSING &&
    Boolean(academicYearId) && !selectedYear && !invalidYear;
  const effectiveStatus = suppressMissing || missingYearUnresolved ? undefined : status;
  const validAcademicYearId = invalidYear ? "" : academicYearId;
  const roster = useInventoryListStudents(
    {
      ...(validAcademicYearId ? { academic_year_id: validAcademicYearId } : {}),
      ...(effectiveStatus ? { status: effectiveStatus } : {}),
      ...(yearLevel ? { year_level: yearLevel } : {}),
      ...(search ? { search } : {}),
      ...(formRevisionId ? { form_revision_id: formRevisionId } : {}),
      page,
      page_size: pageSize,
    },
    { query: { enabled: access.canViewRoster, retry: false } },
  );
  const response = roster.data?.data;
  const hasFilters = Boolean(formRevisionId || validAcademicYearId || status || yearLevel || search);

  useEffect(() => {
    const next = new URLSearchParams(paramsString);
    let changed = false;
    if (invalidYear) {
      next.delete("academic_year_id");
      changed = true;
    }
    if (suppressMissing) {
      next.delete("status");
      changed = true;
    }
    if (changed) {
      next.delete("page");
      router.replace(next.size ? `${pathname}?${next.toString()}` : pathname, { scroll: false });
    }
  }, [invalidYear, paramsString, pathname, router, suppressMissing]);

  function applyFilters(next: RosterFilterDraft) {
    const query = new URLSearchParams(paramsString);
    const values: Record<string, string> = {
      search: next.search,
      form_revision_id: next.formRevisionId,
      academic_year_id: canFilterYear ? next.academicYearId : "",
      status: next.status,
      year_level: next.yearLevel,
    };
    for (const [name, value] of Object.entries(values)) {
      if (value) query.set(name, value);
      else query.delete(name);
    }
    query.delete("page");
    router.replace(query.size ? `${pathname}?${query.toString()}` : pathname, { scroll: false });
  }

  function movePage(nextPage: number) {
    const next = new URLSearchParams(paramsString);
    if (nextPage > 1) next.set("page", String(nextPage));
    else next.delete("page");
    router.push(`${pathname}?${next.toString()}`);
  }

  return (
    <section aria-label="Counselor Individual Inventory roster">
      <InventoryHeading
        title="Individual Inventory"
      />

      <RosterFilters
        key={paramsString}
        revisions={response?.filter_options.form_revisions}
        applied={{
          search,
          formRevisionId,
          academicYearId: selectedYear?.id ?? (academicYearId && !invalidYear ? academicYearId : ""),
          status: suppressMissing ? "" : status ?? "",
          yearLevel: yearLevel ? String(yearLevel) : "",
        }}
        hasFilters={hasFilters}
        canFilterYear={canFilterYear}
        years={years}
        yearsPending={academicYears.isPending}
        yearsFailed={academicYears.isError}
        appliedYearKnown={Boolean(selectedYear)}
        onApply={applyFilters}
        onClear={() => router.replace(pathname, { scroll: false })}
        notes={academicYears.isError && canFilterYear || missingYearUnresolved || suppressMissing ? (
          <>
            {academicYears.isError && canFilterYear ? (
              <p role="status" className="text-sm text-warning">Academic Year choices could not be loaded. The roster still uses the selected Academic Year when one is present; otherwise, it uses the current Academic Year.</p>
            ) : null}
            {missingYearUnresolved ? (
              <p role="status" className="text-sm text-warning">The Missing filter is paused until this Academic Year can be confirmed. Missing status applies only to the current Academic Year.</p>
            ) : null}
            {suppressMissing ? (
              <p role="status" className="text-sm text-muted">The Missing filter applies only to the current Academic Year and was cleared for this selection.</p>
            ) : null}
          </>
        ) : null}
      />

      <Panel aria-labelledby="inventory-roster-results-heading">
        <PanelHeader
          title="Students"
          titleId="inventory-roster-results-heading"
          context={roster.isFetching && !roster.isPending
            ? "Refreshing roster…"
            : response && !roster.isError
              ? describeResultPage({ count: response.items.length, page: response.page, hasNext: response.has_next, noun: { one: "Student", other: "Students" }, filtered: hasFilters })
              : null}
        />
        {roster.isPending ? (
          <RowsSkeleton label="Loading scoped Student Individual Inventory roster…" rows={2} />
        ) : roster.isError ? (
          <PanelMessage role="alert" tone="danger" action={<Button variant="secondary" onClick={() => void roster.refetch()}>Try again</Button>}>
            {inventoryErrorMessage(roster.error, "The scoped Student Inventory roster could not be loaded.")}
          </PanelMessage>
        ) : response && response.items.length === 0 ? (
          <PanelMessage>
            {effectiveStatus === InventoryStatusValue.MISSING
              ? "No Students are currently missing an Inventory under these filters."
              : hasFilters
                ? "No students match these filters."
                : "No students are available."}
          </PanelMessage>
        ) : response ? (
          <div className={dataTable.scroll}>
            <table className={`${dataTable.table} min-w-[62rem]`}>
              <caption className="sr-only">Counselor-scoped annual Student Individual Inventory roster</caption>
              <thead className={dataTable.head}>
                <tr>
                  <th scope="col" className={`${dataTable.headerCell} ${dataTable.stickyHeaderCell} min-w-64`}>Student</th>
                  <th scope="col" className={`${dataTable.headerCell} min-w-32`}>Academic Year</th>
                  <th scope="col" className={`${dataTable.headerCell} min-w-48`}>Program</th>
                  <th scope="col" className={`${dataTable.headerCell} min-w-24`}>Year Level</th>
                  <th scope="col" className={`${dataTable.headerCell} min-w-44`}>Status</th>
                  <th scope="col" className={`${dataTable.headerCell} min-w-40`}>Submitted</th>
                </tr>
              </thead>
              <tbody className={dataTable.body}>
                {response.items.map((row) => {
                  const submittedAt = row.last_submitted_at ?? row.submitted_at;
                  const canOpen = row.status === InventoryStatusValue.SUBMITTED && Boolean(row.inventory_id);
                  const identity = (
                    <>
                      <span className="block font-semibold">{row.student.display_name}</span>
                      <span className="mt-1 block font-mono text-xs text-muted">{row.student.institutional_id ?? "Institutional ID not provided"}</span>
                    </>
                  );
                  return (
                    <tr key={row.student.id} className={dataTable.row}>
                      <th scope="row" className={`${dataTable.cell} ${dataTable.stickyCell} text-left font-normal text-ink`}>
                        {canOpen && row.inventory_id ? (
                          <Link href={`/portal/inventory/records/${row.inventory_id}`} aria-label={`View submitted Individual Inventory for ${row.student.display_name}`} className="rounded-sm text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
                            {identity}
                          </Link>
                        ) : identity}
                      </th>
                      <td className={`${dataTable.cell} text-ink`}>{row.academic_year.label}</td>
                      <td className={`${dataTable.cell} text-ink`}>{row.program ? `${row.program.code} · ${row.program.name}` : "Not provided"}</td>
                      <td className={`${dataTable.cell} text-ink`}>{row.year_level ?? "Not provided"}</td>
                      <td className={dataTable.cell}>
                        <InventoryStatus status={row.status} correctionPending={row.correction_pending} />
                      </td>
                      <td className={`${dataTable.cell} text-ink`}>{formatInventoryDate(submittedAt)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : null}
        {response && !roster.isError ? (
          <CanonicalPagination
            className="border-brand-line px-4 py-3 sm:px-5"
            page={response.page}
            hasNext={response.has_next}
            disabled={roster.isFetching}
            label="Inventory roster pagination"
            onPageChange={movePage}
          />
        ) : null}
      </Panel>
    </section>
  );
}
