import { institutionalDateInputValue } from "@/lib/institutional-time";

const CANONICAL_LABEL = /^(\d{4})-(\d{4})$/;
const EARLIEST_DEFAULT_START_YEAR = 1900;
const UPCOMING_YEAR_WINDOW = 10;

export type AcademicYearOption = {
  startYear: number;
  label: string;
  exists: boolean;
};

export function currentInstitutionCalendarYear(now = new Date()): number {
  return Number(institutionalDateInputValue(now).slice(0, 4));
}

export function academicYearLabel(startYear: number): string {
  return `${String(startYear).padStart(4, "0")}-${String(startYear + 1).padStart(4, "0")}`;
}

function existingCanonicalStarts(labels: readonly string[]): Set<number> {
  const starts = new Set<number>();
  for (const label of labels) {
    const match = CANONICAL_LABEL.exec(label);
    if (!match) continue;
    const start = Number(match[1]);
    const end = Number(match[2]);
    if (start >= 1 && start <= 9998 && end === start + 1) starts.add(start);
  }
  return starts;
}

export function academicYearOptions(
  currentYear: number,
  existingLabels: readonly string[],
): AcademicYearOption[] {
  const existing = existingCanonicalStarts(existingLabels);
  const minYear = Math.min(EARLIEST_DEFAULT_START_YEAR, ...existing);
  const latestExisting = Math.max(0, ...existing);
  const maxYear = Math.min(
    9998,
    Math.max(currentYear + UPCOMING_YEAR_WINDOW, latestExisting + 1),
  );

  return Array.from({ length: maxYear - minYear + 1 }, (_, index) => {
    const startYear = minYear + index;
    return {
      startYear,
      label: academicYearLabel(startYear),
      exists: existing.has(startYear),
    };
  });
}

export function suggestedAcademicYearStart(
  currentYear: number,
  options: readonly AcademicYearOption[],
): number {
  const current = options.find((option) => option.startYear === currentYear && !option.exists);
  if (current) return current.startYear;

  const upcoming = options.find((option) => option.startYear > currentYear && !option.exists);
  if (upcoming) return upcoming.startYear;

  const historical = [...options]
    .reverse()
    .find((option) => option.startYear < currentYear && !option.exists);
  return historical?.startYear ?? options[0]?.startYear ?? currentYear;
}
