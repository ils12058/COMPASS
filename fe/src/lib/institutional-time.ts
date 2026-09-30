export const INSTITUTION_TIME_ZONE = "Asia/Manila";
export const INSTITUTION_TIME_ZONE_LABEL = "Philippine Time";

type CivilDateTimeParts = {
  year: number;
  month: number;
  day: number;
  hour: number;
  minute: number;
  second: number;
  millisecond: number;
};

const DATE_ONLY_PATTERN = /^(\d{4})-(\d{2})-(\d{2})$/;
const DATE_TIME_INPUT_PATTERN =
  /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,3}))?)?$/;

function pad(value: number, width = 2): string {
  return String(value).padStart(width, "0");
}

function utcMillis(parts: CivilDateTimeParts): number {
  const date = new Date(0);
  date.setUTCFullYear(parts.year, parts.month - 1, parts.day);
  date.setUTCHours(parts.hour, parts.minute, parts.second, parts.millisecond);
  return date.getTime();
}

function isValidCivilParts(parts: CivilDateTimeParts): boolean {
  const date = new Date(utcMillis(parts));
  return (
    date.getUTCFullYear() === parts.year &&
    date.getUTCMonth() + 1 === parts.month &&
    date.getUTCDate() === parts.day &&
    date.getUTCHours() === parts.hour &&
    date.getUTCMinutes() === parts.minute &&
    date.getUTCSeconds() === parts.second &&
    date.getUTCMilliseconds() === parts.millisecond
  );
}

function parseDateOnly(value: string): CivilDateTimeParts | null {
  const match = DATE_ONLY_PATTERN.exec(value);
  if (!match) return null;
  const parts: CivilDateTimeParts = {
    year: Number(match[1]),
    month: Number(match[2]),
    day: Number(match[3]),
    hour: 0,
    minute: 0,
    second: 0,
    millisecond: 0,
  };
  return isValidCivilParts(parts) ? parts : null;
}

function parseDateTimeInput(value: string): CivilDateTimeParts | null {
  const match = DATE_TIME_INPUT_PATTERN.exec(value);
  if (!match) return null;
  const fraction = match[7] ?? "";
  const parts: CivilDateTimeParts = {
    year: Number(match[1]),
    month: Number(match[2]),
    day: Number(match[3]),
    hour: Number(match[4]),
    minute: Number(match[5]),
    second: Number(match[6] ?? "0"),
    millisecond: Number(fraction.padEnd(3, "0") || "0"),
  };
  return isValidCivilParts(parts) ? parts : null;
}

function partsInZone(date: Date, timeZone: string): CivilDateTimeParts | null {
  if (Number.isNaN(date.getTime())) return null;
  try {
    const formatter = new Intl.DateTimeFormat("en-CA-u-ca-gregory-nu-latn", {
      timeZone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hourCycle: "h23",
    });
    const values = new Map(
      formatter
        .formatToParts(date)
        .filter((part) => part.type !== "literal")
        .map((part): [string, string] => [part.type, part.value]),
    );
    const parts: CivilDateTimeParts = {
      year: Number(values.get("year")),
      month: Number(values.get("month")),
      day: Number(values.get("day")),
      hour: Number(values.get("hour")),
      minute: Number(values.get("minute")),
      second: Number(values.get("second")),
      millisecond: date.getUTCMilliseconds(),
    };
    return isValidCivilParts(parts) ? parts : null;
  } catch {
    return null;
  }
}

function offsetMillisecondsAt(instantMilliseconds: number, timeZone: string): number | null {
  const wholeSecond = Math.trunc(instantMilliseconds / 1000) * 1000;
  const parts = partsInZone(new Date(wholeSecond), timeZone);
  if (!parts) return null;
  return utcMillis({ ...parts, millisecond: 0 }) - wholeSecond;
}

function civilDateTimeToInstant(
  parts: CivilDateTimeParts,
  timeZone: string,
): Date | null {
  const wallClockAsUtc = utcMillis({ ...parts, millisecond: 0 });
  let candidate = wallClockAsUtc;

  for (let iteration = 0; iteration < 4; iteration += 1) {
    const offset = offsetMillisecondsAt(candidate, timeZone);
    if (offset === null) return null;
    const next = wallClockAsUtc - offset;
    if (next === candidate) break;
    candidate = next;
  }

  const result = new Date(candidate + parts.millisecond);
  const roundTrip = partsInZone(result, timeZone);
  if (
    !roundTrip ||
    roundTrip.year !== parts.year ||
    roundTrip.month !== parts.month ||
    roundTrip.day !== parts.day ||
    roundTrip.hour !== parts.hour ||
    roundTrip.minute !== parts.minute ||
    roundTrip.second !== parts.second
  ) {
    return null;
  }
  return result;
}

function formatDateTimeInputParts(parts: CivilDateTimeParts): string {
  return (
    `${pad(parts.year, 4)}-${pad(parts.month)}-${pad(parts.day)}T` +
    `${pad(parts.hour)}:${pad(parts.minute)}`
  );
}

function formatDateInputParts(parts: CivilDateTimeParts): string {
  return `${pad(parts.year, 4)}-${pad(parts.month)}-${pad(parts.day)}`;
}

export function institutionalDateTimeInputToISO(value: string): string | null {
  const parts = parseDateTimeInput(value);
  const instant = parts ? civilDateTimeToInstant(parts, INSTITUTION_TIME_ZONE) : null;
  return instant ? instant.toISOString() : null;
}

export function isoToInstitutionalDateTimeInput(
  value: string | null | undefined,
): string {
  if (!value) return "";
  const parts = partsInZone(new Date(value), INSTITUTION_TIME_ZONE);
  return parts ? formatDateTimeInputParts(parts) : "";
}

export function institutionalDateInputValue(date = new Date()): string {
  const parts = partsInZone(date, INSTITUTION_TIME_ZONE);
  return parts ? formatDateInputParts(parts) : "";
}

export function institutionalDateTimeInputValue(date = new Date()): string {
  const parts = partsInZone(date, INSTITUTION_TIME_ZONE);
  return parts ? formatDateTimeInputParts(parts) : "";
}

export function isFutureInstitutionalDateInput(
  value: string,
  now = new Date(),
): boolean {
  return parseDateOnly(value) !== null && value > institutionalDateInputValue(now);
}

export function isFutureInstitutionalDateTimeInput(
  value: string,
  now = new Date(),
): boolean {
  const instant = institutionalDateTimeInputToISO(value);
  return instant !== null && new Date(instant).getTime() > now.getTime();
}

export function formatDateOnly(
  value: string | null | undefined,
  options?: { dateStyle?: "medium" | "long" },
): string {
  if (!value) return "Not recorded";
  const parts = parseDateOnly(value);
  if (!parts) return value;
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: options?.dateStyle ?? "medium",
    timeZone: "UTC",
  }).format(new Date(utcMillis(parts)));
}

export function formatDateTimeInZone(
  value: string | null | undefined,
  timeZone: string,
): string {
  if (!value) return "Not recorded";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  try {
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone,
    }).format(date);
  } catch {
    return value;
  }
}

export function formatInstitutionalDateTime(
  value: string | null | undefined,
): string {
  return formatDateTimeInZone(value, INSTITUTION_TIME_ZONE);
}
