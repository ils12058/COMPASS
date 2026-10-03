"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { LoadingRegion } from "@/components/ui/loading-region";
import { Skeleton } from "@/components/ui/skeleton";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";
import { CompassApiError, readApiErrorCode } from "@/lib/api/errors";
import {
  CallSlipDestinationTypeValue,
  CallSlipIssuanceModeValue,
  CallSlipLifecycleStateValue,
} from "@/lib/api/generated/model";
import { PageHeader, pageBackLinkClass } from "@/components/ui/page-header";
import { Notice } from "@/components/ui/notice";
import { RowsSkeleton } from "@/components/ui/rows-skeleton";

const knownCallSlipErrors: Record<string, string> = {
  permission_denied: "You do not have permission to use this Call Slip workspace.",
  call_slip_not_found: "Call Slip not found.",
  call_slip_not_permitted: "This Call Slip is unavailable to this account.",
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
  return (code && knownCallSlipErrors[code]) || fallback;
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
    <PageHeader
      title={title}
      description={description}
      actions={action}
      back={backHref ? (
        <Link href={backHref} className={pageBackLinkClass}>
          {backLabel ?? "Back to Call Slips"}
        </Link>
      ) : undefined}
    />
  );
}

export function CallSlipListSkeleton({ label = "Loading Call Slips…", framed = true }: { label?: string; framed?: boolean }) {
  return <RowsSkeleton label={label} framed={framed} />;
}

export function CallSlipDetailSkeleton({ label = "Loading Call Slip…" }: { label?: string }) {
  return (
    <LoadingRegion label={label} className="space-y-4">
      <Skeleton className="h-16 w-full" />
      <Skeleton className="h-48 w-full" />
      <Skeleton className="h-32 w-full" />
    </LoadingRegion>
  );
}

// Linked issuance first confirms the Referral and any current linked Call Slip.
export function LinkedCallSlipCheckLoading() {
  return (
    <div className="space-y-4" aria-busy="true">
      <p role="status" className="text-sm text-muted">Checking Referral and linked Call Slip state…</p>
    </div>
  );
}

export function CallSlipAccessUnavailable({
  title = "Call Slips unavailable",
  message = "Call Slips are unavailable to this account.",
}: {
  title?: string;
  message?: string;
}) {
  return <WorkspaceUnavailable title={title}>{message}</WorkspaceUnavailable>;
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
    <Notice
      tone="danger"
      role="alert"
      action={<Button variant="secondary" onClick={onRetry}>Retry</Button>}
    >
      {callSlipErrorMessage(error, fallback)}
    </Notice>
  );
}

export function CallSlipNotice({ children }: { children: ReactNode }) {
  return <p role="status" className="mt-4 text-sm text-muted">{children}</p>;
}

export function callSlipStateLabel(
  state: CallSlipLifecycleStateValue,
  studentFacing = false,
): string {
  if (state === CallSlipLifecycleStateValue.ACTIVE) return "Active";
  if (state === CallSlipLifecycleStateValue.COMPLETED) return "Completed";
  return studentFacing ? "Withdrawn" : "Voided";
}

export function callSlipDestinationLabel(
  destinationType: CallSlipDestinationTypeValue,
  otherDestination: string,
): string {
  return destinationType === CallSlipDestinationTypeValue.GUIDANCE_OFFICE
    ? "Guidance Office"
    : otherDestination;
}

export const callSlipIssuanceModeLabels: Record<CallSlipIssuanceModeValue, string> = {
  [CallSlipIssuanceModeValue.LIVE]: "Live issuance",
  [CallSlipIssuanceModeValue.HISTORICAL]: "Historical / back-entry",
  [CallSlipIssuanceModeValue.LEGACY_UNKNOWN]: "Not recorded (created before COMPASS tracked issuance mode)",
};
