"use client";

import { useMemo, useState, type FormEvent } from "react";

import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  ActionFeedback,
  availabilitySelectClass,
  modeScopeLabel,
  type StepUpHooks,
} from "@/features/availability/availability-shared";
import {
  AvailabilityModeScope,
  type ExceptionCreateRequest,
  type ExceptionResponse,
} from "@/lib/api/generated/model";

function formatDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Date unavailable";
  return new Intl.DateTimeFormat("en-PH", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function toAwareIso(value: string): string | null {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

function ExceptionList({
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
  if (items.length === 0) return null;

  return (
    <ul className="divide-y divide-border border-y border-border">
      {items.map((item) => (
        <li
          key={item.id}
          className="grid gap-4 py-4 md:grid-cols-[minmax(0,1fr)_auto] md:items-start"
        >
          <div className="min-w-0">
            <p className="font-medium text-ink">
              {formatDateTime(item.starts_at)} – {formatDateTime(item.ends_at)}
            </p>
            <p className="mt-1 text-sm text-muted">
              {modeScopeLabel(item.mode_scope)}
            </p>
            {item.reason.trim() ? (
              <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-muted">
                {item.reason}
              </p>
            ) : null}
          </div>
          {canRemove ? (
            <Button
              variant="quiet"
              disabled={pending}
              onClick={() => onRemove(item)}
            >
              Remove
            </Button>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

export function UnavailabilitySection({
  items,
  canCreate,
  canRemove,
  administrative,
  createPending,
  removePending,
  error,
  notice,
  onCreate,
  onRemove,
}: {
  items: ExceptionResponse[];
  canCreate: boolean;
  canRemove: boolean;
  administrative: boolean;
  createPending: boolean;
  removePending: boolean;
  error: string | null;
  notice: string | null;
  onCreate: (
    payload: ExceptionCreateRequest,
    hooks?: StepUpHooks,
  ) => Promise<boolean>;
  onRemove: (id: string, hooks?: StepUpHooks) => Promise<boolean>;
}) {
  const [addOpen, setAddOpen] = useState(false);
  const [removal, setRemoval] = useState<ExceptionResponse | null>(null);
  const [startsAt, setStartsAt] = useState("");
  const [endsAt, setEndsAt] = useState("");
  const [modeScope, setModeScope] = useState<AvailabilityModeScope>(
    AvailabilityModeScope.ALL,
  );
  const [reason, setReason] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);

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

    const startsIso = toAwareIso(startsAt);
    const endsIso = toAwareIso(endsAt);
    if (!startsIso || !endsIso) {
      setLocalError("Enter a valid start and end date/time.");
      return;
    }
    if (new Date(startsIso).getTime() >= new Date(endsIso).getTime()) {
      setLocalError("The start date/time must be earlier than the end date/time.");
      return;
    }

    const saved = await onCreate(
      {
        starts_at: startsIso,
        ends_at: endsIso,
        mode_scope: modeScope,
        reason,
      },
      administrative
        ? {
            onStepUpRequired: () => setAddOpen(false),
            onStepUpVerified: () => setAddOpen(true),
          }
        : undefined,
    );

    if (saved) {
      setAddOpen(false);
      resetCreateForm();
    }
  }

  async function confirmRemoval() {
    if (!removal) return;
    const target = removal;

    const removed = await onRemove(
      target.id,
      administrative
        ? {
            onStepUpRequired: () => setRemoval(null),
            onStepUpVerified: () => setRemoval(target),
          }
        : undefined,
    );

    if (removed) setRemoval(null);
  }

  const mutationPending = createPending || removePending;
  const modalOpen = addOpen || removal !== null;

  return (
    <section aria-labelledby="unavailability-heading">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2
            id="unavailability-heading"
            className="font-heading text-2xl font-semibold text-ink"
          >
            Unavailability
          </h2>
          <p className="mt-2 text-sm text-muted">
            Dated unavailability removes time from recurring Availability.
          </p>
        </div>
        {canCreate ? (
          <Button
            onClick={() => {
              setLocalError(null);
              setAddOpen(true);
            }}
          >
            Add unavailability
          </Button>
        ) : null}
      </div>

      {!modalOpen ? <ActionFeedback error={error} notice={notice} /> : null}

      {items.length === 0 ? (
        <p className="mt-5 border-y border-border py-7 text-sm text-muted">
          No unavailability has been recorded.
        </p>
      ) : (
        <div className="mt-5 space-y-8">
          {upcoming.length > 0 ? (
            <section aria-labelledby="upcoming-unavailability-heading">
              <h3
                id="upcoming-unavailability-heading"
                className="mb-3 font-semibold text-ink"
              >
                Upcoming
              </h3>
              <ExceptionList
                items={upcoming}
                canRemove={canRemove}
                pending={mutationPending}
                onRemove={setRemoval}
              />
            </section>
          ) : null}

          {past.length > 0 ? (
            <section aria-labelledby="past-unavailability-heading">
              <h3
                id="past-unavailability-heading"
                className="mb-3 font-semibold text-ink"
              >
                Past
              </h3>
              <ExceptionList
                items={past}
                canRemove={canRemove}
                pending={mutationPending}
                onRemove={setRemoval}
              />
            </section>
          ) : null}
        </div>
      )}

      <Dialog
        open={addOpen}
        onOpenChange={(open) => {
          if (createPending) return;
          setAddOpen(open);
          if (!open && !administrative) setLocalError(null);
        }}
      >
        <DialogContent>
          <DialogTitle>Add unavailability</DialogTitle>
          <DialogDescription>
            Add a dated period that should be removed from recurring Availability.
          </DialogDescription>
          <form className="mt-6 space-y-5" onSubmit={submitCreate}>
            <div className="grid gap-2">
              <Label htmlFor="unavailability-from">From</Label>
              <Input
                id="unavailability-from"
                type="datetime-local"
                required
                value={startsAt}
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
                onChange={(event) => setEndsAt(event.target.value)}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="unavailability-mode">Applies to</Label>
              <select
                id="unavailability-mode"
                className={availabilitySelectClass}
                value={modeScope}
                onChange={(event) =>
                  setModeScope(event.target.value as AvailabilityModeScope)
                }
              >
                <option value={AvailabilityModeScope.ALL}>
                  {modeScopeLabel(AvailabilityModeScope.ALL)}
                </option>
                <option value={AvailabilityModeScope.IN_PERSON}>
                  {modeScopeLabel(AvailabilityModeScope.IN_PERSON)}
                </option>
                <option value={AvailabilityModeScope.ONLINE}>
                  {modeScopeLabel(AvailabilityModeScope.ONLINE)}
                </option>
              </select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="unavailability-reason">
                Reason <span className="font-normal text-muted">(optional)</span>
              </Label>
              <textarea
                id="unavailability-reason"
                rows={4}
                className="w-full rounded-md border border-border bg-surface-raised px-3 py-2 text-sm leading-6 text-ink outline-none placeholder:text-muted focus:border-focus focus:ring-2 focus:ring-focus/25"
                value={reason}
                onChange={(event) => setReason(event.target.value)}
              />
            </div>
            {localError ? (
              <p role="alert" className="text-sm text-danger">
                {localError}
              </p>
            ) : null}
            <ActionFeedback error={error} notice={notice} />
            <div className="flex justify-end gap-2">
              <Button
                variant="secondary"
                disabled={createPending}
                onClick={() => setAddOpen(false)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={createPending}>
                {createPending ? "Adding…" : "Add unavailability"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      <AlertDialog
        open={removal !== null}
        onOpenChange={(open) => {
          if (removePending) return;
          if (!open) setRemoval(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogTitle>Remove this unavailability?</AlertDialogTitle>
          <AlertDialogDescription>
            {removal
              ? formatDateTime(removal.starts_at) +
                " – " +
                formatDateTime(removal.ends_at) +
                " will no longer subtract time from Availability."
              : "This unavailability will be removed."}
          </AlertDialogDescription>
          <ActionFeedback error={error} notice={notice} />
          <div className="mt-6 flex justify-end gap-2">
            <AlertDialogCancel asChild>
              <Button variant="secondary" disabled={removePending}>
                Cancel
              </Button>
            </AlertDialogCancel>
            <Button
              variant="danger"
              disabled={removePending}
              onClick={() => void confirmRemoval()}
            >
              {removePending ? "Removing…" : "Remove unavailability"}
            </Button>
          </div>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  );
}
