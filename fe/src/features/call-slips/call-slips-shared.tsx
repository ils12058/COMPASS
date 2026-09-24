"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { CompassApiError, readApiErrorCode, readApiErrorMessage } from "@/lib/api/errors";

const knownCallSlipErrors: Record<string, string> = {
  permission_denied: "You do not have permission to use this Call Slip workspace.",
  call_slip_not_found: "Call Slip not found.",
  call_slip_not_permitted: "This Call Slip is not available within your current access.",
  call_slip_document_unavailable: "The document could not be released right now. Try again later.",
  release_audit_unavailable: "The document could not be released right now. Try again later.",
  invalid_call_slip_request: "The Call Slip request contains a value that was not accepted. Review the details and try again.",
  call_slip_conflict: "The Call Slip conflicts with the current record state. Refresh the record and review it before trying again.",
  idempotency_key_conflict: "This issuance attempt no longer matches its original details. Review the form and submit again.",
  recent_mfa_required: "Recent authenticator verification is required.",
};

export function callSlipErrorCode(error: unknown): string | undefined {
  return error instanceof CompassApiError ? readApiErrorCode(error.body) : undefined;
}

export function callSlipErrorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof CompassApiError)) return fallback;
  const code = readApiErrorCode(error.body);
  return (code && knownCallSlipErrors[code]) || readApiErrorMessage(error.body) || fallback;
}

export function uncertainCallSlipMutation(error: unknown): boolean {
  return !(error instanceof CompassApiError) || error.status >= 500;
}

export function CallSlipHeading({
  title,
  description,
  action,
  backHref,
  backLabel,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
  backHref?: string;
  backLabel?: string;
}) {
  return (
    <header className="border-b border-border pb-6">
      {backHref ? (
        <Link href={backHref} className="mb-4 inline-flex min-h-9 items-center text-sm font-semibold text-brand underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
          {backLabel ?? "Back to Call Slips"}
        </Link>
      ) : null}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="font-heading text-3xl font-bold text-ink">{title}</h1>
          {description ? <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">{description}</p> : null}
        </div>
        {action}
      </div>
    </header>
  );
}

export function CallSlipAccessUnavailable({
  title = "Call Slips unavailable",
  message = "Your current access does not include this Call Slip workspace.",
}: {
  title?: string;
  message?: string;
}) {
  return (
    <section className="max-w-xl border-y border-border py-8">
      <h1 className="font-heading text-3xl font-bold text-ink">{title}</h1>
      <p className="mt-3 text-sm leading-6 text-muted">{message}</p>
      <Link href="/portal" className="mt-5 inline-block text-sm font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
        Return to Home
      </Link>
    </section>
  );
}

export function CallSlipQueryError({
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
      <p className="text-sm text-danger">{callSlipErrorMessage(error, fallback)}</p>
      <Button variant="secondary" className="mt-3" onClick={onRetry}>Retry</Button>
    </div>
  );
}

export function CallSlipNotice({ children }: { children: ReactNode }) {
  return <p role="status" className="mt-4 text-sm text-muted">{children}</p>;
}

export function callSlipStateLabel(state: string, studentFacing = false): string {
  if (state === "ACTIVE") return "Active";
  if (state === "COMPLETED") return "Completed";
  if (state === "VOIDED") return studentFacing ? "Withdrawn" : "Voided";
  return state;
}

export function callSlipDestinationLabel(
  destinationType: string,
  otherDestination: string,
): string {
  return destinationType === "GUIDANCE_OFFICE" ? "Guidance Office" : otherDestination;
}
