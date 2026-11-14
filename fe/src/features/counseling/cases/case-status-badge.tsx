import { caseStatusLabel } from "@/features/counseling/cases/case-presentation";
import type { CounselingCaseStatus } from "@/lib/api/generated/model";

// The case's own lifecycle state. Waiting steps such as a pending transfer are separate facts and
// never replace it.
export function CaseStatusBadge({ status }: { status: CounselingCaseStatus }) {
  return (
    <span
      className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-semibold ${
        status === "ACTIVE"
          ? "border-success/30 bg-success/10 text-success"
          : "border-border bg-surface-muted text-muted"
      }`}
    >
      {caseStatusLabel(status)}
    </span>
  );
}
