"use client";

import { Plus, X } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Panel, PanelFooter, PanelHeader } from "@/components/ui/panel";
import { modeScopeLabel } from "@/features/availability/availability-shared";
import { focusHeading } from "@/lib/focus-heading";
import {
  draftFromWindows,
  formatClockRange,
  requestFromDraft,
  validateDraft,
  weekdayLabels,
  weekdayOrder,
  weekdayShortLabels,
  windowsForDay,
  type DraftProblem,
  type DraftWindow,
} from "@/features/availability/weekly-schedule";
import {
  AvailabilityModeScope,
  type Weekday,
  type WeeklyWindowRequest,
  type WeeklyWindowResponse,
} from "@/lib/api/generated/model";

function createKey(): string {
  return Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 9);
}

// One row per weekday: the short day name, its hours, and (when editable) Add. The board follows
// the panel's own width (a container query), so it never squeezes when it shares the page with
// Unavailability: wide, it is three columns; narrow, the day and Add share a line and the hours
// take the full width beneath them.
const editableDayRow =
  "grid grid-cols-[minmax(0,1fr)_auto] items-start gap-x-3 gap-y-1 px-4 py-2 sm:px-5 @[30rem]/weekly:grid-cols-[3.5rem_minmax(0,1fr)_auto]";
const editableHours = "col-span-2 row-start-2 min-w-0 @[30rem]/weekly:col-span-1 @[30rem]/weekly:col-start-2 @[30rem]/weekly:row-start-1";
const editableAdd = "col-start-2 row-start-1 @[30rem]/weekly:col-start-3";
// A day without hours ("No hours set") fits on one line at any width.
const emptyDayRow = "grid grid-cols-[3.5rem_minmax(0,1fr)_auto] items-start gap-x-3 px-4 py-2 sm:px-5";
const readOnlyDayRow = "grid grid-cols-[3.5rem_minmax(0,1fr)] gap-x-3 px-4 py-2 sm:px-5";

function DayName({ weekday, id }: { weekday: Weekday; id: string }) {
  return (
    <p id={id} className="col-start-1 row-start-1 pt-2.5 text-sm font-semibold text-ink">
      <span aria-hidden="true">{weekdayShortLabels[weekday]}</span>
      <span className="sr-only">{weekdayLabels[weekday]}</span>
    </p>
  );
}

function ReadOnlyHours({ windows }: { windows: { start_time: string; end_time: string; mode_scope: AvailabilityModeScope }[] }) {
  if (windows.length === 0) return <p className="py-2.5 text-sm text-muted">No hours set</p>;
  return (
    <ul>
      {windows.map((window) => (
        <li key={window.start_time + window.end_time + window.mode_scope} className="py-2.5 text-sm text-ink">
          {formatClockRange(window.start_time, window.end_time)}
          <span className="text-muted"> · {modeScopeLabel(window.mode_scope)}</span>
        </li>
      ))}
    </ul>
  );
}

function ModeOptions() {
  return (
    <>
      <option value={AvailabilityModeScope.ALL}>{modeScopeLabel(AvailabilityModeScope.ALL)}</option>
      <option value={AvailabilityModeScope.IN_PERSON}>{modeScopeLabel(AvailabilityModeScope.IN_PERSON)}</option>
      <option value={AvailabilityModeScope.ONLINE}>{modeScopeLabel(AvailabilityModeScope.ONLINE)}</option>
    </>
  );
}

