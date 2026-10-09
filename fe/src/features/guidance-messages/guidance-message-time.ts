import { INSTITUTION_TIME_ZONE, institutionalDateInputValue } from "@/lib/institutional-time";

// Message times read in institutional civil time (ADR-096), like Notifications. Day boundaries
// ("Today", "Yesterday") follow the institution's calendar, not the browser's time zone.

const DAY_MS = 86_400_000;

const timeOfDay = new Intl.DateTimeFormat("en-PH", {
  hour: "numeric",
  minute: "2-digit",
  timeZone: INSTITUTION_TIME_ZONE,
});
const monthDay = new Intl.DateTimeFormat("en-PH", {
  month: "short",
  day: "numeric",
  timeZone: INSTITUTION_TIME_ZONE,
});
const shortDate = new Intl.DateTimeFormat("en-PH", {
  dateStyle: "medium",
  timeZone: INSTITUTION_TIME_ZONE,
});
const longDate = new Intl.DateTimeFormat("en-PH", {
  weekday: "long",
  month: "long",
  day: "numeric",
  year: "numeric",
  timeZone: INSTITUTION_TIME_ZONE,
});
const dateTime = new Intl.DateTimeFormat("en-PH", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: INSTITUTION_TIME_ZONE,
});

function parse(value: string | null | undefined): Date | null {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

/** The institutional calendar day of an instant, as YYYY-MM-DD. */
export function messageDayKey(value: string): string {
  const date = parse(value);
  return date ? institutionalDateInputValue(date) : "";
}

/** A directory row's last activity: the time today, "Yesterday", a date this year, or a full date. */
export function threadActivityTime(value: string | null | undefined, now = new Date()): string {
  const date = parse(value);
  if (!date) return "";
  const day = institutionalDateInputValue(date);
  const today = institutionalDateInputValue(now);
  if (day === today) return timeOfDay.format(date);
  if (day === institutionalDateInputValue(new Date(now.getTime() - DAY_MS))) return "Yesterday";
  if (day.slice(0, 4) === today.slice(0, 4)) return monthDay.format(date);
  return shortDate.format(date);
}

/** The time printed beside one Message; its day comes from the separator above it. */
export function messageTime(value: string): string {
  const date = parse(value);
  return date ? timeOfDay.format(date) : "Time unavailable";
}

/** The separator between days in a conversation. */
export function messageDayLabel(value: string, now = new Date()): string {
  const date = parse(value);
  if (!date) return "Date unavailable";
  const day = institutionalDateInputValue(date);
  if (day === institutionalDateInputValue(now)) return "Today";
  if (day === institutionalDateInputValue(new Date(now.getTime() - DAY_MS))) return "Yesterday";
  return longDate.format(date);
}

/** A full readable date and time, such as a Counseling appointment's start. */
export function guidanceDateTime(value: string | null | undefined): string {
  const date = parse(value);
  return date ? dateTime.format(date) : "Date unavailable";
}
