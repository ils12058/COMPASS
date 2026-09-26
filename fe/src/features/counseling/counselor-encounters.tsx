"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import type { CounselingAccess } from "@/features/counseling/counseling-access";
import {
  counselingDeliveryModeLabel,
  counselingEntryModeLabel,
  counselingErrorMessage,
  CounselingPageHeading,
  CounselingPagination,
  CounselingQueryError,
} from "@/features/counseling/counseling-shared";
import { RecordEncounterForm } from "@/features/counseling/record-encounter-form";
import {
  CounselingEntryMode,
  DeliveryMode,
} from "@/lib/api/generated/model";
import { useCounselingListMyEncounters } from "@/lib/api/generated/counseling/counseling";

const tableCell = "px-4 py-3 align-top text-sm";

function positivePage(value: string | null): number {
  const parsed = Number.parseInt(value ?? "1", 10);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : 1;
}

function enumParam<T extends string>(value: string | null, allowed: Record<string, T>): T | undefined {
  return value && Object.values(allowed).includes(value as T) ? value as T : undefined;
}

function formatDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? value : new Intl.DateTimeFormat("en-PH", { dateStyle: "medium", timeStyle: "short" }).format(date);
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
        description="Record completed Counseling interactions and review encounters assigned to you."
        action={access.canManageAssigned ? <Button disabled={recordOpen && recordUncertain} onClick={() => { if (recordUncertain) return; setRecordOpen((open) => !open); }}>{recordUncertain ? "Recording result unconfirmed" : recordOpen ? "Close recording" : "Record counseling encounter"}</Button> : undefined}
      />

      {recordOpen ? <RecordEncounterForm onCancel={() => setRecordOpen(false)} onUncertain={() => setRecordUncertain(true)} /> : null}

      {access.canViewAssigned ? (
        <section id="encounters" aria-labelledby="my-counseling-encounters-heading" className="mt-7">
          <h2 id="my-counseling-encounters-heading" className="font-heading text-xl font-semibold text-ink">My counseling encounters</h2>
          <div className="mb-5 mt-4 grid gap-4 border-y border-border py-5 sm:grid-cols-2 lg:grid-cols-4">
            <div className="grid gap-2"><Label htmlFor="counseling-entry-filter">Origin</Label><select id="counseling-entry-filter" value={entryMode ?? "ALL"} onChange={(event) => setFilter("entry_mode", event.target.value === "ALL" ? "" : event.target.value)} className="min-h-10 rounded-md border border-border bg-surface-raised px-3 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"><option value="ALL">All origins</option><option value="APPOINTMENT">Appointment</option><option value="WALK_IN">Walk-in</option><option value="CALLED_IN">Called-in</option><option value="REFERRED">Referred</option></select></div>
            <div className="grid gap-2"><Label htmlFor="counseling-delivery-filter">Delivery mode</Label><select id="counseling-delivery-filter" value={deliveryMode ?? "ALL"} onChange={(event) => setFilter("delivery_mode", event.target.value === "ALL" ? "" : event.target.value)} className="min-h-10 rounded-md border border-border bg-surface-raised px-3 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"><option value="ALL">All delivery modes</option><option value="IN_PERSON">In person</option><option value="ONLINE">Online</option></select></div>
            <div className="grid gap-2"><Label htmlFor="counseling-from-date">From date</Label><Input id="counseling-from-date" type="date" value={fromDate} onChange={(event) => setFilter("from_date", event.target.value)} /></div>
            <div className="grid gap-2"><Label htmlFor="counseling-to-date">To date</Label><Input id="counseling-to-date" type="date" value={toDate} onChange={(event) => setFilter("to_date", event.target.value)} /></div>
            {hasFilters ? <div className="sm:col-span-2 lg:col-span-4"><Button variant="quiet" onClick={() => router.replace(pathname, { scroll: false })}>Clear filters</Button></div> : null}
          </div>

          {encounters.isPending ? (
            <div aria-busy="true" className="space-y-2 py-3"><span className="sr-only">Loading My Counseling Encounters…</span><Skeleton className="h-14 w-full" /><Skeleton className="h-14 w-full" /><Skeleton className="h-14 w-full" /></div>
          ) : encounters.isError ? (
            <CounselingQueryError message={counselingErrorMessage(encounters.error, "My Counseling Encounters could not be loaded.")} onRetry={() => void encounters.refetch()} />
          ) : items.length === 0 ? (
            <p className="border-y border-border py-6 text-sm text-muted">{hasFilters ? "No Counseling Encounters match the current filters. Clear or adjust them to broaden the results." : "There are no Counseling Encounters assigned to you yet."}</p>
          ) : (
            <>
              <div className="overflow-x-auto border-y border-border">
                <table className="w-full min-w-[850px] border-separate border-spacing-0 text-left">
                  <caption className="sr-only">Counseling Encounters assigned to you</caption>
                  <thead className="bg-surface-muted text-xs font-semibold uppercase tracking-wide text-muted"><tr><th scope="col" className={`${tableCell} sticky left-0 z-20 bg-surface-muted`}>Student</th><th scope="col" className={tableCell}>Origin</th><th scope="col" className={tableCell}>Delivery</th><th scope="col" className={tableCell}>Actual start</th><th scope="col" className={tableCell}>Actual end</th><th scope="col" className={tableCell}>Appointment</th></tr></thead>
                  <tbody className="divide-y divide-border">
                    {items.map((encounter) => (
                      <tr key={encounter.id} className="group hover:bg-surface-muted/50">
                        <th scope="row" className={`${tableCell} sticky left-0 z-10 min-w-48 bg-surface-raised font-normal group-hover:bg-surface-muted`}><Link href={`/portal/counseling/encounters/${encounter.id}`} className="font-semibold text-brand underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">{encounter.student.display_name}</Link><span className="mt-1 block text-xs text-muted">View encounter</span></th>
                        <td className={tableCell}>{counselingEntryModeLabel(encounter.entry_mode)}</td>
                        <td className={tableCell}>{counselingDeliveryModeLabel(encounter.delivery_mode)}</td>
                        <td className={tableCell}>{formatDate(encounter.started_at)}</td>
                        <td className={tableCell}>{formatDate(encounter.ended_at)}</td>
                        <td className={tableCell}>{encounter.appointment?.reference_code ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <CounselingPagination page={encounters.data?.data.page ?? page} hasNext={encounters.data?.data.has_next ?? false} onPageChange={(nextPage) => router.push(updateQuery(pathname, new URLSearchParams(searchParams.toString()), "page", String(nextPage)), { scroll: false })} />
            </>
          )}
        </section>
      ) : access.canManageAssigned ? (
        <p className="mt-5 text-sm text-muted">Your current access allows recording completed Counseling Encounters but does not include viewing the assigned encounter list.</p>
      ) : null}
    </div>
  );
}
