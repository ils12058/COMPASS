"use client";

import { FormEvent, useState } from "react";
import { LoaderCircle, Plus, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import type {
  AvailabilityModeScope,
  Weekday,
  WeeklyWindowRequest,
  WeeklyWindowResponse,
} from "@/lib/api/generated/model";
import {
  AvailabilityModeScope as AvailabilityModeScopeValues,
  Weekday as WeekdayValues,
} from "@/lib/api/generated/model";
import {
  availabilitySelectClassName,
  formatAvailabilityValue,
  toApiTimeValue,
  toTimeInputValue,
} from "@/features/portal/admin/availability/portal-it-admin-availability-shared";

type WindowDraft = {
  endTime: string;
  modeScope: AvailabilityModeScope;
  startTime: string;
  weekday: Weekday;
};

function toDraft(window: WeeklyWindowResponse): WindowDraft {
  return {
    endTime: toTimeInputValue(window.end_time),
    modeScope: window.mode_scope,
    startTime: toTimeInputValue(window.start_time),
    weekday: window.weekday,
  };
}

function newWindow(): WindowDraft {
  return {
    endTime: "17:00",
    modeScope: AvailabilityModeScopeValues.ALL,
    startTime: "09:00",
    weekday: WeekdayValues.MONDAY,
  };
}

export function PortalItAdminWeeklyScheduleEditor({
  initialWindows,
  isSubmitting,
  onSubmit,
}: {
  initialWindows: WeeklyWindowResponse[];
  isSubmitting: boolean;
  onSubmit: (windows: WeeklyWindowRequest[]) => void | Promise<void>;
}) {
  const [windows, setWindows] = useState(() => initialWindows.map(toDraft));
  const [validationError, setValidationError] = useState<string | null>(null);

  function updateWindow(index: number, changes: Partial<WindowDraft>) {
    setWindows((current) =>
      current.map((window, windowIndex) =>
        windowIndex === index ? { ...window, ...changes } : window,
      ),
    );
    setValidationError(null);
  }

  function removeWindow(index: number) {
    setWindows((current) => current.filter((_, windowIndex) => windowIndex !== index));
    setValidationError(null);
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (
      windows.some(
        (window) =>
          !window.startTime ||
          !window.endTime ||
          window.startTime >= window.endTime,
      )
    ) {
      setValidationError("Each availability window needs a start time before its end time.");
      return;
    }

    setValidationError(null);
    void onSubmit(
      windows.map((window) => ({
        end_time: toApiTimeValue(window.endTime),
        mode_scope: window.modeScope,
        start_time: toApiTimeValue(window.startTime),
        weekday: window.weekday,
      })),
    );
  }

  return (
    <form className="space-y-4" onSubmit={submit}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="font-semibold">Recurring windows</h3>
          <p className="mt-1 text-sm leading-6 text-muted-foreground">
            Add the regular hours that are open for requests.
          </p>
        </div>
        <Button
          type="button"
          variant="outline"
          onClick={() => setWindows((current) => [...current, newWindow()])}
        >
          <Plus aria-hidden="true" />
          Add window
        </Button>
      </div>

      {validationError ? (
        <p className="text-sm text-destructive" role="alert">
          {validationError}
        </p>
      ) : null}

      {windows.length ? (
        <div className="space-y-3">
          {windows.map((window, index) => (
            <div
              key={`${window.weekday}-${window.startTime}-${window.endTime}-${index}`}
              className="rounded-2xl border border-[var(--compass-border)] bg-[var(--compass-surface-subtle)] p-4"
            >
              <div className="grid gap-3 sm:grid-cols-[1.2fr_1fr_1fr_1.2fr_auto] sm:items-end">
                <div>
                  <Label htmlFor={`availability-weekday-${index}`}>Day</Label>
                  <select
                    id={`availability-weekday-${index}`}
                    className={`${availabilitySelectClassName} mt-2`}
                    value={window.weekday}
                    onChange={(event) =>
                      updateWindow(index, { weekday: event.target.value as Weekday })
                    }
                  >
                    {Object.values(WeekdayValues).map((weekday) => (
                      <option key={weekday} value={weekday}>
                        {formatAvailabilityValue(weekday)}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <Label htmlFor={`availability-start-${index}`}>Starts</Label>
                  <input
                    id={`availability-start-${index}`}
                    className="mt-2 h-10 w-full rounded-lg border border-input bg-card px-2.5 text-sm text-foreground outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
                    type="time"
                    value={window.startTime}
                    onChange={(event) => updateWindow(index, { startTime: event.target.value })}
                  />
                </div>
                <div>
                  <Label htmlFor={`availability-end-${index}`}>Ends</Label>
                  <input
                    id={`availability-end-${index}`}
                    className="mt-2 h-10 w-full rounded-lg border border-input bg-card px-2.5 text-sm text-foreground outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
                    type="time"
                    value={window.endTime}
                    onChange={(event) => updateWindow(index, { endTime: event.target.value })}
                  />
                </div>
                <div>
                  <Label htmlFor={`availability-scope-${index}`}>Applies to</Label>
                  <select
                    id={`availability-scope-${index}`}
                    className={`${availabilitySelectClassName} mt-2`}
                    value={window.modeScope}
                    onChange={(event) =>
                      updateWindow(index, {
                        modeScope: event.target.value as AvailabilityModeScope,
                      })
                    }
                  >
                    {Object.values(AvailabilityModeScopeValues).map((scope) => (
                      <option key={scope} value={scope}>
                        {formatAvailabilityValue(scope)}
                      </option>
                    ))}
                  </select>
                </div>
                <Button
                  aria-label={`Remove window ${index + 1}`}
                  className="sm:mb-0.5"
                  type="button"
                  variant="ghost"
                  size="icon"
                  onClick={() => removeWindow(index)}
                >
                  <Trash2 aria-hidden="true" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="rounded-2xl border border-dashed border-[var(--compass-border-strong)] bg-[var(--compass-surface-subtle)] p-6 text-center">
          <p className="text-sm leading-6 text-muted-foreground">
            No recurring windows are configured yet.
          </p>
        </div>
      )}

      <div className="flex justify-end border-t border-[var(--compass-border)] pt-4">
        <Button disabled={isSubmitting} type="submit">
          {isSubmitting ? <LoaderCircle aria-hidden="true" className="animate-spin" /> : null}
          {isSubmitting ? "Saving…" : "Save schedule"}
        </Button>
      </div>
    </form>
  );
}
