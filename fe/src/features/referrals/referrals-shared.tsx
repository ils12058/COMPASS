"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";
import { CompassApiError, readApiErrorCode, readApiErrorMessage } from "@/lib/api/errors";

const knownReferralErrors: Record<string, string> = {
  permission_denied: "You do not have permission to use this Referral workspace.",
  referral_not_found: "Referral not found.",
  referral_not_permitted: "This Referral is not available within your current Guidance access.",
  referral_document_unavailable: "The document could not be released right now. Try again later.",
  release_audit_unavailable: "The document could not be released right now. Try again later.",
  invalid_referral_request: "The Referral request contains a value that was not accepted. Review the details and try again.",
  referral_conflict: "The Referral has changed or conflicts with another recorded source action. Refresh the record and review it before trying again.",
  idempotency_key_conflict: "This creation attempt no longer matches its original details. Review the form and submit again.",
  recent_mfa_required: "Recent authenticator verification is required.",
};

export function referralErrorCode(error: unknown): string | undefined {
  return error instanceof CompassApiError ? readApiErrorCode(error.body) : undefined;
}

export function referralErrorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof CompassApiError)) return fallback;
  const code = readApiErrorCode(error.body);
  return (code && knownReferralErrors[code]) || readApiErrorMessage(error.body) || fallback;
}

export function uncertainReferralMutation(error: unknown): boolean {
  return !(error instanceof CompassApiError) || error.status >= 500;
}

export function ReferralHeading({
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
          {backLabel ?? "Back to Referrals"}
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

export function ReferralAccessUnavailable({
  title = "Referrals unavailable",
  message = "Your current access does not include the Referral workspace.",
}: {
  title?: string;
  message?: string;
}) {
  return <WorkspaceUnavailable title={title}>{message}</WorkspaceUnavailable>;
}

export function ReferralQueryError({
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
      <p className="text-sm text-danger">{referralErrorMessage(error, fallback)}</p>
      <Button variant="secondary" className="mt-3" onClick={onRetry}>Retry</Button>
    </div>
  );
}

export function ReferralNotice({ children }: { children: ReactNode }) {
  return <p role="status" className="mt-4 text-sm text-muted">{children}</p>;
}
