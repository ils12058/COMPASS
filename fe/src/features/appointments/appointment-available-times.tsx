import { Button } from "@/components/ui/button";
import { LoadingRegion } from "@/components/ui/loading-region";
import { Notice } from "@/components/ui/notice";
import { Skeleton } from "@/components/ui/skeleton";
import type { BookableSlotResponse } from "@/lib/api/generated/model";
import { INSTITUTION_TIME_ZONE, INSTITUTION_TIME_ZONE_LABEL } from "@/lib/institutional-time";
import { formatAppointmentTime } from "./appointments-shared";
import { SLOT_NO_LONGER_AVAILABLE, SLOTS_NOT_RECHECKED } from "./appointment-slot-freshness";

// Presentation only: each flow retains its own canonical query, selection, and submission checks.
export function AppointmentAvailableTimes({
  date, items, selected, timezone = INSTITUTION_TIME_ZONE, pending, fetching, failed,
  unconfirmed, lost, error, disabled = false, replacement = false, onSelect, onRefresh,
}: {
  date: string;
  items: BookableSlotResponse[];
  selected: string | null;
  timezone?: string;
  pending: boolean;
  fetching: boolean;
  failed: boolean;
  unconfirmed: boolean;
  lost: boolean;
  error?: string | null;
  disabled?: boolean;
  replacement?: boolean;
  onSelect: (startsAt: string) => void;
  onRefresh: () => void;
}) {
  return <section aria-label={replacement ? "Replacement times" : "Appointment times"} className="min-w-0">
    <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
      <h4 className="text-sm font-semibold text-ink">Available times · {timezone === INSTITUTION_TIME_ZONE ? INSTITUTION_TIME_ZONE_LABEL : timezone}</h4>
      {date ? <Button variant="quiet" disabled={disabled || fetching} onClick={onRefresh}>Refresh times</Button> : null}
    </div>
    {error ? <p role="alert" className="mb-3 text-sm text-danger">{error}</p> : lost ? <p role="status" className="mb-3 text-sm text-warning">{SLOT_NO_LONGER_AVAILABLE}</p> : null}
    {!date ? <p className="text-sm text-muted">Select a date to see available times.</p> : pending ? (
      <LoadingRegion label={replacement ? "Loading replacement times…" : "Loading available times…"} className="flex flex-wrap gap-2">
        <Skeleton className="h-11 w-24" /><Skeleton className="h-11 w-24" /><Skeleton className="h-11 w-24" />
      </LoadingRegion>
    ) : failed && !unconfirmed ? (
      <div role="alert">
        <p className="text-sm text-danger">Couldn&apos;t load {replacement ? "replacement" : "available"} times. Try again.</p>
        <Button className="mt-3" variant="secondary" disabled={disabled || fetching} onClick={onRefresh}>Retry</Button>
      </div>
    ) : <>
      {unconfirmed ? <Notice role="status" tone="warning" className="mb-3" action={<Button variant="secondary" disabled={disabled || fetching} onClick={onRefresh}>{fetching ? "Retrying…" : "Retry"}</Button>}>{SLOTS_NOT_RECHECKED}</Notice> : fetching ? <p role="status" className="mb-3 text-sm text-muted">Checking available times…</p> : null}
      {items.length === 0 ? <p role="status" className="text-sm text-muted">{replacement ? "No times are available. Choose another date." : "No available Appointment times were found for this date. Choose another date."}</p> : <>
        <div role="group" aria-label={replacement ? "Available replacement times" : "Available Appointment times"} className="flex flex-wrap gap-2">
          {items.map((slot) => <Button key={slot.starts_at} variant={selected === slot.starts_at ? "primary" : "secondary"} disabled={disabled || unconfirmed} aria-pressed={selected === slot.starts_at} onClick={() => onSelect(slot.starts_at)}>
            {formatAppointmentTime(slot.starts_at, timezone)}
          </Button>)}
        </div>
        <p className="mt-3 text-sm text-muted">{selected ? `Selected time: ${formatAppointmentTime(selected, timezone)}` : "Choose an available time."}</p>
      </>}
    </>}
  </section>;
}
