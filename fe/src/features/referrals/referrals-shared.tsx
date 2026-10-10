"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { LoadingRegion } from "@/components/ui/loading-region";
import { PageHeader, pageBackLinkClass } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";
import { CompassApiError, readApiErrorCode } from "@/lib/api/errors";
import { Notice } from "@/components/ui/notice";
import { RowsSkeleton } from "@/components/ui/rows-skeleton";
import type { SortOption } from "@/components/ui/sort-field";
import { ReferralOrdering } from "@/lib/api/generated/model";

const knownReferralErrors: Record<string, string> = {
  permission_denied: "You don't have access to referrals.",
  referral_not_found: "Referral not found.",
  referral_not_permitted: "This referral is unavailable.",
  referral_document_unavailable: "The document could not be released right now. Try again later.",
  release_audit_unavailable: "The document could not be released right now. Try again later.",
  invalid_referral_request: "Some referral details need attention. Review them and try again.",
  referral_conflict: "This referral changed or conflicts with another recorded action. Review the latest details before trying again.",
  referral_active_call_slip_conflict: "This Referral cannot be voided while its linked Call Slip is active. Void the Call Slip first.",
  referral_completed_call_slip_conflict: "This Referral cannot be voided because its linked Call Slip records a completed interview.",
  idempotency_key_conflict: "This creation attempt no longer matches its original details. Review the form and submit again.",
};

// The date on the Referral is the canonical chronology; the newest referred comes first (ADR-090).
export const referralOrderingOptions: readonly SortOption<ReferralOrdering>[] = [
  { value: ReferralOrdering.NEWEST_REFERRED, label: "Newest referred first" },
  { value: ReferralOrdering.OLDEST_REFERRED, label: "Oldest referred first" },
  { value: ReferralOrdering.STUDENT_ASC, label: "Student A–Z" },
  { value: ReferralOrdering.STUDENT_DESC, label: "Student Z–A" },
];

export function referralErrorCode(error: unknown): string | undefined {
  return error instanceof CompassApiError ? readApiErrorCode(error.body) : undefined;
}

export function referralErrorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof CompassApiError)) return fallback;
  const code = readApiErrorCode(error.body);
  return (code && knownReferralErrors[code]) || fallback;
}

export function uncertainReferralMutation(error: unknown): boolean {
  return !(error instanceof CompassApiError) || error.status >= 500;
}

export function ReferralHeading({
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
          {backLabel ?? "Back to Referrals"}
        </Link>
      ) : undefined}
    />
  );
}

export function ReferralListSkeleton({ framed = true }: { framed?: boolean }) {
  return <RowsSkeleton label="Loading referrals…" framed={framed} />;
}

export function ReferralDetailSkeleton() {
  return (
    <LoadingRegion label="Loading referral…" className="space-y-4">
      <Skeleton className="h-16 w-full" />
      <Skeleton className="h-40 w-full" />
      <Skeleton className="h-64 w-full" />
    </LoadingRegion>
  );
}

export function ReferralAccessUnavailable({
  title = "Referrals unavailable",
  message = "You don't have access to referrals.",
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
    <Notice
      tone="danger"
      role="alert"
      action={<Button variant="secondary" onClick={onRetry}>Retry</Button>}
    >
      {referralErrorMessage(error, fallback)}
    </Notice>
  );
}

export function ReferralNotice({ children }: { children: ReactNode }) {
  return <p role="status" className="mt-4 text-sm text-muted">{children}</p>;
}
