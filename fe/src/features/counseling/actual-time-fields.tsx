"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { INSTITUTION_TIME_ZONE_LABEL, institutionalDateTimeInputToISO } from "@/lib/institutional-time";

export type ActualTimeField = "start" | "end";
export type ActualTimeIssues = Partial<Record<ActualTimeField, string>>;

// What the reader must fix in an encounter's actual times, by field. The inputs are civil times in
// the institutional zone whatever the browser's zone. `now` (milliseconds) enables the future check.
// The backend validates every save again.
export function actualTimeIssues(startedAt: string, endedAt: string, now: number | null): ActualTimeIssues {
  const start = startedAt ? institutionalDateTimeInputToISO(startedAt) : null;
  const end = endedAt ? institutionalDateTimeInputToISO(endedAt) : null;
  const issues: ActualTimeIssues = {};
  if (!startedAt) issues.start = "Enter the actual start time.";
  else if (!start) issues.start = "Enter a valid actual start date and time.";
  if (!endedAt) issues.end = "Enter the actual end time.";
  else if (!end) issues.end = "Enter a valid actual end date and time.";
  else if (start && Date.parse(end) <= Date.parse(start)) issues.end = "The actual end must be later than the start.";
  else if (now !== null && Date.parse(end) > now) issues.end = "The actual end cannot be in the future.";
  return issues;
}

export function firstActualTimeIssue(issues: ActualTimeIssues): ActualTimeField | null {
  return issues.start ? "start" : issues.end ? "end" : null;
}

export function actualTimeInputId(idPrefix: string, field: ActualTimeField): string {
  return `${idPrefix}-${field === "start" ? "started" : "ended"}-at`;
}

// The actual times of a Counseling Encounter, shared by recording and correction so both read,
// validate, and explain the times the same way. Scheduled Appointment times are context elsewhere
// in the form and never fill these fields.
export function ActualTimeFields({
  idPrefix,
  startedAt,
  endedAt,
  onChange,
  issues,
  attempted,
  disabled,
  withSeconds = false,
  scheduled = false,
}: {
  idPrefix: string;
  startedAt: string;
  endedAt: string;
  onChange: (field: ActualTimeField, value: string) => void;
  issues: ActualTimeIssues;
  // Missing times are reported only after a save attempt; a completed pair is checked as it is entered.
  attempted: boolean;
  disabled: boolean;
  // Corrections keep the saved seconds.
  withSeconds?: boolean;
  // The encounter has a scheduled Appointment to compare against.
  scheduled?: boolean;
}) {
  const shown = attempted || (startedAt && endedAt) ? issues : {};
  const helpId = `${idPrefix}-time-help`;
  const field = (name: ActualTimeField, label: string, value: string) => {
    const id = actualTimeInputId(idPrefix, name);
    const error = shown[name];
    return (
      <div className="grid min-w-0 content-start gap-2">
        <Label htmlFor={id}>{label}</Label>
        <Input
          id={id}
          type="datetime-local"
          step={withSeconds ? 1 : undefined}
          required
          value={value}
          disabled={disabled}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? `${id}-error` : undefined}
          onChange={(event) => onChange(name, event.target.value)}
        />
        <div aria-live="polite">{error ? <p id={`${id}-error`} className="text-sm text-danger">{error}</p> : null}</div>
      </div>
    );
  };
  return (
    <fieldset className="min-w-0" aria-describedby={helpId}>
      <legend className="text-sm font-semibold text-ink">Actual counseling interaction</legend>
      <p id={helpId} className="mt-1 text-sm text-muted">
        Enter when the counseling conversation actually started and ended, in {INSTITUTION_TIME_ZONE_LABEL}.
        {scheduled ? " These times may differ from the scheduled appointment." : null}
      </p>
      <div className="mt-3 grid gap-4 sm:grid-cols-2">
        {field("start", "Actual start", startedAt)}
        {field("end", "Actual end", endedAt)}
      </div>
    </fieldset>
  );
}
