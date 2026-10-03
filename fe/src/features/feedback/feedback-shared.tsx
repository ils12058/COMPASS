import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { LoadingRegion } from "@/components/ui/loading-region";
import { Skeleton } from "@/components/ui/skeleton";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";
import { CompassApiError, readApiErrorCode } from "@/lib/api/errors";
import { formatInstitutionalDateTime } from "@/lib/institutional-time";
import { PageHeader } from "@/components/ui/page-header";
import { Notice } from "@/components/ui/notice";
import { PanelSection } from "@/components/ui/panel";
import { RowsSkeleton } from "@/components/ui/rows-skeleton";

const feedbackOpportunityIdPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function feedbackOpportunityId(value: string | null): string | null {
  return value && feedbackOpportunityIdPattern.test(value) ? value : null;
}

export function feedbackErrorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof CompassApiError)) return fallback;
  const code = readApiErrorCode(error.body);
  const known: Record<string, string> = {
    permission_denied: "You do not have permission to use this Feedback workspace.",
    feedback_not_found: "The requested Feedback response could not be found.",
    feedback_opportunity_not_found: "This Feedback opportunity is not available.",
    feedback_already_submitted: "Feedback for this service has already been submitted.",
    feedback_configuration_conflict:
      "Feedback is temporarily unavailable because its configuration needs attention.",
    invalid_feedback_request:
      "Some response values were not accepted. Review the form and try again.",
    invalid_idempotency_key:
      "This submission attempt could not be verified. Review the response and submit again.",
    idempotency_key_conflict:
      "This submission key was already used for different response details. Review the form and submit again.",
    idempotency_in_progress:
      "This exact submission is still being processed. Retry the same response shortly.",
    idempotency_unavailable:
      "The submission result could not be confirmed. Retry the same response safely.",
  };
  return (code && known[code]) || fallback;
}

export function feedbackErrorCode(error: unknown): string | undefined {
  return error instanceof CompassApiError ? readApiErrorCode(error.body) : undefined;
}

export function FeedbackPageHeading({
  eyebrow,
  title,
  description,
  action,
  headingId = "feedback-page-heading",
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: ReactNode;
  headingId?: string;
}) {
  return (
    <PageHeader
      title={title}
      headingId={headingId}
      context={eyebrow}
      description={description}
      actions={action}
      className="mb-0"
    />
  );
}

export function FeedbackSection({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: ReactNode;
}) {
  // One part of the instrument; the form renders the parts inside one Panel.
  return (
    <PanelSection title={title} titleId={"feedback-" + title.toLowerCase().replace(/[^a-z0-9]+/g, "-")} description={description}>
      <div className="space-y-5">{children}</div>
    </PanelSection>
  );
}

export function FeedbackFormSkeleton({ label }: { label: string }) {
  return (
    <LoadingRegion label={label} className="max-w-4xl">
      <Skeleton className="h-4 w-48" />
      <Skeleton className="mt-3 h-9 w-80 max-w-full" />
      <Skeleton className="mt-3 h-4 w-full max-w-2xl" />
      <div className="mt-8 space-y-6">
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    </LoadingRegion>
  );
}

export function FeedbackListSkeleton({ label }: { label: string }) {
  return <RowsSkeleton label={label} />;
}

export function FeedbackDetailSkeleton({ label }: { label: string }) {
  return (
    <LoadingRegion label={label}>
      <Skeleton className="h-4 w-48" />
      <Skeleton className="mt-3 h-9 w-72 max-w-full" />
      <Skeleton className="mt-3 h-4 w-56" />
      <div className="mt-8 grid gap-x-8 gap-y-5 sm:grid-cols-2">
        {Array.from({ length: 6 }, (_, index) => (
          <Skeleton key={index} className="h-12 w-full" />
        ))}
      </div>
    </LoadingRegion>
  );
}

export function FeedbackAccessUnavailable({
  title = "Feedback unavailable",
  message = "Feedback is unavailable to this account.",
}: {
  title?: string;
  message?: string;
}) {
  return <WorkspaceUnavailable title={title}>{message}</WorkspaceUnavailable>;
}

export function FeedbackQueryError({
  error,
  fallback,
  onRetry,
}: {
  error: unknown;
  fallback: string;
  onRetry: () => void;
}) {
  return (
    <Notice
      tone="danger"
      role="alert"
      action={<Button variant="secondary" onClick={onRetry}>Retry</Button>}
    >
      {feedbackErrorMessage(error, fallback)}
    </Notice>
  );
}

export function FeedbackDate({ value }: { value: string }) {
  return <time dateTime={value}>{formatInstitutionalDateTime(value)}</time>;
}

export type RadioChoice = { value: string | number; label: string };

export function FeedbackRadioGroup({
  legend,
  name,
  value,
  choices,
  onChange,
  columns = 2,
  disabled = false,
  required = false,
  hint,
}: {
  legend: string;
  name: string;
  value: string | number | null;
  choices: readonly RadioChoice[];
  onChange: (value: string | number) => void;
  columns?: 1 | 2 | 3 | 6;
  disabled?: boolean;
  required?: boolean;
  hint?: string;
}) {
  const grid = columns === 1 ? "grid-cols-1" : columns === 2 ? "grid-cols-1 sm:grid-cols-2" : columns === 3 ? "grid-cols-1 sm:grid-cols-3" : "grid-cols-2 sm:grid-cols-3 lg:grid-cols-6";
  return (
    <fieldset className="min-w-0" disabled={disabled}>
      <legend className="text-sm font-semibold text-ink">
        {legend}{required ? <span aria-hidden="true" className="text-danger"> *</span> : null}
      </legend>
      {hint ? <p className="mt-1 text-xs leading-5 text-muted">{hint}</p> : null}
      <div className={`mt-3 grid gap-x-4 gap-y-3 ${grid}`}>
        {choices.map((choice, index) => {
          const id = `${name}-${index}`;
          return (
            <label key={String(choice.value)} htmlFor={id} className="flex min-h-10 items-start gap-2 text-sm leading-5 text-ink">
              <input
                id={id}
                className="mt-1 h-4 w-4 shrink-0 accent-brand"
                type="radio"
                name={name}
                value={String(choice.value)}
                checked={value === choice.value}
                required={required && index === 0}
                onChange={() => onChange(choice.value)}
              />
              <span>{choice.label}</span>
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}

export function FeedbackFieldLabel({
  htmlFor,
  children,
  required = false,
}: {
  htmlFor: string;
  children: ReactNode;
  required?: boolean;
}) {
  return (
    <label htmlFor={htmlFor} className="block text-sm font-semibold text-ink">
      {children}{required ? <span aria-hidden="true" className="text-danger"> *</span> : null}
    </label>
  );
}

export function FeedbackRatingLabel({ value }: { value: number }) {
  return ({ 1: "Poor", 2: "Fair", 3: "Good", 4: "Very Good", 5: "Excellent" } as Record<number, string>)[value] ?? "Not recorded";
}
