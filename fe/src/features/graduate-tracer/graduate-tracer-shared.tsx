import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { CompassApiError, readApiErrorCode, readApiErrorMessage } from "@/lib/api/errors";

export function graduateTracerErrorCode(error: unknown): string | undefined {
  return error instanceof CompassApiError ? readApiErrorCode(error.body) : undefined;
}

export function isUncertainGraduateTracerMutation(error: unknown): boolean {
  return !(error instanceof CompassApiError) || error.status >= 500;
}

export function graduateTracerErrorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof CompassApiError)) return fallback;
  switch (readApiErrorCode(error.body)) {
    case "graduate_tracer_not_found":
      return "The Graduate Tracer response could not be found or is no longer available.";
    case "graduated_student_required":
      return "Starting, editing, or submitting requires the Student lifecycle to be Graduated.";
    case "graduate_tracer_conflict":
      return "The response changed or became unavailable before this action completed. Check its current status before continuing.";
    case "invalid_graduate_tracer_request":
      return readApiErrorMessage(error.body) ?? "Review the survey answers and correct the invalid values.";
    case "permission_denied":
      return "Your current access does not allow this Graduate Tracer action.";
    default:
      return readApiErrorMessage(error.body) ?? fallback;
  }
}

export function GraduateTracerHeading({
  id,
  title,
  description,
  action,
}: {
  id?: string;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <header className="flex flex-col gap-4 border-b border-border pb-6 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 id={id} className="font-heading text-3xl font-bold text-ink">{title}</h1>
        {description ? <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">{description}</p> : null}
      </div>
      {action}
    </header>
  );
}

export function GraduateTracerError({
  error,
  fallback,
  onRetry,
}: {
  error?: unknown;
  fallback: string;
  onRetry?: () => void;
}) {
  return (
    <div role="alert" className="border-y border-danger/30 py-4 text-sm leading-6 text-ink">
      <p>{graduateTracerErrorMessage(error, fallback)}</p>
      {onRetry ? <Button variant="secondary" className="mt-3" onClick={onRetry}>Retry</Button> : null}
    </div>
  );
}

export function GraduateTracerSection({
  id,
  title,
  children,
}: {
  id: string;
  title: string;
  children: ReactNode;
}) {
  const headingId = `${id}-heading`;
  return (
    <section id={id} tabIndex={-1} aria-labelledby={headingId} className="scroll-mt-6 border-t border-border py-6 focus:outline-none">
      <h2 id={headingId} className="font-heading text-xl font-semibold text-ink">{title}</h2>
      <div className="mt-5 space-y-6">{children}</div>
    </section>
  );
}

export function GraduateTracerAnswer({
  label,
  value,
}: {
  label: string;
  value: string | null | undefined;
}) {
  return (
    <div className="min-w-0">
      <dt className="text-xs font-semibold text-muted">{label}</dt>
      <dd className="mt-1 whitespace-pre-wrap break-words text-sm leading-6 text-ink">{value?.trim() || "Not provided"}</dd>
    </div>
  );
}

export function GraduateTracerStatus({ submitted }: { submitted: boolean }) {
  return (
    <span className={`inline-flex min-h-7 items-center rounded-full border px-2.5 text-xs font-semibold ${submitted ? "border-info/30 bg-info/10 text-info" : "border-border bg-surface-muted text-muted"}`}>
      {submitted ? "Submitted" : "Draft"}
    </span>
  );
}
