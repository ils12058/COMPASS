"use client";

import { ChevronRight, Plus } from "lucide-react";
import { useMemo, useRef, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import {
  formatUnavailabilityRange,
  modeScopeLabel,
} from "@/features/availability/availability-shared";
import { focusHeading } from "@/lib/focus-heading";
import {
  AvailabilityModeScope,
  type ExceptionCreateRequest,
  type ExceptionResponse,
} from "@/lib/api/generated/model";
import {
  INSTITUTION_TIME_ZONE_LABEL,
  institutionalDateTimeInputToISO,
} from "@/lib/institutional-time";

function ExceptionRows({
  items,
  canRemove,
  pending,
  onRemove,
}: {
  items: ExceptionResponse[];
  canRemove: boolean;
  pending: boolean;
  onRemove: (item: ExceptionResponse) => void;
}) {
  return (
    <ul className="divide-y divide-border">
      {items.map((item) => {
        const range = formatUnavailabilityRange(item.starts_at, item.ends_at);
        return (
          <li key={item.id} className="flex items-start justify-between gap-3 px-4 py-3 sm:px-5">
            <div className="min-w-0">
              <p className="text-sm font-semibold text-ink">{range}</p>
              <p className="text-sm text-muted">{modeScopeLabel(item.mode_scope)}</p>
              {item.reason.trim() ? (
                <p className="mt-1 whitespace-pre-wrap break-words text-sm leading-6 text-muted">{item.reason}</p>
              ) : null}
            </div>
            {canRemove ? (
              <Button
                variant="quiet"
                className="-mr-2 shrink-0 px-2.5"
                disabled={pending}
                aria-label={`Remove unavailability ${range}`}
                onClick={() => onRemove(item)}
              >
                Remove
              </Button>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}

// Dated periods that take time out of the recurring hours. Upcoming periods are always listed;
// past ones fold away under a count. Adding happens in a dialog that stays open on failure; the
// page announces a successful add. Removing confirms, then shows its outcome in the same dialog.
export function UnavailabilitySection({
  items,
  canCreate,
  canRemove,
  createPending,
  removePending,
  error,
  onCreate,
  onRemove,
  onResetError,
}: {
  items: ExceptionResponse[];
  canCreate: boolean;
  canRemove: boolean;
  createPending: boolean;
  removePending: boolean;
  error: string | null;
  onCreate: (payload: ExceptionCreateRequest) => Promise<boolean>;
  onRemove: (id: string) => Promise<boolean>;
  onResetError: () => void;
}) {
  const [addOpen, setAddOpen] = useState(false);
  const [removal, setRemoval] = useState<ExceptionResponse | null>(null);
  const [removed, setRemoved] = useState(false);
  const [startsAt, setStartsAt] = useState("");
  const [endsAt, setEndsAt] = useState("");
  const [modeScope, setModeScope] = useState<AvailabilityModeScope>(AvailabilityModeScope.ALL);
  const [reason, setReason] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);
  const addButton = useRef<HTMLButtonElement>(null);

  const [now] = useState(() => Date.now());
  const upcoming = useMemo(
    () =>
      items.filter((item) => {
        const end = new Date(item.ends_at).getTime();
        return !Number.isNaN(end) && end >= now;
      }),
    [items, now],
  );
  const past = useMemo(
    () =>
      items
        .filter((item) => {
          const end = new Date(item.ends_at).getTime();
          return !Number.isNaN(end) && end < now;
        })
        .slice()
        .reverse(),
    [items, now],
  );

  function resetCreateForm() {
    setStartsAt("");
    setEndsAt("");
    setModeScope(AvailabilityModeScope.ALL);
    setReason("");
    setLocalError(null);
  }

  async function submitCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLocalError(null);

    const startsIso = institutionalDateTimeInputToISO(startsAt);
    const endsIso = institutionalDateTimeInputToISO(endsAt);
    if (!startsIso || !endsIso) {
      setLocalError("Enter a valid start and end date/time.");
      return;
    }
    if (new Date(startsIso).getTime() >= new Date(endsIso).getTime()) {
      setLocalError("The start date/time must be earlier than the end date/time.");
      return;
    }

    const saved = await onCreate({ starts_at: startsIso, ends_at: endsIso, mode_scope: modeScope, reason });
    if (saved) {
      setAddOpen(false);
      resetCreateForm();
    }
  }

  async function confirmRemoval() {
    if (!removal) return;
    if (await onRemove(removal.id)) setRemoved(true);
  }

  const mutationPending = createPending || removePending;
  const removalRange = removal ? formatUnavailabilityRange(removal.starts_at, removal.ends_at) : "";

  return (
    <Panel aria-labelledby="unavailability-heading">
      <PanelHeader
        title="Unavailability"
        titleId="unavailability-heading"
        actions={canCreate ? (
          <Button
            ref={addButton}
            variant="secondary"
            className="px-3"
            onClick={() => {
              setLocalError(null);
              onResetError();
              setAddOpen(true);
            }}
          >
            <Plus size={16} aria-hidden="true" />
            Add<span className="sr-only"> unavailability</span>
          </Button>
        ) : undefined}
      />

      {/* Kept out of the title band so Add stays beside the title in a narrow column. */}
      <p className="border-b border-border px-4 py-2.5 text-sm leading-6 text-muted sm:px-5">
        Dated unavailability removes future bookable time from recurring Availability. Existing
        Appointments remain scheduled. Times use {INSTITUTION_TIME_ZONE_LABEL}.
      </p>

      {items.length === 0 ? (
        <PanelMessage>No unavailability has been recorded.</PanelMessage>
      ) : (
        <>
          <section aria-labelledby="upcoming-unavailability-heading">
            <h3
              id="upcoming-unavailability-heading"
              className="px-4 pt-3 text-xs font-semibold uppercase tracking-wide text-muted sm:px-5"
            >
              Upcoming
            </h3>
            {upcoming.length > 0 ? (
              <ExceptionRows items={upcoming} canRemove={canRemove} pending={mutationPending} onRemove={(item) => {
                onResetError();
                setRemoved(false);
                setRemoval(item);
              }} />
            ) : (
              <p className="px-4 pb-3 pt-1 text-sm text-muted sm:px-5">No upcoming unavailability.</p>
            )}
          </section>
          {past.length > 0 ? (
            <details className="group border-t border-border">
              <summary className="flex min-h-11 cursor-pointer list-none items-center gap-1.5 px-4 text-sm font-semibold text-muted hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-focus sm:px-5 [&::-webkit-details-marker]:hidden">
                <ChevronRight size={16} aria-hidden="true" className="transition-transform group-open:rotate-90 motion-reduce:transition-none" />
                Past · {past.length}
              </summary>
              <div className="border-t border-border">
                <ExceptionRows items={past} canRemove={canRemove} pending={mutationPending} onRemove={(item) => {
                  onResetError();
                  setRemoved(false);
                  setRemoval(item);
                }} />
              </div>
            </details>
          ) : null}
        </>
      )}

      <Dialog
        open={addOpen}
        onOpenChange={(open) => {
          setAddOpen(open);
          if (!open) setLocalError(null);
        }}
      >
        <DialogContent dismissible={!createPending}>
          <DialogTitle>Add unavailability</DialogTitle>
          <DialogDescription>
            Add a dated period that should be removed from recurring Availability.
            This changes future bookable time only; existing Appointments in this
            period remain scheduled.
          </DialogDescription>
          <form className="mt-6 space-y-5" onSubmit={submitCreate}>
            <div className="grid gap-2">
              <Label htmlFor="unavailability-from">From</Label>
              <Input
                id="unavailability-from"
                type="datetime-local"
                required
                value={startsAt}
                aria-describedby="unavailability-timezone-help"
                onChange={(event) => setStartsAt(event.target.value)}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="unavailability-until">Until</Label>
              <Input
                id="unavailability-until"
                type="datetime-local"
                required
                value={endsAt}
                aria-describedby="unavailability-timezone-help"
                onChange={(event) => setEndsAt(event.target.value)}
              />
            </div>
            <p id="unavailability-timezone-help" className="text-xs leading-5 text-muted">
              From and Until use {INSTITUTION_TIME_ZONE_LABEL}.
            </p>
            <div className="grid gap-2">
              <Label htmlFor="unavailability-mode">Applies to</Label>
              <Select
                id="unavailability-mode"
                value={modeScope}
                onChange={(event) => setModeScope(event.target.value as AvailabilityModeScope)}
              >
                <option value={AvailabilityModeScope.ALL}>{modeScopeLabel(AvailabilityModeScope.ALL)}</option>
                <option value={AvailabilityModeScope.IN_PERSON}>{modeScopeLabel(AvailabilityModeScope.IN_PERSON)}</option>
                <option value={AvailabilityModeScope.ONLINE}>{modeScopeLabel(AvailabilityModeScope.ONLINE)}</option>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="unavailability-reason">
                Reason <span className="font-normal text-muted">(optional)</span>
              </Label>
              <Textarea
                id="unavailability-reason"
                rows={4}
                value={reason}
                onChange={(event) => setReason(event.target.value)}
              />
            </div>
            {localError || error ? (
              <p role="alert" className="text-sm text-danger">
                {localError ?? error}
              </p>
            ) : null}
            <div className="flex justify-end gap-2">
              <Button variant="secondary" disabled={createPending} onClick={() => setAddOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createPending}>
                {createPending ? "Adding…" : "Add unavailability"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      <ConsequentialActionDialog
        open={removal !== null}
        title="Remove this unavailability?"
        confirmLabel="Remove unavailability"
        pendingLabel="Removing…"
        pending={removePending}
        error={error}
        variant="danger"
        completed={removed ? {
          title: "Unavailability removed",
          children: <p>{removalRange} no longer subtracts time from Availability.</p>,
        } : null}
        onOpenChange={(open) => {
          if (!open) setRemoval(null);
        }}
        onConfirm={() => void confirmRemoval()}
        onCloseAutoFocus={(event) => {
          if (!removed) return;
          // The removed period's Remove button is gone; keep focus on this region.
          event.preventDefault();
          if (addButton.current) addButton.current.focus();
          else focusHeading("unavailability-heading");
        }}
      >
        <p>
          {removal ? removalRange + " will no longer subtract time from Availability." : "This unavailability will be removed."}
        </p>
      </ConsequentialActionDialog>
    </Panel>
  );
}
