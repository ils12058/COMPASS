import { CompassApiError } from "@/lib/api/errors";
import {
  ReferralTimingAnswer,
  ReferralTimingInformationType,
  ReferralTimingPattern,
  ReferralTimingVerificationAnswer,
  ReferralTimingWeekday,
} from "@/lib/api/generated/model";
import type { ReferralSchedulingStatementRequest, ReferralTimingWindowRequest } from "@/lib/api/generated/model";
import { institutionalDateInputValue, institutionalDateTimeInputToISO } from "@/lib/institutional-time";

// Incomplete input and stable row keys are presentation state, not a second wire contract.
export type TimingWindowDraft = {
  key: number;
  informationType: ReferralTimingInformationType;
  pattern: ReferralTimingPattern;
  date: string;
  weekday: ReferralTimingWeekday | "";
  validUntil: string;
  startTime: string;
  endTime: string;
};
export type TimingDraft = {
  answer: ReferralTimingAnswer | ReferralTimingVerificationAnswer | "";
  windows: TimingWindowDraft[];
  note: string;
};
export type TimingFieldErrors = Record<string, string>;
export const TIMING_NOTE_LIMIT = 500;
export const TIMING_VALIDITY_DAYS = 180;
export const TIMING_WINDOW_LIMIT = 5;
export const emptyTimingDraft = (): TimingDraft => ({ answer: "", windows: [], note: "" });
export const newTimingWindow = (key: number): TimingWindowDraft => ({
  key, informationType: ReferralTimingInformationType.STUDENT_AVAILABLE,
  pattern: ReferralTimingPattern.SPECIFIC_DATE, date: "", weekday: "", validUntil: "", startTime: "", endTime: "",
});

export function timingDraftDirty(draft: TimingDraft): boolean {
  return draft.answer !== "" || draft.note !== "" || draft.windows.length > 0;
}

