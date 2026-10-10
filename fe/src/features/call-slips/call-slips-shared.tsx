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
  CallSlipOrdering,
} from "@/lib/api/generated/model";
import { PageHeader, pageBackLinkClass } from "@/components/ui/page-header";
import { Notice } from "@/components/ui/notice";
import { RowsSkeleton } from "@/components/ui/rows-skeleton";
import type { SortOption } from "@/components/ui/sort-field";

const knownCallSlipErrors: Record<string, string> = {
  permission_denied: "You don't have access to call slips.",
  call_slip_not_found: "Call Slip not found.",
  call_slip_not_permitted: "This call slip is unavailable.",
  call_slip_document_unavailable: "The document could not be released right now. Try again later.",
  release_audit_unavailable: "The document could not be released right now. Try again later.",
  invalid_call_slip_request: "Some call slip details need attention. Review them and try again.",
  call_slip_conflict: "This call slip changed or conflicts with its current details. Review the latest details before trying again.",
  idempotency_key_conflict: "This issuance attempt no longer matches its original details. Review the form and submit again.",
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
  help,
  backHref,
  backLabel,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
  help?: ReactNode;
  backHref?: string;
  backLabel?: string;
}) {
  return (
    <PageHeader
      title={title}
      description={description}
      actions={action} help={help}
      back={backHref ? (
        <Link href={backHref} className={pageBackLinkClass}>
          {backLabel ?? "Back to Call Slips"}
        </Link>
      ) : undefined}
    />
  );
}

export function CallSlipListSkeleton({ label = "Loading call slips…", framed = true }: { label?: string; framed?: boolean }) {
  return <RowsSkeleton label={label} framed={framed} />;
}

export function CallSlipDetailSkeleton({ label = "Loading call slip…" }: { label?: string }) {
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
      <p role="status" className="text-sm text-muted">Checking the referral and linked call slip…</p>
    </div>
  );
}

export function CallSlipAccessUnavailable({
  title = "Call Slips unavailable",
  message = "You don't have access to call slips.",
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

// A Call Slip's report time is when the Student is expected to report. Active Call Slips default
// to the nearest report time; completed, voided, and mixed lists to the latest (ADR-090).
export const callSlipOrderingOptions: readonly SortOption<CallSlipOrdering>[] = [
  { value: CallSlipOrdering.EARLIEST_REPORT, label: "Earliest report time first" },
  { value: CallSlipOrdering.LATEST_REPORT, label: "Latest report time first" },
  { value: CallSlipOrdering.STUDENT_ASC, label: "Student A–Z" },
  { value: CallSlipOrdering.STUDENT_DESC, label: "Student Z–A" },
];

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
