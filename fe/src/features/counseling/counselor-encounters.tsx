"use client";

import { CircleAlert, NotebookPen, X } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { dataTable } from "@/components/ui/data-table";
import { FilterField } from "@/components/ui/filter-toolbar";
import { FloatingListTools } from "@/components/ui/floating-list-tools";
import { Input } from "@/components/ui/input";
import { PageAction } from "@/components/ui/page-action";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
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
  formatCounselingDateTime,
} from "@/features/counseling/counseling-shared";
import { RecordEncounterForm } from "@/features/counseling/record-encounter-form";
import {
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
  const hasFilters = Boolean(entryMode || deliveryMode || fromDate || toDate);
  const encounters = useCounselingListMyEncounters(
    {
      ...(entryMode ? { entry_mode: entryMode } : {}),
      ...(deliveryMode ? { delivery_mode: deliveryMode } : {}),
      ...(fromDate ? { from_date: fromDate } : {}),
      ...(toDate ? { to_date: toDate } : {}),
      page,
      page_size: 20,
    },
    { query: { enabled: access.canViewAssigned, retry: false } },
  );
  const items = encounters.data?.data.items ?? [];

  function setFilter(name: string, value: string) {
    router.replace(updateQuery(pathname, new URLSearchParams(searchParams.toString()), name, value), { scroll: false });
  }

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
          {/* Selects and dates only, so each choice applies as soon as it changes. The tools step
              aside while an encounter is being recorded, so they never sit over that form. */}
          {recordOpen ? null : (
          <FloatingListTools
            label="Counseling encounter filters"
            filterCount={[entryMode, deliveryMode, fromDate, toDate].filter(Boolean).length}
            clear={hasFilters ? <Button variant="quiet" onClick={() => router.replace(pathname, { scroll: false })}>Clear filters</Button> : undefined}
            filters={<>
            <FilterField label="Origin" htmlFor="counseling-entry-filter"><Select id="counseling-entry-filter" value={entryMode ?? "ALL"} onChange={(event) => setFilter("entry_mode", event.target.value === "ALL" ? "" : event.target.value)}><option value="ALL">All origins</option><option value="APPOINTMENT">Appointment</option><option value="WALK_IN">Walk-in</option><option value="CALLED_IN">Called-in</option><option value="REFERRED">Referred</option></Select></FilterField>
            <FilterField label="Delivery mode" htmlFor="counseling-delivery-filter"><Select id="counseling-delivery-filter" value={deliveryMode ?? "ALL"} onChange={(event) => setFilter("delivery_mode", event.target.value === "ALL" ? "" : event.target.value)}><option value="ALL">All delivery modes</option><option value="IN_PERSON">In person</option><option value="ONLINE">Online</option></Select></FilterField>
            <FilterField label="From date" htmlFor="counseling-from-date"><Input id="counseling-from-date" type="date" value={fromDate} onChange={(event) => setFilter("from_date", event.target.value)} /></FilterField>
            <FilterField label="To date" htmlFor="counseling-to-date"><Input id="counseling-to-date" type="date" value={toDate} onChange={(event) => setFilter("to_date", event.target.value)} /></FilterField>
            </>}
          />
          )}

          <Panel as="div">
          <PanelHeader
            title="My counseling encounters"
            titleId="my-counseling-encounters-heading"
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
                  <thead className={dataTable.head}><tr><th scope="col" className={`${dataTable.headerCell} ${dataTable.stickyHeaderCell}`}>Student</th><th scope="col" className={dataTable.headerCell}>Origin</th><th scope="col" className={dataTable.headerCell}>Delivery</th><th scope="col" className={dataTable.headerCell}>Actual start</th><th scope="col" className={dataTable.headerCell}>Actual end</th><th scope="col" className={dataTable.headerCell}>Appointment</th></tr></thead>
                  <tbody className={dataTable.body}>
                    {items.map((encounter) => (
                      <tr key={encounter.id} className={dataTable.row}>
                        <th scope="row" className={`${dataTable.cell} ${dataTable.stickyCell} min-w-48 font-normal`}><Link href={`/portal/counseling/encounters/${encounter.id}`} className="font-semibold text-brand underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">{encounter.student.display_name}</Link><span className="mt-1 block text-xs text-muted">View encounter</span></th>
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
