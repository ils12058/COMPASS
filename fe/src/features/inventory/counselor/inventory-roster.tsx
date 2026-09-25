"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { getInventoryAccess } from "@/features/inventory/inventory-access";
import {
  formatInventoryDate,
  InventoryHeading,
  InventoryQueryError,
  InventoryStatus,
  inventorySelectClass,
} from "@/features/inventory/inventory-shared";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { useAcademicYearsList } from "@/lib/api/generated/academic-years/academic-years";
import { useInventoryListStudents } from "@/lib/api/generated/inventory/inventory";
import { InventoryStatusValue } from "@/lib/api/generated/model";

const pageSize = 20;

function validStatus(value: string | null): value is "MISSING" | "DRAFT" | "SUBMITTED" {
  return value === InventoryStatusValue.MISSING ||
    value === InventoryStatusValue.DRAFT ||
    value === InventoryStatusValue.SUBMITTED;
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
      page,
      page_size: pageSize,
    },
    { query: { enabled: access.canViewRoster, retry: false } },
  );
  const response = roster.data?.data;
  const hasFilters = Boolean(validAcademicYearId || status || yearLevel || search);

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

  function updateFilter(name: string, value: string) {
    const next = new URLSearchParams(paramsString);
    if (value) next.set(name, value);
    else next.delete(name);
    next.delete("page");
    router.replace(next.size ? `${pathname}?${next.toString()}` : pathname, { scroll: false });
  }

  function applySearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const value = form.get("search");
    updateFilter("search", typeof value === "string" ? value.trim() : "");
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
        description="Students within your authorized Guidance scope."
      />

      <div className="border-b border-border py-5">
        <div className="grid gap-4 lg:grid-cols-[minmax(16rem,1.4fr)_minmax(12rem,1fr)_minmax(10rem,.7fr)_minmax(10rem,.7fr)] lg:items-end">
          <form key={search} onSubmit={applySearch}>
            <Label htmlFor="inventory-roster-search">Search</Label>
            <div className="mt-2 flex gap-2">
              <Input
                id="inventory-roster-search"
                name="search"
                type="search"
                defaultValue={search}
                placeholder="Search by Student name or Institutional ID"
              />
              <Button type="submit" variant="secondary">Search</Button>
            </div>
          </form>

          {canFilterYear ? (
            <div>
              <Label htmlFor="inventory-roster-year">Academic Year</Label>
              <select
                id="inventory-roster-year"
                className={`mt-2 ${inventorySelectClass}`}
                value={selectedYear?.id ?? (academicYearId && !invalidYear ? academicYearId : "")}
                disabled={academicYears.isPending || academicYears.isError}
                onChange={(event) => updateFilter("academic_year_id", event.target.value)}
              >
                <option value="">Current Academic Year</option>
                {academicYearId && !selectedYear && !invalidYear ? (
                  <option value={academicYearId}>
                    {academicYears.isError ? "Selected Academic Year" : "Loading Academic Year…"}
                  </option>
                ) : null}
                {years.map((year) => (
                  <option key={year.id} value={year.id}>{year.label}{year.is_current ? " · Current" : ""}</option>
                ))}
              </select>
            </div>
          ) : null}

          <div>
            <Label htmlFor="inventory-roster-status">Status</Label>
            <select
              id="inventory-roster-status"
              className={`mt-2 ${inventorySelectClass}`}
              value={suppressMissing ? "" : status ?? ""}
              onChange={(event) => updateFilter("status", event.target.value)}
            >
              <option value="">All statuses</option>
              {!historicalYear ? <option value={InventoryStatusValue.MISSING}>Missing</option> : null}
              <option value={InventoryStatusValue.DRAFT}>Draft</option>
              <option value={InventoryStatusValue.SUBMITTED}>Submitted</option>
            </select>
          </div>

          <div>
            <Label htmlFor="inventory-roster-year-level">Year Level</Label>
            <select
              id="inventory-roster-year-level"
              className={`mt-2 ${inventorySelectClass}`}
              value={yearLevel ?? ""}
              onChange={(event) => updateFilter("year_level", event.target.value)}
            >
              <option value="">All Year Levels</option>
              {Array.from({ length: 10 }, (_, index) => index + 1).map((year) => (
                <option key={year} value={year}>{year}{year === 1 ? "st" : year === 2 ? "nd" : year === 3 ? "rd" : "th"} year</option>
              ))}
            </select>
          </div>
        </div>
        {academicYears.isError && canFilterYear ? (
          <p role="status" className="mt-3 text-sm text-warning">Academic Year choices could not be loaded. The roster still uses the selected Academic Year when one is present; otherwise, it uses the current Academic Year.</p>
        ) : null}
        {missingYearUnresolved ? (
          <p role="status" className="mt-3 text-sm text-warning">The Missing filter is held until this Academic Year can be verified, so an unsupported historical Missing query is not sent.</p>
        ) : null}
        {suppressMissing ? (
          <p role="status" className="mt-3 text-sm text-muted">The Missing filter applies only to the current Academic Year and was cleared for this selection.</p>
        ) : null}
        {hasFilters ? (
          <Button variant="quiet" className="mt-3" onClick={() => router.replace(pathname, { scroll: false })}>
            Clear filters
          </Button>
        ) : null}
      </div>

      {roster.isPending ? (
        <div className="mt-5 space-y-2" aria-busy="true">
          <div className="h-12 animate-pulse rounded bg-surface-muted" />
          <div className="h-12 animate-pulse rounded bg-surface-muted" />
          <p className="sr-only">Loading scoped Student Individual Inventory roster…</p>
        </div>
      ) : roster.isError ? (
        <div className="mt-5">
          <InventoryQueryError error={roster.error} fallback="The scoped Student Inventory roster could not be loaded." onRetry={() => void roster.refetch()} />
        </div>
      ) : response && response.items.length === 0 ? (
        <p className="border-b border-border py-8 text-sm text-muted">
          {effectiveStatus === InventoryStatusValue.MISSING
            ? "No Students are currently missing an Inventory under these filters."
            : hasFilters
              ? "No Students match these filters."
              : "No Students are available within your current Inventory scope."}
        </p>
      ) : response ? (
        <>
          {roster.isFetching ? <p role="status" className="mt-3 text-xs text-muted">Refreshing roster…</p> : null}
          <div className="mt-5 overflow-x-auto border-y border-border">
            <table className="w-full min-w-[62rem] border-collapse text-left text-sm">
              <caption className="sr-only">Counselor-scoped annual Student Individual Inventory roster</caption>
              <thead>
                <tr className="border-b border-border bg-surface-muted">
                  <th scope="col" className="sticky left-0 z-10 min-w-64 bg-surface-muted px-3 py-3 font-semibold text-ink">Student</th>
                  <th scope="col" className="min-w-32 px-3 py-3 font-semibold text-ink">Academic Year</th>
                  <th scope="col" className="min-w-48 px-3 py-3 font-semibold text-ink">Program</th>
                  <th scope="col" className="min-w-24 px-3 py-3 font-semibold text-ink">Year Level</th>
                  <th scope="col" className="min-w-44 px-3 py-3 font-semibold text-ink">Status</th>
                  <th scope="col" className="min-w-40 px-3 py-3 font-semibold text-ink">Submitted</th>
                </tr>
              </thead>
              <tbody>
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
                    <tr key={row.student.id} className="border-b border-border last:border-b-0">
                      <th scope="row" className="sticky left-0 bg-surface-raised px-3 py-4 text-left align-top font-normal text-ink">
                        {canOpen && row.inventory_id ? (
                          <Link href={`/portal/inventory/records/${row.inventory_id}`} aria-label={`View submitted Individual Inventory for ${row.student.display_name}`} className="rounded-sm hover:text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
                            {identity}
                          </Link>
                        ) : identity}
                      </th>
                      <td className="px-3 py-4 align-top text-ink">{row.academic_year.label}</td>
                      <td className="px-3 py-4 align-top text-ink">{row.program ? `${row.program.code} · ${row.program.name}` : "Not provided"}</td>
                      <td className="px-3 py-4 align-top text-ink">{row.year_level ?? "Not provided"}</td>
                      <td className="px-3 py-4 align-top">
                        <InventoryStatus status={row.status} correctionPending={row.correction_pending} />
                      </td>
                      <td className="px-3 py-4 align-top text-ink">{formatInventoryDate(submittedAt)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {page > 1 || response.has_next ? (
            <nav aria-label="Inventory roster pagination" className="mt-5 flex items-center justify-between gap-4">
              <Button variant="secondary" disabled={page <= 1 || roster.isFetching} onClick={() => movePage(page - 1)}>
                Previous
              </Button>
              <p aria-live="polite" className="text-sm text-muted">Page {response.page}</p>
              <Button variant="secondary" disabled={!response.has_next || roster.isFetching} onClick={() => movePage(page + 1)}>
                Next
              </Button>
            </nav>
          ) : null}
        </>
      ) : null}
    </section>
  );
}