function EditableHours({
  weekday,
  rows,
  pending,
  invalid,
  onUpdate,
  onRemove,
}: {
  weekday: Weekday;
  rows: DraftWindow[];
  pending: boolean;
  invalid: boolean;
  onUpdate: (key: string, changes: Partial<Omit<DraftWindow, "key" | "weekday">>) => void;
  onRemove: (key: string) => void;
}) {
  if (rows.length === 0) return <p className="py-2.5 text-sm text-muted">No hours set</p>;
  const day = weekdayLabels[weekday];
  return (
    <ul className="space-y-2">
      {rows.map((window, index) => {
        const prefix = "weekly-" + weekday.toLowerCase() + "-" + index;
        const position = rows.length > 1 ? ` ${index + 1}` : "";
        return (
          <li key={window.key} className="flex flex-wrap items-center gap-2">
            {/* The times and the mode each wrap as a unit on narrow screens. */}
            <span className="flex items-center gap-2">
              <Label htmlFor={prefix + "-start"} className="sr-only">{`${day} hours${position} start time`}</Label>
              <Input
                id={prefix + "-start"}
                type="time"
                className="w-[8rem]"
                disabled={pending}
                aria-invalid={invalid || undefined}
                value={window.start_time}
                onChange={(event) => onUpdate(window.key, { start_time: event.target.value })}
              />
              <span aria-hidden="true" className="text-muted">–</span>
              <Label htmlFor={prefix + "-end"} className="sr-only">{`${day} hours${position} end time`}</Label>
              <Input
                id={prefix + "-end"}
                type="time"
                className="w-[8rem]"
                disabled={pending}
                aria-invalid={invalid || undefined}
                value={window.end_time}
                onChange={(event) => onUpdate(window.key, { end_time: event.target.value })}
              />
            </span>
            <span className="flex items-center gap-2">
              <Label htmlFor={prefix + "-mode"} className="sr-only">{`${day} hours${position} apply to`}</Label>
              <Select
                id={prefix + "-mode"}
                className="w-auto min-w-[10.5rem]"
                disabled={pending}
                aria-invalid={invalid || undefined}
                value={window.mode_scope}
                onChange={(event) => onUpdate(window.key, { mode_scope: event.target.value as AvailabilityModeScope })}
              >
                <ModeOptions />
              </Select>
              <button
                type="button"
                disabled={pending}
                onClick={() => onRemove(window.key)}
                aria-label={`Remove ${formatClockRange(window.start_time, window.end_time)} on ${day}`}
                title="Remove these hours"
                className="inline-flex min-h-10 min-w-10 items-center justify-center rounded-md text-muted hover:bg-surface-muted hover:text-danger focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus disabled:cursor-not-allowed disabled:opacity-55"
              >
                <X size={17} aria-hidden="true" />
              </button>
            </span>
          </li>
        );
      })}
    </ul>
  );
}

// The recurring weekly hours. Editing changes a local draft; Save replaces the whole schedule.
// A problem that stops saving is shown on the day it concerns; a failed save stays beside Save.
// Success is announced by the page (ActionStatus), and the page remounts the editor with the
// saved windows.
export function WeeklyScheduleEditor({
  windows,
  canMutate,
  pending,
  error,
  onSave,
}: {
  windows: WeeklyWindowResponse[];
  canMutate: boolean;
  pending: boolean;
  error: string | null;
  onSave: (windows: WeeklyWindowRequest[]) => Promise<boolean>;
}) {
  const [draft, setDraft] = useState<DraftWindow[]>(() => draftFromWindows(windows));
  const [dirty, setDirty] = useState(false);
  const [problem, setProblem] = useState<DraftProblem | null>(null);

  function edit(change: (current: DraftWindow[]) => DraftWindow[]) {
    setProblem(null);
    setDirty(true);
    setDraft(change);
  }

  function addWindow(weekday: Weekday) {
    edit((current) => [
      ...current,
      { key: createKey(), weekday, start_time: "08:00", end_time: "17:00", mode_scope: AvailabilityModeScope.ALL },
    ]);
  }

  async function save() {
    const found = validateDraft(draft);
    if (found) {
      setProblem(found);
      return;
    }
    const saved = await onSave(requestFromDraft(draft));
    if (saved) {
      setDirty(false);
      setProblem(null);
    }
  }

  return (
    <Panel aria-labelledby="weekly-schedule-heading" className="@container/weekly">
      <PanelHeader title="Weekly schedule" titleId="weekly-schedule-heading" />
      <ul className="divide-y divide-border">
        {weekdayOrder.map((weekday) => {
          const dayId = "weekday-" + weekday.toLowerCase();
          const dayProblem = problem?.weekday === weekday ? problem.message : null;
          const empty = windowsForDay(draft, weekday).length === 0;
          return (
            <li
              key={weekday}
              aria-labelledby={dayId}
              className={!canMutate ? readOnlyDayRow : empty ? emptyDayRow : editableDayRow}
            >
              <DayName weekday={weekday} id={dayId} />
              <div className={canMutate && !empty ? editableHours : "min-w-0"}>
                {canMutate ? (
                  <EditableHours
                    weekday={weekday}
                    rows={windowsForDay(draft, weekday)}
                    pending={pending}
                    invalid={dayProblem !== null}
                    onUpdate={(key, changes) =>
                      edit((current) => current.map((window) => (window.key === key ? { ...window, ...changes } : window)))
                    }
                    onRemove={(key) => edit((current) => current.filter((window) => window.key !== key))}
                  />
                ) : (
                  <ReadOnlyHours windows={windowsForDay(draft, weekday)} />
                )}
                {dayProblem ? (
                  <p role="alert" className="pb-1 pt-1.5 text-sm text-danger">
                    {dayProblem}
                  </p>
                ) : null}
              </div>
              {canMutate ? (
                <div className={empty ? undefined : editableAdd}>
                  <Button
                    variant="quiet"
                    className="px-2.5"
                    disabled={pending}
                    onClick={() => addWindow(weekday)}
                    aria-label={"Add time on " + weekdayLabels[weekday]}
                  >
                    <Plus size={16} aria-hidden="true" />
                    Add
                  </Button>
                </div>
              ) : null}
            </li>
          );
        })}
      </ul>
      {canMutate ? (
        <PanelFooter>
          <Button disabled={pending || !dirty} aria-describedby={error ? "weekly-schedule-error" : undefined} onClick={() => void save()}>
            {pending ? "Saving…" : "Save weekly schedule"}
          </Button>
          <p className="min-w-0 flex-1 text-sm leading-6 text-muted">
            Saving replaces all weekly hours shown above. Existing appointments stay scheduled; review them
            separately if the hours change.
          </p>
          {error ? (
            <p id="weekly-schedule-error" role="alert" className="basis-full text-sm text-danger">
              {error}
            </p>
          ) : null}
        </PanelFooter>
      ) : null}
    </Panel>
  );
}

