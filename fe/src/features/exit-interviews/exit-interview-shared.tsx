import Link from "next/link";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { CompassApiError, readApiErrorCode, readApiErrorMessage } from "@/lib/api/errors";
import type { ExitInterviewStatusValue } from "@/lib/api/generated/model";

export function exitInterviewErrorCode(error: unknown): string | undefined {
  return error instanceof CompassApiError
    ? readApiErrorCode(error.body)
    : undefined;
}

export function shouldHideExitInterviewCachedData(error: unknown): boolean {
  return (
    error instanceof CompassApiError &&
    (error.status === 401 || error.status === 403 || error.status === 404)
  );
}

export function exitInterviewErrorMessage(
  error: unknown,
  fallback: string,
): string {
  if (!(error instanceof CompassApiError)) return fallback;

  switch (readApiErrorCode(error.body)) {
    case "exit_interview_not_found":
      return "This Exit Interview could not be found or is no longer available.";
    case "exit_interview_inventory_required":
      return "A submitted Individual Inventory for the current Academic Year is required before starting an Exit Interview.";
    case "current_student_required":
      return "Starting, editing, or submitting an Exit Interview requires CURRENT Student lifecycle under the current institutional rule.";
    case "current_academic_year_not_configured":
      return "A current Academic Year is not configured. Contact the institutional administrator.";
    case "exit_interview_not_submitted":
      return "This Exit Interview is currently a draft and is not available for Head Guidance review until the Student submits it.";
    case "exit_interview_conflict":
      return "The Exit Interview changed before this action completed. Refresh the record and review its current status.";
    case "permission_denied":
      return "Your current access does not allow this Exit Interview action.";
    default:
      return readApiErrorMessage(error.body) ?? fallback;
  }
}

export function isUncertainExitInterviewMutation(error: unknown): boolean {
  return !(error instanceof CompassApiError) || error.status >= 500;
}

export function ExitInterviewHeading({
  title,
  description,
  action,
  id,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
  id?: string;
}) {
  return (
    <header className="border-b border-border pb-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 id={id} className="font-heading text-3xl font-bold text-ink">
            {title}
          </h1>
          {description ? (
            <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
              {description}
            </p>
          ) : null}
        </div>
        {action}
      </div>
    </header>
  );
}

export function ExitInterviewStatus({
  status,
}: {
  status: ExitInterviewStatusValue;
}) {
  const style =
    status === "SUBMITTED"
      ? "border-info/30 bg-info/10 text-info"
      : "border-border bg-surface-muted text-muted";
  return (
    <span className={`inline-flex min-h-7 items-center rounded-full border px-2.5 text-xs font-semibold ${style}`}>
      {status === "DRAFT" ? "Draft" : "Submitted"}
    </span>
  );
}

export function ExitInterviewSection({
  title,
  children,
  id,
}: {
  title: string;
  children: ReactNode;
  id?: string;
}) {
  const headingId = id ?? title.toLowerCase().replace(/[^a-z0-9]+/g, "-");
  return (
    <section aria-labelledby={headingId} className="border-t border-border py-6">
      <h2 id={headingId} className="font-heading text-xl font-semibold text-ink">
        {title}
      </h2>
      {children}
    </section>
  );
}

export function ExitInterviewField({
  label,
  value,
}: {
  label: string;
  value: string | null | undefined;
}) {
  return (
    <div className="min-w-0">
      <dt className="text-xs font-semibold text-muted">{label}</dt>
      <dd className="mt-1 whitespace-pre-wrap break-words text-sm text-ink">
        {value?.trim() || "Not provided"}
      </dd>
    </div>
  );
}

export function ExitInterviewUnavailable({
  title = "Exit Interview unavailable",
  message = "Your current access does not include this Exit Interview workspace.",
}: {
  title?: string;
  message?: string;
}) {
  return (
    <section className="max-w-xl border-y border-border py-8">
      <h1 className="font-heading text-3xl font-bold text-ink">{title}</h1>
      <p className="mt-3 text-sm leading-6 text-muted">{message}</p>
      <Link
        href="/portal"
        className="mt-5 inline-block text-sm font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
      >
        Return to Home
      </Link>
    </section>
  );
}

export function ExitInterviewError({
  error,
  fallback,
  onRetry,
}: {
  error: unknown;
  fallback: string;
  onRetry?: () => void;
}) {
  return (
    <div role="alert" className="border-y border-danger/30 py-5">
      <p className="text-sm text-danger">
        {exitInterviewErrorMessage(error, fallback)}
      </p>
      {onRetry ? (
        <Button variant="secondary" className="mt-3" onClick={onRetry}>
          Retry
        </Button>
      ) : null}
    </div>
  );
}
