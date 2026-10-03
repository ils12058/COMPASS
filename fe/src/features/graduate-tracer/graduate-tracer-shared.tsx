import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { CompassApiError, readApiErrorCode } from "@/lib/api/errors";
import { PageHeader } from "@/components/ui/page-header";
import { Notice } from "@/components/ui/notice";
import { PanelSection } from "@/components/ui/panel";

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
      return "Only graduates can start, edit, or submit a Graduate Tracer response.";
    case "graduate_tracer_conflict":
      return "The response changed or became unavailable before this action completed. Check its current status before continuing.";
    case "invalid_graduate_tracer_request":
      return "Review the survey answers and correct the invalid values.";
    case "permission_denied":
      return "You cannot complete this Graduate Tracer action with this account.";
    default:
      return fallback;
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
  return <PageHeader title={title} headingId={id} description={description} actions={action} className="mb-0" />;
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
    <Notice
      tone="danger"
      role="alert"
      action={onRetry ? <Button variant="secondary" onClick={onRetry}>Retry</Button> : undefined}
    >
      {graduateTracerErrorMessage(error, fallback)}
    </Notice>
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
  // One part of the official survey; the form or response renders the parts inside one Panel.
  // The section is a jump-link target, so it takes focus without drawing a ring.
  return (
    <PanelSection id={id} tabIndex={-1} title={title} titleId={headingId} className="scroll-mt-6 focus:outline-none">
      <div className="space-y-6">{children}</div>
    </PanelSection>
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
