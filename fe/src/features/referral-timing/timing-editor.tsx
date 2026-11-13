"use client";

import { useRef } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { ReferralTimingInformationType, ReferralTimingPattern, ReferralTimingWeekday } from "@/lib/api/generated/model";
import { institutionalDateInputValue } from "@/lib/institutional-time";
import { addCivilDays, newTimingWindow, timingInputId, type TimingDraft, type TimingFieldErrors, type TimingWindowDraft } from "./timing-draft";

export const weekdayLabels: Record<ReferralTimingWeekday, string> = {
  MONDAY: "Monday", TUESDAY: "Tuesday", WEDNESDAY: "Wednesday", THURSDAY: "Thursday", FRIDAY: "Friday", SATURDAY: "Saturday",
};
const informationTypes = [
  { value: ReferralTimingInformationType.STUDENT_AVAILABLE, label: "The student is usually free" },
  { value: ReferralTimingInformationType.CLASS_RELEASE, label: "The student may leave my class" },
];
const patterns = [{ value: ReferralTimingPattern.SPECIFIC_DATE, label: "Specific date" }, { value: ReferralTimingPattern.RECURRING_WEEKDAY, label: "Recurring weekday" }];

export function TimingEditor({ prefix, draft, onChange, errors = {}, disabled = false, verification = false }: {
  prefix: string; draft: TimingDraft; onChange: (draft: TimingDraft) => void; errors?: TimingFieldErrors; disabled?: boolean; verification?: boolean;
}) {
  const nextKey = useRef(1);
  const today = institutionalDateInputValue();
  function addWindow() {
    const key = Math.max(nextKey.current, ...draft.windows.map(row => row.key + 1));
    nextKey.current = key + 1;
    const next = { ...draft, windows: [...draft.windows, newTimingWindow(key)] };
    onChange(next);
    requestAnimationFrame(() => document.getElementById(`${prefix}-window-${key}-information_type`)?.focus());
  }
  function patchWindow(key: number, patch: Partial<TimingWindowDraft>) {
    onChange({ ...draft, windows: draft.windows.map(window => window.key === key ? { ...window, ...patch } : window) });
  }
  function feedback(field: string) {
    return errors[field] ? <p id={`${timingInputId(prefix, draft, field)}-error`} className="mt-1 text-sm text-danger">{errors[field]}</p> : null;
  }
  function errorProps(field: string) {
    return { "aria-invalid": !!errors[field], "aria-describedby": errors[field] ? `${timingInputId(prefix, draft, field)}-error` : undefined };
  }
  return <fieldset disabled={disabled} className="min-w-0 space-y-4">
    <legend className="sr-only">{verification ? "Verified availability information" : "When can Guidance reach or meet the student?"}</legend>
    <fieldset className="min-w-0">
      <legend className="mb-2 text-sm font-semibold">{verification ? "Confirmed timing" : "Timing information"}</legend>
      <div className="grid min-w-0 grid-cols-1 gap-2 sm:grid-cols-2">
        {[{ value: "KNOWN" as const, label: verification ? "Confirmed times" : "Known times" }, { value: verification ? "NO_SUITABLE_TIME" as const : "UNKNOWN" as const, label: verification ? "No suitable time confirmed" : "Unknown / needs confirmation" }].map((choice, index) => <Label key={choice.value} className="flex min-h-11 cursor-pointer items-center gap-2 rounded-md border border-border-strong px-3 py-2 has-checked:border-brand has-checked:bg-brand-wash" htmlFor={`${prefix}-${index === 0 ? "answer_kind" : "no-time"}`}>
          <Input type="radio" className="size-4 min-h-0 w-4 shrink-0 accent-brand" id={`${prefix}-${index === 0 ? "answer_kind" : "no-time"}`} name={`${prefix}-answer`} checked={draft.answer === choice.value} value={choice.value} onChange={() => onChange({ ...draft, answer: choice.value })} {...errorProps("answer_kind")} />
          <span className="min-w-0 [overflow-wrap:anywhere]">{choice.label}</span>
        </Label>)}
      </div>
      {feedback("answer_kind")}
    </fieldset>
    {draft.answer === "KNOWN" ? <>
      {draft.windows.map((window, index) => <fieldset key={window.key} className="min-w-0 border-t border-border pt-4">
        <legend className="px-1 text-sm font-semibold text-brand">Window {index + 1} of {draft.windows.length}</legend>
        <div className="grid min-w-0 grid-cols-1 gap-4 sm:grid-cols-2">
          <div><Label htmlFor={timingInputId(prefix, draft, `windows.${index}.information_type`)}>Information type</Label>
            <Select className="mt-2" id={timingInputId(prefix, draft, `windows.${index}.information_type`)} value={window.informationType} onChange={event => { const selected = informationTypes.find(option => option.value === event.target.value); if (selected) patchWindow(window.key, { informationType: selected.value }); }} {...errorProps(`windows.${index}.information_type`)}>{informationTypes.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}</Select>
            {feedback(`windows.${index}.information_type`)}
          </div>
          <div><Label htmlFor={timingInputId(prefix, draft, `windows.${index}.pattern`)}>Pattern</Label>
            <Select className="mt-2" id={timingInputId(prefix, draft, `windows.${index}.pattern`)} value={window.pattern} onChange={event => { const selected = patterns.find(option => option.value === event.target.value); if (selected) patchWindow(window.key, { pattern: selected.value }); }} {...errorProps(`windows.${index}.pattern`)}>{patterns.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}</Select>
            {feedback(`windows.${index}.pattern`)}
          </div>
          {window.pattern === "SPECIFIC_DATE" ? <div><Label htmlFor={timingInputId(prefix, draft, `windows.${index}.date`)}>Date · Philippine Time</Label>
            <Input className="mt-2" type="date" min={today} id={timingInputId(prefix, draft, `windows.${index}.date`)} value={window.date} onChange={event => patchWindow(window.key, { date: event.target.value })} {...errorProps(`windows.${index}.date`)} />{feedback(`windows.${index}.date`)}
          </div> : <>
            <div><Label htmlFor={timingInputId(prefix, draft, `windows.${index}.weekday`)}>Weekday</Label><Select className="mt-2" id={timingInputId(prefix, draft, `windows.${index}.weekday`)} value={window.weekday} onChange={event => { const selected = Object.values(ReferralTimingWeekday).find(value => value === event.target.value); patchWindow(window.key, { weekday: selected ?? "" }); }} {...errorProps(`windows.${index}.weekday`)}><option value="">Choose Monday to Saturday</option>{Object.values(ReferralTimingWeekday).map(value => <option key={value} value={value}>{weekdayLabels[value]}</option>)}</Select>{feedback(`windows.${index}.weekday`)}</div>
            <div><Label htmlFor={timingInputId(prefix, draft, `windows.${index}.valid_until`)}>Valid until · Philippine Time</Label><Input className="mt-2" type="date" min={today} max={addCivilDays(today, 180)} id={timingInputId(prefix, draft, `windows.${index}.valid_until`)} value={window.validUntil} onChange={event => patchWindow(window.key, { validUntil: event.target.value })} {...errorProps(`windows.${index}.valid_until`)} />{feedback(`windows.${index}.valid_until`)}</div>
          </>}
          <div><Label htmlFor={timingInputId(prefix, draft, `windows.${index}.start_time`)}>Start time · Philippine Time</Label><Input className="mt-2" type="time" step="60" id={timingInputId(prefix, draft, `windows.${index}.start_time`)} value={window.startTime} onChange={event => patchWindow(window.key, { startTime: event.target.value })} {...errorProps(`windows.${index}.start_time`)} />{feedback(`windows.${index}.start_time`)}</div>
          <div><Label htmlFor={timingInputId(prefix, draft, `windows.${index}.end_time`)}>End time · Philippine Time</Label><Input className="mt-2" type="time" step="60" id={timingInputId(prefix, draft, `windows.${index}.end_time`)} value={window.endTime} onChange={event => patchWindow(window.key, { endTime: event.target.value })} {...errorProps(`windows.${index}.end_time`)} />{feedback(`windows.${index}.end_time`)}</div>
        </div>
        <Button type="button" variant="secondary" className="mt-3" aria-label={`Remove Window ${index + 1}`} onClick={() => { onChange({ ...draft, windows: draft.windows.filter(row => row.key !== window.key) }); requestAnimationFrame(() => document.getElementById(`${prefix}-add-window`)?.focus()); }}>Remove window</Button>
      </fieldset>)}
      <Button type="button" id={`${prefix}-add-window`} variant="secondary" disabled={draft.windows.length >= 5} onClick={addWindow} {...errorProps("windows")}>Add window</Button>
      {feedback("windows")}
      <p className="text-sm text-muted">One to five windows. Overlapping times are allowed. Recurring times need a validity date within 180 days.</p>
    </> : null}
    {draft.answer === "KNOWN" || (verification && draft.answer === "NO_SUITABLE_TIME") ? <div>
      <Label htmlFor={`${prefix}-note`}>Scheduling constraints note (optional)</Label>
      <Textarea className="mt-2" rows={3} id={`${prefix}-note`} value={draft.note} onChange={event => onChange({ ...draft, note: event.target.value })} {...errorProps("note")} aria-describedby={`${prefix}-note-help${errors.note ? ` ${prefix}-note-error` : ""}`} />
      <p id={`${prefix}-note-help`} className="mt-1 text-sm text-muted">Scheduling constraints only, up to 500 characters. Keep the reason for Referral in the existing reason field.</p>
      {feedback("note")}
    </div> : null}
  </fieldset>;
}
