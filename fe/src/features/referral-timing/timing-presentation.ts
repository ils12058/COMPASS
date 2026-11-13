import type { ReferralSchedulingStatementResponse, ReferralTimingStatus, ReferralTimingWindowRequest } from "@/lib/api/generated/model";
import { formatInstitutionalDateTime, institutionalDateInputValue, institutionalDateTimeInputToISO } from "@/lib/institutional-time";
import { addCivilDays } from "./timing-draft";

export function formatTimingWindowTime(time: string): string {
  const minuteOnly = /^(\d{2}:\d{2}):00(?:\.0+)?$/.exec(time);
  return minuteOnly ? minuteOnly[1] : time;
}

export function timingStatusLabel(status?: ReferralTimingStatus): string {
  return status === "KNOWN" ? "Timing: Known" : status === "UNKNOWN" ? "Timing: Unknown" : "Timing: Not provided";
}

export function reportedProvenance(statement: ReferralSchedulingStatementResponse): string {
  const time = `${formatInstitutionalDateTime(statement.created_at)} · Philippine Time`;
  return statement.submission_channel === "FACULTY_PORTAL"
    ? `Reported by ${statement.author_name} on ${time}`
    : `Reported by the referrer, recorded by ${statement.author_name} on ${time}`;
}

export function timingWindowExpired(window: ReferralTimingWindowRequest, now = new Date()): boolean {
  if (window.pattern === "SPECIFIC_DATE" && window.date) {
    const end = institutionalDateTimeInputToISO(`${window.date}T${window.end_time}`);
    return end !== null && new Date(end).getTime() <= now.getTime();
  }
  return window.pattern === "RECURRING_WEEKDAY" && !!window.valid_until && window.valid_until < institutionalDateInputValue(now);
}

export function timingWindowExpiry(window: ReferralTimingWindowRequest): string | null {
  return window.pattern === "SPECIFIC_DATE" && window.date
    ? institutionalDateTimeInputToISO(`${window.date}T${window.end_time}`)
    : window.valid_until ? institutionalDateTimeInputToISO(`${addCivilDays(window.valid_until, 1)}T00:00`) : null;
}
