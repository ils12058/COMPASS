import Link from "next/link";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { CompassApiError, readApiErrorCode, readApiErrorMessage } from "@/lib/api/errors";

export const feedbackSelectClass =
  "min-h-11 w-full rounded-md border border-border-strong bg-surface-raised px-3 py-2 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus";

export function feedbackErrorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof CompassApiError)) return fallback;
  const code = readApiErrorCode(error.body);
  const message = readApiErrorMessage(error.body);
  const known: Record<string, string> = {
    permission_denied: "You do not have permission to use this Feedback workspace.",
    feedback_not_found: "The requested Feedback response could not be found.",
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
  return (code && known[code]) || message || fallback;
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
    <header className="flex flex-col gap-4 border-b border-border pb-6 sm:flex-row sm:items-end sm:justify-between">
      <div>
        {eyebrow ? (
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-muted">
            {eyebrow}
          </p>
        ) : null}
        <h1 id={headingId} className="mt-1 font-heading text-3xl font-bold text-ink">{title}</h1>
        {description ? <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">{description}</p> : null}
      </div>
      {action}
    </header>
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
  return (
    <section aria-label={title} className="border-t border-border py-6 sm:py-7">
      <h2 className="font-heading text-xl font-semibold text-ink">{title}</h2>
      {description ? <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">{description}</p> : null}
      <div className="mt-5 space-y-5">{children}</div>
    </section>
  );
}

export function FeedbackAccessUnavailable({
  title = "Feedback unavailable",
  message = "Your current access does not include this Feedback workspace.",
}: {
  title?: string;
  message?: string;
}) {
  return (
    <section aria-labelledby="feedback-unavailable-heading" className="max-w-xl border-y border-border py-8">
      <h1 id="feedback-unavailable-heading" className="font-heading text-3xl font-bold text-ink">{title}</h1>
      <p className="mt-3 text-sm leading-6 text-muted">{message}</p>
      <Link href="/portal" className="mt-5 inline-block text-sm font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
        Return to Home
      </Link>
    </section>
  );
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
    <div role="alert" className="border-y border-danger/30 py-5">
      <p className="text-sm text-danger">{feedbackErrorMessage(error, fallback)}</p>
      <Button variant="secondary" className="mt-3" onClick={onRetry}>Retry</Button>
    </div>
  );
}

export function FeedbackDate({ value }: { value: string }) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return <time>{value}</time>;
  return <time dateTime={value}>{new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date)}</time>;
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