export function addCivilDays(day: string, days: number): string {
  const date = new Date(`${day}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

function validDate(value: string): boolean {
  return /^\d{4}-\d{2}-\d{2}$/.test(value) && institutionalDateTimeInputToISO(`${value}T00:00`) !== null;
}
function timeSeconds(value: string): number | null {
  const match = /^(\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,6}))?)?$/.exec(value);
  if (!match || Number(match[1]) > 23 || Number(match[2]) > 59 || Number(match[3] ?? 0) > 59) return null;
  return Number(match[1]) * 3600 + Number(match[2]) * 60 + Number(match[3] ?? 0) + Number(`0.${match[4] ?? "0"}`);
}

export function validateTimingDraft(draft: TimingDraft, { verification = false, now = new Date() } = {}): TimingFieldErrors {
  const errors: TimingFieldErrors = {};
  const noTime = verification ? ReferralTimingVerificationAnswer.NO_SUITABLE_TIME : ReferralTimingAnswer.UNKNOWN;
  if (draft.answer !== "KNOWN" && draft.answer !== noTime) errors.answer_kind = "Choose known times or the unknown option.";
  const known = draft.answer === "KNOWN";
  if (known && draft.windows.length === 0) errors.windows = "Add at least one window for known times.";
  if (known && draft.windows.length > TIMING_WINDOW_LIMIT) errors.windows = "Provide at most five windows.";
  if ((known || verification) && ([...draft.note].length > TIMING_NOTE_LIMIT || /\u0000|[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]/u.test(draft.note))) errors.note = "Use plain text of at most 500 characters, without invalid characters.";
  if (!known) return errors;
  const today = institutionalDateInputValue(now);
  const maximum = addCivilDays(today, TIMING_VALIDITY_DAYS);
  const seen = new Set<string>();
  draft.windows.forEach((window, index) => {
    const field = (name: string) => `windows.${index}.${name}`;
    if (!Object.values(ReferralTimingInformationType).includes(window.informationType)) errors[field("information_type")] = "Choose student availability or class release.";
    if (!Object.values(ReferralTimingPattern).includes(window.pattern)) errors[field("pattern")] = "Choose a specific date or a recurring weekday.";
    const start = timeSeconds(window.startTime), end = timeSeconds(window.endTime);
    if (start === null) errors[field("start_time")] = "Enter a valid time in Philippine Time.";
    if (end === null) errors[field("end_time")] = "Enter a valid time in Philippine Time.";
    else if (start !== null && end <= start) errors[field("end_time")] = "End time must be after start time.";
    if (window.pattern === ReferralTimingPattern.SPECIFIC_DATE) {
      if (!validDate(window.date)) errors[field("date")] = "Enter a valid date.";
      else if (window.date < today) errors[field("date")] = "Date must be today or later in Philippine Time.";
    } else {
      if (!Object.values(ReferralTimingWeekday).some(value => value === window.weekday)) errors[field("weekday")] = "Choose Monday to Saturday.";
      if (!validDate(window.validUntil)) errors[field("valid_until")] = "Enter a valid date.";
      else if (window.validUntil < today || window.validUntil > maximum) errors[field("valid_until")] = "Valid until must be today to 180 days ahead in Philippine Time.";
    }
    // Compare normalized active fields; inactive input is kept locally when switching patterns.
    const signature = JSON.stringify([window.informationType, window.pattern, window.pattern === "SPECIFIC_DATE" ? window.date : window.weekday, window.pattern === "SPECIFIC_DATE" ? null : window.validUntil, start, end]);
    if (seen.has(signature)) errors[field("start_time")] = "This window duplicates another window.";
    seen.add(signature);
  });
  return errors;
}

export function timingWindowsRequest(draft: TimingDraft): ReferralTimingWindowRequest[] {
  if (draft.answer !== "KNOWN") return [];
  return draft.windows.map(window => ({
    information_type: window.informationType, pattern: window.pattern,
    start_time: window.startTime, end_time: window.endTime,
    date: window.pattern === "SPECIFIC_DATE" ? window.date : null,
    weekday: window.pattern === "RECURRING_WEEKDAY" && window.weekday ? window.weekday : null,
    valid_until: window.pattern === "RECURRING_WEEKDAY" ? window.validUntil : null,
  }));
}

export function timingStatementRequest(draft: TimingDraft): ReferralSchedulingStatementRequest | null {
  if (draft.answer !== "KNOWN" && draft.answer !== "UNKNOWN") return null;
  return { answer_kind: draft.answer, windows: timingWindowsRequest(draft), note: draft.answer === "KNOWN" ? draft.note : "" };
}

export function timingInputId(prefix: string, draft: TimingDraft, field: string): string {
  const parts = field.split(".");
  if (parts[0] === "windows" && parts.length === 3) return `${prefix}-window-${draft.windows[Number(parts[1])]?.key}-${parts[2]}`;
  if (field === "windows") return `${prefix}-add-window`;
  return `${prefix}-${field}`;
}

export function focusTimingError(prefix: string, draft: TimingDraft, errors: TimingFieldErrors): void {
  const fields = ["answer_kind", ...draft.windows.flatMap((_, index) =>
    ["information_type", "pattern", "date", "weekday", "valid_until", "start_time", "end_time"].map(field => `windows.${index}.${field}`)
  ), "windows", "note", "confirmation_source"];
  const first = fields.find(field => errors[field]) ?? Object.keys(errors)[0];
  if (first) requestAnimationFrame(() => document.getElementById(timingInputId(prefix, draft, first))?.focus());
}

function record(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object";
}
export function timingBackendErrors(error: unknown): TimingFieldErrors {
  if (!(error instanceof CompassApiError) || error.status !== 422 || !record(error.body) || !record(error.body.error) || !Array.isArray(error.body.error.details)) return {};
  const fields: TimingFieldErrors = {};
  for (const issue of error.body.error.details) {
    if (!record(issue) || !Array.isArray(issue.loc) || typeof issue.message !== "string") continue;
    const loc = issue.loc.map(String);
    const index = loc.findIndex(part => ["windows", "note", "answer_kind", "confirmation_source"].includes(part));
    if (index >= 0) fields[loc.slice(index).join(".")] = issue.message;
  }
  return fields;
}
