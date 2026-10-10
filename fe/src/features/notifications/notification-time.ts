import { INSTITUTION_TIME_ZONE } from "@/lib/institutional-time";

const formatter = new Intl.DateTimeFormat("en-PH", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: INSTITUTION_TIME_ZONE,
});

export function notificationTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Date unavailable" : formatter.format(date);
}
