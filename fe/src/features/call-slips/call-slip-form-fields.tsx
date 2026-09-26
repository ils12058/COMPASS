"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  CallSlipDestinationTypeValue,
  type CallSlipCreateRequest,
} from "@/lib/api/generated/model";

export type CallSlipDraft = {
  courseYear: string;
  destinationType: CallSlipDestinationTypeValue;
  otherDestination: string;
  reportAt: string;
  notifyStudent: boolean;
};

export function CallSlipFormFields({
  draft,
  onChange,
}: {
  draft: CallSlipDraft;
  onChange: (next: CallSlipDraft) => void;
}) {
  return (
    <div className="space-y-6">
      <div className="grid gap-2">
        <Label htmlFor="call-slip-course-year">Course / Year</Label>
        <Input
          id="call-slip-course-year"
          maxLength={255}
          required
          value={draft.courseYear}
          onChange={(event) => onChange({ ...draft, courseYear: event.target.value })}
        />
      </div>
      <div className="grid gap-2">
        <Label htmlFor="call-slip-destination">Please report to</Label>
        <select
          id="call-slip-destination"
          className="min-h-11 w-full rounded-md border border-border-strong bg-surface-raised px-3 py-2 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          value={draft.destinationType}
          onChange={(event) => {
            const destinationType = event.target.value as CallSlipDestinationTypeValue;
            onChange({
              ...draft,
              destinationType,
              otherDestination:
                destinationType === CallSlipDestinationTypeValue.GUIDANCE_OFFICE
                  ? ""
                  : draft.otherDestination,
            });
          }}
        >
          <option value={CallSlipDestinationTypeValue.GUIDANCE_OFFICE}>Guidance Office</option>
          <option value={CallSlipDestinationTypeValue.OTHER}>Other</option>
        </select>
      </div>
      {draft.destinationType === CallSlipDestinationTypeValue.OTHER ? (
        <div className="grid gap-2">
          <Label htmlFor="call-slip-other-destination">Other destination</Label>
          <Input
            id="call-slip-other-destination"
            maxLength={255}
            required
            value={draft.otherDestination}
            onChange={(event) => onChange({ ...draft, otherDestination: event.target.value })}
          />
        </div>
      ) : null}
      <div className="grid gap-2">
        <Label htmlFor="call-slip-report-at">Report date and time</Label>
        <Input
          id="call-slip-report-at"
          type="datetime-local"
          step="60"
          required
          value={draft.reportAt}
          onChange={(event) => onChange({ ...draft, reportAt: event.target.value })}
        />
        <p className="text-xs leading-5 text-muted">
          Enter the date and time the Student was instructed to report. Past, present, and future source dates are allowed.
        </p>
      </div>
      <fieldset className="min-w-0">
        <legend className="text-sm font-semibold text-ink">Issuance mode</legend>
        <div className="mt-3 space-y-3">
          <label className="flex items-start gap-3 text-sm leading-5 text-ink">
            <input
              className="mt-1 h-4 w-4 shrink-0 accent-brand"
              type="radio"
              name="call-slip-issuance-mode"
              checked={draft.notifyStudent}
              onChange={() => onChange({ ...draft, notifyStudent: true })}
            />
            <span>
              <span className="block font-semibold">Live issuance</span>
              <span className="mt-1 block text-muted">Issue this Call Slip now. COMPASS will create the Student&apos;s in-app notification and queue the required operational email.</span>
            </span>
          </label>
          <label className="flex items-start gap-3 text-sm leading-5 text-ink">
            <input
              className="mt-1 h-4 w-4 shrink-0 accent-brand"
              type="radio"
              name="call-slip-issuance-mode"
              checked={!draft.notifyStudent}
              onChange={() => onChange({ ...draft, notifyStudent: false })}
            />
            <span>
              <span className="block font-semibold">Historical / back-entry</span>
              <span className="mt-1 block text-muted">Record an existing historical Call Slip. The Student is not notified now, or if this Call Slip is voided later.</span>
            </span>
          </label>
        </div>
      </fieldset>
    </div>
  );
}

export function toCallSlipRequestFields(draft: CallSlipDraft): Pick<
  CallSlipCreateRequest,
  "course_year" | "destination_type" | "other_destination" | "report_at" | "notify_student"
> | null {
  const reportAt = new Date(draft.reportAt);
  if (
    !draft.courseYear.trim() ||
    !draft.reportAt ||
    Number.isNaN(reportAt.getTime()) ||
    (draft.destinationType === CallSlipDestinationTypeValue.OTHER && !draft.otherDestination.trim())
  ) {
    return null;
  }

  return {
    course_year: draft.courseYear.trim(),
    destination_type: draft.destinationType,
    other_destination:
      draft.destinationType === CallSlipDestinationTypeValue.OTHER
        ? draft.otherDestination.trim()
        : "",
    report_at: reportAt.toISOString(),
    notify_student: draft.notifyStudent,
  };
}
