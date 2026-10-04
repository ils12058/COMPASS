import {
  AvailabilityModeScope,
  Weekday,
  type WeeklyWindowRequest,
  type WeeklyWindowResponse,
} from "@/lib/api/generated/model";

// Recurring weekly hours as the editor holds them before saving. Saving replaces the whole
// schedule with these windows (the backend's replace contract); nothing here talks to the server.
export type DraftWindow = {
  key: string;
  weekday: Weekday;
  start_time: string;
  end_time: string;
  mode_scope: AvailabilityModeScope;
};

export const weekdayOrder: Weekday[] = [
  Weekday.MONDAY,
  Weekday.TUESDAY,
  Weekday.WEDNESDAY,
  Weekday.THURSDAY,
  Weekday.FRIDAY,
  Weekday.SATURDAY,
  Weekday.SUNDAY,
];

export const weekdayLabels: Record<Weekday, string> = {
  [Weekday.MONDAY]: "Monday",
  [Weekday.TUESDAY]: "Tuesday",
  [Weekday.WEDNESDAY]: "Wednesday",
  [Weekday.THURSDAY]: "Thursday",
  [Weekday.FRIDAY]: "Friday",
  [Weekday.SATURDAY]: "Saturday",
  [Weekday.SUNDAY]: "Sunday",
};

export const weekdayShortLabels: Record<Weekday, string> = {
  [Weekday.MONDAY]: "Mon",
  [Weekday.TUESDAY]: "Tue",
  [Weekday.WEDNESDAY]: "Wed",
  [Weekday.THURSDAY]: "Thu",
  [Weekday.FRIDAY]: "Fri",
  [Weekday.SATURDAY]: "Sat",
  [Weekday.SUNDAY]: "Sun",
};

export function draftFromWindows(windows: WeeklyWindowResponse[]): DraftWindow[] {
  return windows.map((window) => ({
    key: window.id,
    weekday: window.weekday,
    start_time: window.start_time.slice(0, 5),
    end_time: window.end_time.slice(0, 5),
    mode_scope: window.mode_scope,
  }));
}

// A window for "All delivery modes" overlaps both In person and Online.
export function scopesOverlap(left: AvailabilityModeScope, right: AvailabilityModeScope): boolean {
  return left === right || left === AvailabilityModeScope.ALL || right === AvailabilityModeScope.ALL;
}

export type DraftProblem = { weekday: Weekday; message: string };

// The first problem that stops the schedule from saving, tied to the day the reader must fix.
export function validateDraft(draft: DraftWindow[]): DraftProblem | null {
  for (const window of draft) {
    if (!window.start_time || !window.end_time) {
      return { weekday: window.weekday, message: "Each recurring window needs a start and end time." };
    }
    if (window.start_time >= window.end_time) {
      return {
        weekday: window.weekday,
        message: weekdayLabels[window.weekday] + " contains a window whose start time is not earlier than its end time.",
      };
    }
  }

  for (const weekday of weekdayOrder) {
    const rows = draft.filter((window) => window.weekday === weekday);
    for (let leftIndex = 0; leftIndex < rows.length; leftIndex += 1) {
      for (let rightIndex = leftIndex + 1; rightIndex < rows.length; rightIndex += 1) {
        const left = rows[leftIndex];
        const right = rows[rightIndex];
        const timeOverlap = left.start_time < right.end_time && right.start_time < left.end_time;
        if (timeOverlap && scopesOverlap(left.mode_scope, right.mode_scope)) {
          return { weekday, message: weekdayLabels[weekday] + " has overlapping hours for the same delivery mode." };
        }
      }
    }
  }

  return null;
}

export function requestFromDraft(draft: DraftWindow[]): WeeklyWindowRequest[] {
  return draft.map((window) => ({
    weekday: window.weekday,
    start_time: window.start_time,
    end_time: window.end_time,
    mode_scope: window.mode_scope,
  }));
}

export function windowsForDay<T extends { weekday: Weekday }>(windows: T[], weekday: Weekday): T[] {
  return windows.filter((window) => window.weekday === weekday);
}

// "08:00" → "8:00 AM". Recurring hours are wall-clock times in the institution's day, so they are
// formatted as written rather than converted between time zones.
export function formatClockTime(value: string): string {
  const match = /^(\d{2}):(\d{2})/.exec(value);
  if (!match) return value;
  const hours = Number(match[1]);
  const suffix = hours >= 12 ? "PM" : "AM";
  const hour12 = hours % 12 === 0 ? 12 : hours % 12;
  return `${hour12}:${match[2]} ${suffix}`;
}

export function formatClockRange(start: string, end: string): string {
  return `${formatClockTime(start)} – ${formatClockTime(end)}`;
}
