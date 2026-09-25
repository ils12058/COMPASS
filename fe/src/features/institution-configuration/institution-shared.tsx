import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";
import { FormRevisionStatusValue } from "@/lib/api/generated/model";

export function InstitutionWorkspaceUnavailable({
  workspace,
}: {
  workspace: string;
}) {
  return (
    <WorkspaceUnavailable title={`${workspace} unavailable`}>
      Your current access does not include {workspace}.
    </WorkspaceUnavailable>
  );
}

export function FormRevisionStatusBadge({
  status,
}: {
  status: FormRevisionStatusValue;
}) {
  const active = status === FormRevisionStatusValue.ACTIVE;
  return (
    <span
      className={
        "inline-flex rounded-full border px-2 py-0.5 text-xs font-semibold " +
        (active
          ? "border-success/30 bg-success/10 text-success"
          : "border-border bg-surface-muted text-muted")
      }
    >
      {active ? "Active" : "Inactive"}
    </span>
  );
}

export function InstitutionActionFeedback({
  error,
  notice,
  errorId,
}: {
  error: string | null;
  notice: string | null;
  errorId?: string;
}) {
  return (
    <>
      {error ? (
        <p id={errorId} role="alert" className="mt-4 text-sm leading-6 text-danger">
          {error}
        </p>
      ) : null}
      {notice ? (
        <p role="status" className="mt-4 text-sm leading-6 text-muted">
          {notice}
        </p>
      ) : null}
    </>
  );
}
