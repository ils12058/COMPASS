"use client";

import { CircleAlert, NotebookPen, X } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { dataTable } from "@/components/ui/data-table";
import { FilterField } from "@/components/ui/filter-toolbar";
import { FloatingListTools, ListSearchField } from "@/components/ui/floating-list-tools";
import { Input } from "@/components/ui/input";
import { PageAction } from "@/components/ui/page-action";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { SortField } from "@/components/ui/sort-field";
import { SortableColumnHeader } from "@/components/ui/sortable-column-header";
import { useListOrdering } from "@/features/portal/components/list-ordering";
import { Select } from "@/components/ui/select";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { describeResultPage } from "@/features/portal/components/result-context";
import type { CounselingAccess } from "@/features/counseling/counseling-access";
import {
  counselingDeliveryModeLabel,
  counselingEntryModeLabel,
  counselingErrorMessage,
  CounselingListSkeleton,
  CounselingPageHeading,
  encounterOrderingOptions,
  formatCounselingDateTime,
} from "@/features/counseling/counseling-shared";
import { RecordEncounterForm } from "@/features/counseling/record-encounter-form";
import {
  CounselingEncounterOrdering,
  CounselingEntryMode,
  DeliveryMode,
} from "@/lib/api/generated/model";
import { useCounselingListMyEncounters } from "@/lib/api/generated/counseling/counseling";

function positivePage(value: string | null): number {
  const parsed = Number.parseInt(value ?? "1", 10);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : 1;
}

function enumParam<T extends string>(value: string | null, allowed: Record<string, T>): T | undefined {
  return value && Object.values(allowed).includes(value as T) ? value as T : undefined;
}

function updateQuery(pathname: string, current: URLSearchParams, name: string, value: string) {
  const next = new URLSearchParams(current);
  if (value) next.set(name, value);
  else next.delete(name);
  if (name !== "page") next.set("page", "1");
  if (next.get("page") === "1") next.delete("page");
  const query = next.toString();
  return query ? `${pathname}?${query}` : pathname;
}

