import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { LoadingRegion } from "@/components/ui/loading-region";
import { Skeleton } from "@/components/ui/skeleton";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";
import { CompassApiError, readApiErrorCode, readApiErrorMessage } from "@/lib/api/errors";
import { ExitInterviewOrdering, type ExitInterviewStatusValue } from "@/lib/api/generated/model";
import type { SortOption } from "@/components/ui/sort-field";

// Submitted Exit Interviews read by their latest submission; drafts and mixed lists by the last
// update, which is what changes while a Student is still working (ADR-090).
export const exitInterviewOrderingOptions: readonly SortOption<ExitInterviewOrdering>[] = [
  { value: ExitInterviewOrdering.RECENTLY_UPDATED, label: "Recently updated first" },
  { value: ExitInterviewOrdering.NEWEST_SUBMITTED, label: "Newest submitted first" },
  { value: ExitInterviewOrdering.OLDEST_SUBMITTED, label: "Oldest submitted first" },
  { value: ExitInterviewOrdering.STUDENT_ASC, label: "Student A–Z" },
  { value: ExitInterviewOrdering.STUDENT_DESC, label: "Student Z–A" },
];
import { PageHeader } from "@/components/ui/page-header";
import { Notice } from "@/components/ui/notice";
import { RowsSkeleton } from "@/components/ui/rows-skeleton";
import { PanelSection } from "@/components/ui/panel";

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
      return "Only current students can start, edit, or submit an Exit Interview.";
    case "current_academic_year_not_configured":
      return "A current Academic Year is not configured. Contact the institutional administrator.";
    case "exit_interview_not_submitted":
      return "This Exit Interview is currently a draft and is not available for Head Guidance review until the Student submits it.";
    case "exit_interview_opportunity_required":
    case "exit_interview_opportunity_not_open":
    case "exit_interview_opportunity_conflict":
      return readApiErrorMessage(error.body) ?? fallback;
    case "exit_interview_conflict":
      return "The Exit Interview changed before this action completed. Refresh the record and review its current status.";
    case "permission_denied":
      return "You cannot complete this Exit Interview action with this account.";
    default:
      return fallback;
  }
}

export function isUncertainExitInterviewMutation(error: unknown): boolean {
  return !(error instanceof CompassApiError) || error.status >= 500;
}

export function ExitInterviewListSkeleton({ label = "Loading Exit Interviews…", framed = true }: { label?: string; framed?: boolean }) {
  return <RowsSkeleton label={label} rows={4} framed={framed} />;
}

export function ExitInterviewDetailSkeleton() {
  return (
    <LoadingRegion label="Loading Exit Interview…" className="space-y-4">
      <Skeleton className="h-8 w-48" />
      <Skeleton className="h-12 w-2/3" />
      <Skeleton className="h-40 w-full" />
      <Skeleton className="h-64 w-full" />
    </LoadingRegion>
  );
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
  return <PageHeader title={title} headingId={id} description={description} actions={action} />;
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
  // One part of the official form; the form or response renders the parts inside one Panel.
  return (
    <PanelSection title={title} titleId={headingId}>
      {children}
    </PanelSection>
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
  message = "This Exit Interview is unavailable to this account.",
}: {
  title?: string;
  message?: string;
}) {
  return <WorkspaceUnavailable title={title}>{message}</WorkspaceUnavailable>;
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
    <Notice
      tone="danger"
      role="alert"
      action={onRetry ? <Button variant="secondary" onClick={onRetry}>Retry</Button> : undefined}
    >
      {exitInterviewErrorMessage(error, fallback)}
    </Notice>
  );
}
