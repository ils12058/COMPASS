import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { LoadingRegion } from "@/components/ui/loading-region";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelHeader } from "@/components/ui/panel";
import { Skeleton } from "@/components/ui/skeleton";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";
import { CompassApiError, readApiErrorCode, readApiErrorMessage } from "@/lib/api/errors";
import { formatDateOnly, formatInstitutionalDateTime } from "@/lib/institutional-time";
import { GoodMoralOrdering, GoodMoralStatusValue, type GoodMoralVariantValue } from "@/lib/api/generated/model";
import type { SortOption } from "@/components/ui/sort-field";
import { Notice } from "@/components/ui/notice";
import { RowsSkeleton } from "@/components/ui/rows-skeleton";

// Chronology is when a request reached its current status. Requests awaiting preparation or
// issuance default to the one waiting longest; issued and cancelled ones to the newest (ADR-090).
export function goodMoralOrderingOptions(
  status: GoodMoralStatusValue | "",
): readonly SortOption<GoodMoralOrdering>[] {
  const queue =
    status === GoodMoralStatusValue.REQUESTED || status === GoodMoralStatusValue.READY_FOR_ISSUANCE;
  return [
    { value: GoodMoralOrdering.OLDEST_FIRST, label: queue ? "Waiting longest first" : "Oldest first" },
    { value: GoodMoralOrdering.NEWEST_FIRST, label: "Newest first" },
    { value: GoodMoralOrdering.APPLICANT_ASC, label: "Applicant A–Z" },
    { value: GoodMoralOrdering.APPLICANT_DESC, label: "Applicant Z–A" },
  ];
}

export function goodMoralVariantLabel(variant: GoodMoralVariantValue): string {
  return variant === "CURRENT_STUDENT" ? "Current Student" : "Graduate";
}

export function goodMoralStatusLabel(status: GoodMoralStatusValue): string {
  switch (status) {
    case "REQUESTED":
      return "Requested";
    case "READY_FOR_ISSUANCE":
      return "Ready for issuance";
    case "ISSUED":
      return "Issued";
    case "CANCELLED":
      return "Cancelled";
  }
}

export function GoodMoralStatus({ status }: { status: GoodMoralStatusValue }) {
  const style =
    status === "ISSUED"
      ? "border-success/30 bg-success/10 text-success"
      : status === "CANCELLED"
        ? "border-border bg-surface-muted text-muted"
        : "border-warning/30 bg-warning/10 text-warning";
  return (
    <span className={`inline-flex min-h-7 items-center rounded-full border px-2.5 text-xs font-semibold ${style}`}>
      {goodMoralStatusLabel(status)}
    </span>
  );
}

export function formatGoodMoralDate(value: string | null | undefined): string {
  return formatDateOnly(value);
}

export function formatGoodMoralDateTime(value: string | null | undefined): string {
  return formatInstitutionalDateTime(value);
}

export function goodMoralErrorCode(error: unknown): string | undefined {
  return error instanceof CompassApiError ? readApiErrorCode(error.body) : undefined;
}

export function goodMoralErrorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof CompassApiError)) return fallback;
  const code = readApiErrorCode(error.body);
  switch (code) {
    case "good_moral_not_ready":
      return "Review the certificate details and mark the request ready before issuing.";
    case "good_moral_preparation_changed":
      return "This request changed. Review its latest details before continuing.";
    case "good_moral_certificate_date_in_future":
      // Names which date is wrong; COMPASS writes this message for staff.
      return readApiErrorMessage(error.body) ?? "A certificate date is in the future. Correct the certificate details before issuance.";
    case "good_moral_not_found":
      return "Good Moral request not found.";
    case "good_moral_inventory_required":
      return "Submit your Individual Inventory for the current academic year before requesting a certificate.";
    case "good_moral_exit_interview_required":
      return "Complete and submit your Exit Interview before requesting your graduation Good Moral certificate.";
    case "good_moral_affiliation_required":
      return "A current college affiliation is required to request this certificate.";
    case "current_student_required":
      return "This request is available only to current students.";
    case "graduated_student_required":
      return "This request is available only to graduates.";
    case "good_moral_configuration_conflict":
      return "This certificate cannot be issued because its approved document configuration is not currently available.";
    case "good_moral_document_unavailable":
    case "release_audit_unavailable":
      return "The certificate could not be released right now. Try again later.";
    case "idempotency_key_conflict":
      return "This request attempt no longer matches its original details.";
    case "permission_denied":
      return "You cannot complete this Good Moral action with this account.";
    default:
      return fallback;
  }
}