export function CounselorEncounters({ access }: { access: CounselingAccess }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [recordOpen, setRecordOpen] = useState(false);
  const [recordUncertain, setRecordUncertain] = useState(false);
  const entryMode = enumParam(searchParams.get("entry_mode"), CounselingEntryMode);
  const deliveryMode = enumParam(searchParams.get("delivery_mode"), DeliveryMode);
  const fromDate = searchParams.get("from_date") ?? "";
  const toDate = searchParams.get("to_date") ?? "";
  const page = positivePage(searchParams.get("page"));
  const search = searchParams.get("search") ?? "";
  const hasFilters = Boolean(search || entryMode || deliveryMode || fromDate || toDate);
  const { requested: requestedOrdering, setOrdering } = useListOrdering(CounselingEncounterOrdering);
  const encounters = useCounselingListMyEncounters(
    {
      ...(search ? { search } : {}),
      ...(entryMode ? { entry_mode: entryMode } : {}),
      ...(deliveryMode ? { delivery_mode: deliveryMode } : {}),
      ...(fromDate ? { from_date: fromDate } : {}),
      ...(toDate ? { to_date: toDate } : {}),
      ...(requestedOrdering ? { ordering: requestedOrdering } : {}),
      page,
      page_size: 20,
    },
    { query: { enabled: access.canViewAssigned, retry: false } },
  );
  const items = encounters.data?.data.items ?? [];
  // The order the rows are in: the reader's choice, or the default the backend applied.
  const ordering = requestedOrdering ?? encounters.data?.data.ordering;
  // Clearing the filters keeps the chosen order; sorting is not a filter.
  const clearedHref = requestedOrdering ? `${pathname}?ordering=${requestedOrdering}` : pathname;

  return (
    <div>
      <CounselingPageHeading
        title="Counseling"
        description="Record Counseling interactions after they take place."
        action={access.canManageAssigned ? (
          recordUncertain ? (
            <PageAction icon={CircleAlert} label="Unconfirmed" labelDetail="recording result" disabled />
          ) : (
            <PageAction
              icon={recordOpen ? X : NotebookPen}
              label={recordOpen ? "Close" : "Record"}
              labelDetail={recordOpen ? "recording" : "counseling encounter"}
              variant={recordOpen ? "secondary" : "primary"}
              aria-expanded={recordOpen}
              onClick={() => setRecordOpen((open) => !open)}
            />
          )
        ) : undefined}
      />

      {recordOpen ? <RecordEncounterForm onCancel={() => setRecordOpen(false)} onUncertain={() => setRecordUncertain(true)} /> : null}

      <section id="encounters" aria-labelledby="my-counseling-encounters-heading" className={recordOpen ? "mt-5" : undefined}>
          {/* The collection tools step aside while an encounter is being recorded. */}
          {recordOpen ? null : (
          <form action={pathname} method="get" key={searchParams.toString()} role="search" aria-label="Counseling encounters">
          {/* Applying filters keeps the reader's chosen order. */}
          {requestedOrdering ? <input type="hidden" name="ordering" value={requestedOrdering} /> : null}
          <FloatingListTools
            submits
            label="Counseling encounter filters"
            filterCount={[entryMode, deliveryMode, fromDate, toDate].filter(Boolean).length}
            clear={hasFilters ? <Button variant="quiet" onClick={() => router.replace(clearedHref, { scroll: false })}>Clear filters</Button> : undefined}
            filters={<>
            <FilterField label="Origin" htmlFor="counseling-entry-filter"><Select id="counseling-entry-filter" name="entry_mode" defaultValue={entryMode ?? ""}><option value="">All origins</option><option value="APPOINTMENT">Appointment</option><option value="WALK_IN">Walk-in</option><option value="CALLED_IN">Called-in</option><option value="REFERRED">Referred</option></Select></FilterField>
            <FilterField label="Delivery mode" htmlFor="counseling-delivery-filter"><Select id="counseling-delivery-filter" name="delivery_mode" defaultValue={deliveryMode ?? ""}><option value="">All delivery modes</option><option value="IN_PERSON">In person</option><option value="ONLINE">Online</option></Select></FilterField>
            <FilterField label="From date" htmlFor="counseling-from-date"><Input id="counseling-from-date" type="date" name="from_date" defaultValue={fromDate} /></FilterField>
            <FilterField label="To date" htmlFor="counseling-to-date"><Input id="counseling-to-date" type="date" name="to_date" defaultValue={toDate} /></FilterField>
            </>}
          >
            <ListSearchField id="encounter-search" name="search" label="Search Student name, Institutional ID, or Appointment reference" placeholder="Search Student name, Institutional ID, or Appointment reference" defaultValue={search} maxLength={160} />
          </FloatingListTools>
          </form>
          )}

          <Panel as="div">
          <PanelHeader
            title="My counseling encounters"
            titleId="my-counseling-encounters-heading"
            actions={
              <SortField
                id="encounter-sort"
                value={ordering}
                options={encounterOrderingOptions}
                onChange={setOrdering}
              />
            }
            context={encounters.data && !encounters.isError ? describeResultPage({
              count: items.length,
              page: encounters.data.data.page,
              hasNext: encounters.data.data.has_next,
              noun: { one: "encounter", other: "encounters" },
              filtered: hasFilters,
            }) : null}
          />
          {encounters.isPending ? (
            <CounselingListSkeleton label="Loading My Counseling Encounters…" framed={false} />
          ) : encounters.isError ? (
            <PanelMessage role="alert" tone="danger" action={<Button variant="secondary" onClick={() => void encounters.refetch()}>Retry</Button>}>
              {counselingErrorMessage(encounters.error, "My Counseling Encounters could not be loaded.")}
            </PanelMessage>
          ) : items.length === 0 ? (
            <PanelMessage>{hasFilters ? "No counseling encounters match the current filters. Clear or adjust them to broaden the results." : "No counseling encounters are assigned to you yet."}</PanelMessage>
          ) : (
              <div className={dataTable.scroll}>
                <table className={`${dataTable.table} min-w-[850px]`}>
                  <caption className="sr-only">Counseling Encounters assigned to you</caption>
                  <thead className={dataTable.head}><tr><SortableColumnHeader label="Student" ascending={CounselingEncounterOrdering.STUDENT_ASC} descending={CounselingEncounterOrdering.STUDENT_DESC} ascendingLabel="Student A–Z" descendingLabel="Student Z–A" current={ordering} onSort={setOrdering} className={`${dataTable.headerCell} ${dataTable.stickyHeaderCell}`} /><th scope="col" className={dataTable.headerCell}>Origin</th><th scope="col" className={dataTable.headerCell}>Delivery</th><SortableColumnHeader label="Actual start" ascending={CounselingEncounterOrdering.OLDEST_ENCOUNTER} descending={CounselingEncounterOrdering.LATEST_ENCOUNTER} ascendingLabel="Oldest encounter first" descendingLabel="Latest encounter first" firstDirection="descending" current={ordering} onSort={setOrdering} className={dataTable.headerCell} /><th scope="col" className={dataTable.headerCell}>Actual end</th><th scope="col" className={dataTable.headerCell}>Appointment</th></tr></thead>
                  <tbody className={dataTable.body}>
                    {items.map((encounter) => (
                      <tr key={encounter.id} className={dataTable.row}>
                        <th scope="row" className={`${dataTable.cell} ${dataTable.stickyCell} min-w-48 font-normal`}><Link href={`/portal/counseling/encounters/${encounter.id}`} className="font-semibold text-brand underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">{encounter.student.display_name}</Link>{encounter.student.institutional_id ? <span className="mt-1 block text-xs text-muted">{encounter.student.institutional_id}</span> : null}</th>
                        <td className={dataTable.cell}>{counselingEntryModeLabel(encounter.entry_mode)}</td>
                        <td className={dataTable.cell}>{counselingDeliveryModeLabel(encounter.delivery_mode)}</td>
                        <td className={dataTable.cell}>{formatCounselingDateTime(encounter.started_at)}</td>
                        <td className={dataTable.cell}>{formatCounselingDateTime(encounter.ended_at)}</td>
                        <td className={dataTable.cell}>{encounter.appointment?.reference_code ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
          )}
          {!encounters.isPending && !encounters.isError ? <CanonicalPagination className="border-brand-line px-4 py-3 sm:px-5" label="Counseling results pages" page={encounters.data?.data.page ?? page} hasNext={encounters.data?.data.has_next ?? false} onPageChange={(nextPage) => router.push(updateQuery(pathname, new URLSearchParams(searchParams.toString()), "page", String(nextPage)), { scroll: false })} /> : null}
          </Panel>
      </section>
    </div>
  );
}
