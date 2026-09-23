"use client";

import { useState } from "react";

import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  ActionFeedback,
  availabilitySelectClass,
  modeScopeLabel,
  type StepUpHooks,
  weeklyWindowLabel,
} from "@/features/availability/availability-shared";
import {
  AvailabilityModeScope,
  Weekday,
  type WeeklyWindowRequest,
  type WeeklyWindowResponse,
} from "@/lib/api/generated/model";

type DraftWindow = {
  key: string;
  weekday: Weekday;
  start_time: string;
  end_time: string;
  mode_scope: AvailabilityModeScope;
};

const weekdayOrder: Weekday[] = [
  Weekday.MONDAY,
  Weekday.TUESDAY,
  Weekday.WEDNESDAY,
  Weekday.THURSDAY,
  Weekday.FRIDAY,
  Weekday.SATURDAY,
  Weekday.SUNDAY,
];

const weekdayLabels: Record<Weekday, string> = {
  [Weekday.MONDAY]: "Monday",
  [Weekday.TUESDAY]: "Tuesday",
  [Weekday.WEDNESDAY]: "Wednesday",
  [Weekday.THURSDAY]: "Thursday",
  [Weekday.FRIDAY]: "Friday",
  [Weekday.SATURDAY]: "Saturday",
  [Weekday.SUNDAY]: "Sunday",
};

function createKey(): string {
  return (
    Date.now().toString(36) +
    "-" +
    Math.random().toString(36).slice(2, 9)
  );
}

function draftFromWindows(windows: WeeklyWindowResponse[]): DraftWindow[] {
  return windows.map((window) => ({
    key: window.id,
    weekday: window.weekday,
    start_time: window.start_time.slice(0, 5),
    end_time: window.end_time.slice(0, 5),
    mode_scope: window.mode_scope,
  }));
}

function scopesOverlap(
  left: AvailabilityModeScope,
  right: AvailabilityModeScope,
): boolean {
  return (
    left === right ||
    left === AvailabilityModeScope.ALL ||
    right === AvailabilityModeScope.ALL
  );
}

function validateDraft(draft: DraftWindow[]): string | null {
  for (const window of draft) {
    if (!window.start_time || !window.end_time) {
      return "Each recurring window needs a start and end time.";
    }
    if (window.start_time >= window.end_time) {
      return (
        weekdayLabels[window.weekday] +
        " contains a window whose start time is not earlier than its end time."
      );
    }
  }

  for (const weekday of weekdayOrder) {
    const rows = draft.filter((window) => window.weekday === weekday);
    for (let leftIndex = 0; leftIndex < rows.length; leftIndex += 1) {
      for (
        let rightIndex = leftIndex + 1;
        rightIndex < rows.length;
        rightIndex += 1
      ) {
        const left = rows[leftIndex];
        const right = rows[rightIndex];
        const timeOverlap =
          left.start_time < right.end_time &&
          right.start_time < left.end_time;
        if (
          timeOverlap &&
          scopesOverlap(left.mode_scope, right.mode_scope)
        ) {
          return (
            weekdayLabels[weekday] +
            " contains overlapping windows for the same delivery-mode context."
          );
        }
      }
    }
  }

  return null;
}

function requestFromDraft(draft: DraftWindow[]): WeeklyWindowRequest[] {
  return draft.map((window) => ({
    weekday: window.weekday,
    start_time: window.start_time,
    end_time: window.end_time,
    mode_scope: window.mode_scope,
  }));
}

