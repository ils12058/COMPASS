// Year Level is stored and filtered as the number 1 through 10 (ADR-036). These labels are
// display text only and match the backend's report label, for example "3rd Year".
export const YEAR_LEVELS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10] as const;

export function yearLevelLabel(level: number): string {
  const lastTwo = level % 100;
  const suffix = lastTwo >= 11 && lastTwo <= 13
    ? "th"
    : ({ 1: "st", 2: "nd", 3: "rd" } as Record<number, string>)[level % 10] ?? "th";
  return `${level}${suffix} Year`;
}
