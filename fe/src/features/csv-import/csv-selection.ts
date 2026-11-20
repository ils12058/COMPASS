import type {
  CsvImportResponse,
  GraduationImportResponse,
  PeriodImportResponse,
  RosterImportResponse,
} from "@/lib/api/generated/model";

type ImportReport = CsvImportResponse | RosterImportResponse | PeriodImportResponse | GraduationImportResponse;
export type CsvPreviewRow = ImportReport["rows"][number];
export type CsvStatusFilter = "all" | "ready" | "exists" | "problems";

export function rowStatus(row: Pick<CsvPreviewRow, "action">): Exclude<CsvStatusFilter, "all"> {
  if (["CREATE", "SET", "UPDATE", "GRADUATE"].includes(row.action)) return "ready";
  if (["SKIP", "NOOP"].includes(row.action)) return "exists";
  return "problems";
}

export function readyRowNumbers(rows: CsvPreviewRow[]): number[] {
  return rows.filter((row) => rowStatus(row) === "ready").map((row) => row.row_number);
}

export function toggleRow(rows: CsvPreviewRow[], selected: number[], number: number): number[] {
  const row = rows.find((item) => item.row_number === number);
  if (!row || rowStatus(row) === "problems") return selected;
  return selected.includes(number) ? selected.filter((item) => item !== number) : [...selected, number];
}

export function selectionSummary(rows: CsvPreviewRow[], selected: number[]) {
  const chosen = rows.filter((row) => selected.includes(row.row_number));
  const count = (action: string) => chosen.filter((row) => row.action === action).length;
  return {
    selected_count: chosen.length,
    create_count: count("CREATE"),
    set_count: count("SET"),
    update_count: count("UPDATE"),
    graduate_count: count("GRADUATE"),
    skip_count: count("SKIP"),
    noop_count: count("NOOP"),
    write_count: chosen.filter((row) => rowStatus(row) === "ready").length,
    placement_cleared_count: chosen.filter((row) =>
      rowStatus(row) === "ready" && "current_placement_college_code" in row && row.current_placement_college_code,
    ).length,
  };
}

export function selectionCountLabel(selected: number, total: number): string {
  return `Import ${selected} of ${total} rows`;
}

export function csvRowLabel(row: CsvPreviewRow, committed: boolean): string {
  if (rowStatus(row) === "exists") return "Already exists";
  if (rowStatus(row) === "problems") return "Has problems";
  if (!committed) return "Ready";
  const labels: Record<string, string> = {
    CREATE: "Created", SET: "Placement saved", UPDATE: "Updated", GRADUATE: "Graduation recorded",
  };
  return labels[row.action] ?? "Imported";
}

/** Keep reasons useful without exposing enum codes or field identifiers in the preview. */
export function csvProblemMessage(message: string): string {
  const labels: Record<string, string> = {
    institutional_id: "Institutional ID", campus_code: "Campus code", college_code: "College code",
    faculty_college_id: "Faculty college", program_code: "Program code", year_level: "Year level",
    enrollment_status: "Enrollment status", graduation_date: "Graduation date",
    first_name: "First name", middle_name: "Middle name", last_name: "Last name",
    role: "account role", STUDENT: "Student", FACULTY: "Faculty", IT_ADMIN: "IT Administrator",
    INSTITUTIONAL_OFFICER: "Institutional Officer", COUNSELOR: "Counselor",
    GUIDANCE_OFFICE_ASSISTANT: "Guidance Office Assistant", ENROLLED: "Enrolled",
    NOT_ENROLLED: "Not enrolled", UNKNOWN: "Unknown", CURRENT: "Current", GRADUATED: "Graduated",
    set_current_placement: "college placement", ACCOUNT_CSV_IMPORT: "account import",
  };
  return message.replace(/\b[A-Za-z_]+\b/g, (word) => labels[word] ?? word);
}

export function problemRowsCsv(headers: string[], rows: CsvPreviewRow[]): string {
  const quote = (value: string) => `"${value.replaceAll('"', '""')}"`;
  // A correction download can itself be previewed again. Replace its old note column.
  const sourceIndexes = headers.flatMap((header, index) => header.trim() === "problem" ? [] : [index]);
  const sourceHeaders = sourceIndexes.map((index) => headers[index]);
  const records = rows.filter((row) => rowStatus(row) === "problems").map((row) => [
    ...sourceIndexes.map((index) => row.values[index]), csvProblemMessage(row.message),
  ]);
  return [[...sourceHeaders, "problem"], ...records].map((fields) => fields.map(quote).join(",")).join("\r\n") + "\r\n";
}