export function WeeklyScheduleEditor({
  windows,
  canMutate,
  cleanupOnly = false,
  pending,
  error,
  notice,
  onSave,
}: {
  windows: WeeklyWindowResponse[];
  canMutate: boolean;
  cleanupOnly?: boolean;
  pending: boolean;
  error: string | null;
  notice: string | null;
  onSave: (
    windows: WeeklyWindowRequest[],
    hooks?: StepUpHooks,
  ) => Promise<boolean>;
}) {
  const [draft, setDraft] = useState<DraftWindow[]>(() =>
    draftFromWindows(windows),
  );
  const [dirty, setDirty] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const [clearOpen, setClearOpen] = useState(false);

  function updateWindow(
    key: string,
    changes: Partial<Omit<DraftWindow, "key" | "weekday">>,
  ) {
    setLocalError(null);
    setDirty(true);
    setDraft((current) =>
      current.map((window) =>
        window.key === key ? { ...window, ...changes } : window,
      ),
    );
  }

  function addWindow(weekday: Weekday) {
    setLocalError(null);
    setDirty(true);
    setDraft((current) => [
      ...current,
      {
        key: createKey(),
        weekday,
        start_time: "08:00",
        end_time: "17:00",
        mode_scope: AvailabilityModeScope.ALL,
      },
    ]);
  }

  function removeWindow(key: string) {
    setLocalError(null);
    setDirty(true);
    setDraft((current) => current.filter((window) => window.key !== key));
  }

  async function save() {
    const validation = validateDraft(draft);
    if (validation) {
      setLocalError(validation);
      return;
    }

    const saved = await onSave(requestFromDraft(draft));
    if (saved) {
      setDirty(false);
      setLocalError(null);
    }
  }

  async function clearSchedule() {
    const saved = await onSave([], {
      onStepUpRequired: () => setClearOpen(false),
      onStepUpVerified: () => setClearOpen(true),
    });
    if (saved) {
      setClearOpen(false);
      setDirty(false);
      setLocalError(null);
    }
  }

  if (cleanupOnly) {
    return (
      <section aria-labelledby="weekly-schedule-heading">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2
              id="weekly-schedule-heading"
              className="font-heading text-2xl font-semibold text-ink"
            >
              Weekly schedule
            </h2>
            <p className="mt-2 text-sm text-muted">
              Existing recurring Availability may be reviewed or removed.
            </p>
          </div>
          {canMutate && windows.length > 0 ? (
            <Button variant="danger" onClick={() => setClearOpen(true)}>
              Clear weekly schedule
            </Button>
          ) : null}
        </div>

        {windows.length === 0 ? (
          <p className="mt-5 border-y border-border py-7 text-sm text-muted">
            No recurring Availability has been configured.
          </p>
        ) : (
          <div className="mt-5 divide-y divide-border border-y border-border">
            {weekdayOrder.map((weekday) => {
              const rows = windows.filter(
                (window) => window.weekday === weekday,
              );
              if (rows.length === 0) return null;
              return (
                <section key={weekday} className="py-4">
                  <h3 className="font-semibold text-ink">
                    {weekdayLabels[weekday]}
                  </h3>
                  <ul className="mt-2 space-y-1 text-sm text-muted">
                    {rows.map((window) => (
                      <li key={window.id}>{weeklyWindowLabel(window)}</li>
                    ))}
                  </ul>
                </section>
              );
            })}
          </div>
        )}

        <ActionFeedback error={error} notice={notice} />

        <AlertDialog
          open={clearOpen}
          onOpenChange={(open) => {
            if (pending) return;
            setClearOpen(open);
          }}
        >
          <AlertDialogContent>
            <AlertDialogTitle>Clear the complete weekly schedule?</AlertDialogTitle>
            <AlertDialogDescription>
              This removes every recurring Availability window for this provider.
              Historical unavailability records are not removed.
            </AlertDialogDescription>
            <ActionFeedback error={error} notice={notice} />
            <div className="mt-6 flex justify-end gap-2">
              <AlertDialogCancel asChild>
                <Button variant="secondary" disabled={pending}>
                  Cancel
                </Button>
              </AlertDialogCancel>
              <Button
                variant="danger"
                disabled={pending}
                onClick={() => void clearSchedule()}
              >
                {pending ? "Clearing…" : "Clear weekly schedule"}
              </Button>
            </div>
          </AlertDialogContent>
        </AlertDialog>
      </section>
    );
  }

  return (
    <section aria-labelledby="weekly-schedule-heading">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2
            id="weekly-schedule-heading"
            className="font-heading text-2xl font-semibold text-ink"
          >
            Weekly schedule
          </h2>
          <p className="mt-2 text-sm text-muted">
            Saving replaces the complete recurring weekly configuration.
          </p>
        </div>
        {canMutate ? (
          <Button
            disabled={pending || !dirty}
            onClick={() => void save()}
          >
            {pending ? "Saving…" : "Save weekly schedule"}
          </Button>
        ) : null}
      </div>

      <div className="mt-5 divide-y divide-border border-y border-border">
        {weekdayOrder.map((weekday) => {
          const rows = draft.filter((window) => window.weekday === weekday);

          return (
            <section key={weekday} className="py-5" aria-labelledby={"weekday-" + weekday}>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <h3
                  id={"weekday-" + weekday}
                  className="font-semibold text-ink"
                >
                  {weekdayLabels[weekday]}
                </h3>
                {canMutate ? (
                  <Button
                    variant="quiet"
                    onClick={() => addWindow(weekday)}
                    aria-label={"Add time on " + weekdayLabels[weekday]}
                  >
                    Add time
                  </Button>
                ) : null}
              </div>

              {rows.length === 0 ? (
                <p className="mt-3 text-sm text-muted">
                  No recurring availability
                </p>
              ) : (
                <div className="mt-3 space-y-3">
                  {rows.map((window, index) => {
                    const prefix =
                      "weekly-" + weekday.toLowerCase() + "-" + index;
                    return (
                      <div
                        key={window.key}
                        className="grid gap-3 md:grid-cols-[minmax(8rem,1fr)_minmax(8rem,1fr)_minmax(12rem,1.4fr)_auto] md:items-end"
                      >
                        <div className="grid gap-2">
                          <Label htmlFor={prefix + "-start"}>Start time</Label>
                          <Input
                            id={prefix + "-start"}
                            type="time"
                            disabled={!canMutate || pending}
                            value={window.start_time}
                            onChange={(event) =>
                              updateWindow(window.key, {
                                start_time: event.target.value,
                              })
                            }
                          />
                        </div>
                        <div className="grid gap-2">
                          <Label htmlFor={prefix + "-end"}>End time</Label>
                          <Input
                            id={prefix + "-end"}
                            type="time"
                            disabled={!canMutate || pending}
                            value={window.end_time}
                            onChange={(event) =>
                              updateWindow(window.key, {
                                end_time: event.target.value,
                              })
                            }
                          />
                        </div>
                        <div className="grid gap-2">
                          <Label htmlFor={prefix + "-mode"}>Applies to</Label>
                          <select
                            id={prefix + "-mode"}
                            className={availabilitySelectClass}
                            disabled={!canMutate || pending}
                            value={window.mode_scope}
                            onChange={(event) =>
                              updateWindow(window.key, {
                                mode_scope: event.target
                                  .value as AvailabilityModeScope,
                              })
                            }
                          >
                            <option value={AvailabilityModeScope.ALL}>
                              {modeScopeLabel(AvailabilityModeScope.ALL)}
                            </option>
                            <option value={AvailabilityModeScope.IN_PERSON}>
                              {modeScopeLabel(
                                AvailabilityModeScope.IN_PERSON,
                              )}
                            </option>
                            <option value={AvailabilityModeScope.ONLINE}>
                              {modeScopeLabel(AvailabilityModeScope.ONLINE)}
                            </option>
                          </select>
                        </div>
                        {canMutate ? (
                          <Button
                            variant="quiet"
                            disabled={pending}
                            onClick={() => removeWindow(window.key)}
                            aria-label={
                              "Remove " +
                              window.start_time +
                              " to " +
                              window.end_time +
                              " on " +
                              weekdayLabels[weekday]
                            }
                          >
                            Remove
                          </Button>
                        ) : null}
                      </div>
                    );
                  })}
                </div>
              )}
            </section>
          );
        })}
      </div>

      {localError ? (
        <p role="alert" className="mt-4 text-sm text-danger">
          {localError}
        </p>
      ) : null}
      <ActionFeedback error={error} notice={notice} />
    </section>
  );
}
