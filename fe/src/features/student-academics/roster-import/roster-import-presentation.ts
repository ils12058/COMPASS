import type { RosterImportResponse } from "@/lib/api/generated/model";

export const rosterTemplate = "institutional_id,campus_code,college_code\n";

export type RosterIssue = {
  row: number | null;
  institutionalId: string;
  message: string;
};

const rowActionLabels: Record<string, string> = {
  SET: "Set",
  NOOP: "No change",
  CONFLICT: "Conflict",
  INVALID: "Invalid",
};

export function rosterRowActionLabel(action: string): string {
  return rowActionLabels[action] ?? action;
}

function errorBody(error: unknown): unknown {
  return error && typeof error === "object" && "body" in error
    ? (error as { body?: unknown }).body
    : undefined;
}

function errorDetail(body: unknown): Record<string, unknown> | null {
  if (!body || typeof body !== "object" || !("error" in body)) return null;
  const detail = (body as { error?: unknown }).error;
  return detail && typeof detail === "object" ? (detail as Record<string, unknown>) : null;
}

export function rosterIssues(error: unknown): RosterIssue[] {
  const details = errorDetail(errorBody(error))?.details;
  if (!Array.isArray(details)) return [];
  return details.flatMap((issue): RosterIssue[] => {
    if (
      !issue ||
      typeof issue !== "object" ||
      typeof (issue as { message?: unknown }).message !== "string"
    ) {
      return [];
    }
    const item = issue as Record<string, unknown>;
    return [
      {
        row: typeof item.row_number === "number" ? item.row_number : null,
        institutionalId: typeof item.institutional_id === "string" ? item.institutional_id : "",
        message: item.message as string,
      },
    ];
  });
}

export function rosterError(error: unknown, fallback: string): string {
  const detail = errorDetail(errorBody(error));
  if (detail?.code === "permission_denied") {
    return "The student_academics.import capability is required to import an academic roster.";
  }
  if (detail?.code === "identity_policy_unavailable") {
    return "Academic policy is temporarily unavailable. Try again later.";
  }
  return typeof detail?.message === "string" && detail.message ? detail.message : fallback;
}

export function rosterCommitReady({
  file,
  reviewedFile,
  report,
  conflict,
}: {
  file: File | null;
  reviewedFile: File | null;
  report: RosterImportResponse | null;
  conflict: boolean;
}): boolean {
  return Boolean(
    file &&
      reviewedFile === file &&
      report?.valid &&
      !report.committed &&
      !conflict &&
      report.set_count > 0,
  );
}