// Saved hours that can no longer be edited, such as an inactive Counselor's or historical Guidance
// Services Staff hours: they can be reviewed or cleared. Not keyed on the windows, so the clearing
// confirmation stays open to show its outcome after the schedule reloads empty.
export function WeeklyScheduleCleanup({
  windows,
  pending,
  error,
  onClear,
  onResetError,
}: {
  windows: WeeklyWindowResponse[];
  pending: boolean;
  error: string | null;
  onClear: () => Promise<boolean>;
  onResetError: () => void;
}) {
  const [clearOpen, setClearOpen] = useState(false);
  const [cleared, setCleared] = useState(false);

  async function clearSchedule() {
    if (await onClear()) setCleared(true);
  }

  return (
    <Panel aria-labelledby="weekly-schedule-heading" className="@container/weekly">
      <PanelHeader
        title="Weekly schedule"
        titleId="weekly-schedule-heading"
        description="You can review or clear these saved weekly hours. Existing appointments stay scheduled."
        actions={windows.length > 0 ? (
          <Button
            variant="danger"
            onClick={() => {
              onResetError();
              setCleared(false);
              setClearOpen(true);
            }}
          >
            Clear weekly schedule
          </Button>
        ) : undefined}
      />
      <ul className="divide-y divide-border">
        {weekdayOrder.map((weekday) => {
          const dayId = "weekday-" + weekday.toLowerCase();
          return (
            <li key={weekday} aria-labelledby={dayId} className={readOnlyDayRow}>
              <DayName weekday={weekday} id={dayId} />
              <ReadOnlyHours
                windows={windowsForDay(windows, weekday).map((window) => ({
                  ...window,
                  start_time: window.start_time.slice(0, 5),
                  end_time: window.end_time.slice(0, 5),
                }))}
              />
            </li>
          );
        })}
      </ul>
      <ConsequentialActionDialog
        open={clearOpen}
        title="Clear the complete weekly schedule?"
        confirmLabel="Clear weekly schedule"
        pendingLabel="Clearing…"
        pending={pending}
        error={error}
        variant="danger"
        completed={cleared ? {
          title: "Weekly schedule cleared",
          children: <p>No recurring Availability windows remain for this provider. Existing Appointments remain scheduled.</p>,
        } : null}
        onOpenChange={setClearOpen}
        onConfirm={() => void clearSchedule()}
        onCloseAutoFocus={(event) => {
          if (!cleared) return;
          // The Clear button is gone with the hours; keep focus on this schedule.
          event.preventDefault();
          focusHeading("weekly-schedule-heading");
        }}
      >
        <p>
          This removes every recurring Availability window for this provider. Existing Appointments remain
          scheduled. Historical unavailability records are not removed.
        </p>
      </ConsequentialActionDialog>
    </Panel>
  );
}