export function uncertainGoodMoralMutation(error: unknown): boolean {
  return !(error instanceof CompassApiError) || error.status >= 500;
}

// Rows shaped like the queue table. Inside the results panel the panel draws the frame; the route
// fallback has no panel yet, so it draws its own.
// Inside the results panel the panel draws the frame; the route fallback has no panel yet.
export function GoodMoralListSkeleton({
  label = "Loading Good Moral requests…",
  framed = true,
}: {
  label?: string;
  framed?: boolean;
}) {
  return <RowsSkeleton label={label} rows={4} framed={framed} />;
}

export function GoodMoralDetailSkeleton() {
  return (
    <LoadingRegion label="Loading Good Moral request…" className="space-y-5">
      <Skeleton className="h-9 w-72 max-w-full" />
      <div className="rounded-sm border border-brand-line bg-surface-raised px-4 py-4 sm:px-5">
        <Skeleton className="h-6 w-64 max-w-full" />
        <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[0, 1, 2, 3].map((fact) => (
            <Skeleton key={fact} className="h-9 w-full" />
          ))}
        </div>
      </div>
      <Skeleton className="h-40 w-full rounded-sm" />
    </LoadingRegion>
  );
}

export function GoodMoralHeading({
  title,
  description,
  action,
  headingId,
  back,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
  headingId?: string;
  back?: ReactNode;
}) {
  return (
    <PageHeader
      title={title}
      headingId={headingId}
      description={description}
      back={back}
      actions={action}
    />
  );
}

export function GoodMoralUnavailable({
  title = "Good Moral unavailable",
  message = "Good Moral is unavailable to this account.",
}: {
  title?: string;
  message?: string;
}) {
  return <WorkspaceUnavailable title={title}>{message}</WorkspaceUnavailable>;
}

export function GoodMoralError({
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
      {goodMoralErrorMessage(error, fallback)}
    </Notice>
  );
}

export function GoodMoralNotice({
  children,
  tone = "muted",
}: {
  children: ReactNode;
  tone?: "muted" | "danger";
}) {
  return (
    <p role={tone === "danger" ? "alert" : "status"} className={`text-sm leading-6 ${tone === "danger" ? "text-danger" : "text-muted"}`}>
      {children}
    </p>
  );
}

// One Good Moral region on its own working surface. Older section content opened with a top margin
// under the heading; the panel body pads instead, so a leading margin is dropped.
export function GoodMoralSection({
  title,
  children,
  labelledBy,
  description,
  actions,
}: {
  title: string;
  children: ReactNode;
  labelledBy?: string;
  description?: ReactNode;
  actions?: ReactNode;
}) {
  const headingId = labelledBy ?? title.toLowerCase().replace(/[^a-z0-9]+/g, "-");
  return (
    <Panel aria-labelledby={headingId}>
      <PanelHeader title={title} titleId={headingId} description={description} actions={actions} />
      <div className="px-4 py-4 *:first:mt-0 sm:px-5">{children}</div>
    </Panel>
  );
}

export function GoodMoralField({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs font-semibold text-muted">{label}</dt>
      <dd className="mt-1 whitespace-pre-wrap break-words text-sm text-ink">{value?.trim() || "Not provided"}</dd>
    </div>
  );
}

export function formatGoodMoralAmount(value: string | null | undefined): string {
  return value === null || value === undefined || value === "" ? "Not recorded" : value;
}
