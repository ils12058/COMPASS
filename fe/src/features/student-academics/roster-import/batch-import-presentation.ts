import type { GraduationImportResponse, PeriodImportResponse } from "@/lib/api/generated/model";

export const termRecordsTemplate = "institutional_id,campus_code,college_code,year_level,enrollment_status\n";
export const graduationsTemplate = "institutional_id,campus_code,college_code,graduation_date\n";

const actionLabels: Record<string, string> = {
  CREATE: "New record",
  UPDATE: "Will change",
  GRADUATE: "Will graduate",
  NOOP: "No change",
  CONFLICT: "Problem",
  INVALID: "Problem",
};

export function batchRowActionLabel(action: string): string {
  return actionLabels[action] ?? action;
}

const enrollmentLabels: Record<string, string> = {
  ENROLLED: "Enrolled",
  NOT_ENROLLED: "Not enrolled",
  UNKNOWN: "Unknown",
};

export function enrollmentLabel(value: string | null | undefined): string {
  return value ? (enrollmentLabels[value] ?? value) : "—";
}

/** "Year 2 · Enrolled", or "—" when there is no record yet. */
export function termFacts(yearLevel: number | null | undefined, status: string | null | undefined): string {
  if (yearLevel == null && !status) return "—";
  return `${yearLevel == null ? "No year level" : `Year ${yearLevel}`} · ${enrollmentLabel(status)}`;
}

export function periodWriteCount(report: PeriodImportResponse): number {
  return report.create_count + report.update_count;
}

/** The apply step is offered only for the exact file and choices the shown preview checked. */
export function batchCommitReady({
  file,
  reviewed,
  scope,
  report,
  conflict,
  writes,
}: {
  file: File | null;
  reviewed: { file: File; scope: string } | null;
  scope: string;
  report: PeriodImportResponse | GraduationImportResponse | null;
  conflict: boolean;
  writes: number;
}): boolean {
  return Boolean(
    file &&
      reviewed?.file === file &&
      reviewed.scope === scope &&
      report?.valid &&
      !report.committed &&
      !conflict &&
      writes > 0,
  );
}

/** The typed confirmation must be exactly the number of Students the import will record. */
export function typedCountMatches(typed: string, expected: number): boolean {
  return /^\d+$/.test(typed.trim()) && Number(typed.trim()) === expected;
}

export function graduationConsequence(report: GraduationImportResponse): string {
  const students = (count: number) => `${count} ${count === 1 ? "Student" : "Students"}`;
  const parts = [`${students(report.graduate_count)} will become Graduated`];
  if (report.update_count) parts.push(`${students(report.update_count)} will have their graduation record updated`);
  if (report.placement_cleared_count) {
    parts.push(`${students(report.placement_cleared_count)} will leave their current College placement`);
  }
  return `${parts.join("; ")}.`;
}
