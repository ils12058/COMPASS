import Link from "next/link";

import { FormRevisionStatusValue } from "@/lib/api/generated/model";

export function InstitutionWorkspaceUnavailable({
  workspace,
}: {
  workspace: string;
}) {
  return (
    <section
      aria-labelledby="institution-workspace-unavailable-heading"
      className="max-w-xl border-y border-border py-8"
    >
      <h1
        id="institution-workspace-unavailable-heading"
        className="font-heading text-3xl font-bold text-ink"
      >
        {workspace} unavailable
      </h1>
      <p className="mt-3 text-sm leading-6 text-muted">
        Your current access does not include this Institution workspace.
      </p>
      <Link
        className="mt-5 inline-block text-sm font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
        href="/portal"
      >
        Return to Home
      </Link>
    </section>
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
