// Year Level is stored as a number. The Program API provides configured new-entry choices; this
// wider recorded domain remains for historical filters and Programs with pending policy.
export const RECORDED_YEAR_LEVELS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10] as const;

export function yearLevelLabel(level: number): string {
  const lastTwo = level % 100;
  const suffix = lastTwo >= 11 && lastTwo <= 13
    ? "th"
    : ({ 1: "st", 2: "nd", 3: "rd" } as Record<number, string>)[level % 10] ?? "th";
  return `${level}${suffix} Year`;
}

export function recordedYearLevelFilterLabel(level: number): string {
  return level > 4 ? `${yearLevelLabel(level)} (recorded value)` : yearLevelLabel(level);
}

export function retainYearLevelIfApplicable(
  yearLevel: number | null | undefined,
  availableLevels: readonly number[],
): number | null {
  return yearLevel !== null && yearLevel !== undefined && availableLevels.includes(yearLevel)
    ? yearLevel
    : null;
}
