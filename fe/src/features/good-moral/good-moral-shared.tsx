import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";
import { CompassApiError, readApiErrorCode, readApiErrorMessage } from "@/lib/api/errors";
import type { GoodMoralStatusValue, GoodMoralVariantValue } from "@/lib/api/generated/model";

export function goodMoralVariantLabel(variant: GoodMoralVariantValue): string {
  return variant === "CURRENT_STUDENT" ? "Current Student" : "Graduate";
}

export function goodMoralStatusLabel(status: GoodMoralStatusValue): string {
  switch (status) {
    case "REQUESTED":
      return "Requested";
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
  if (!value) return "Not recorded";
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (match) {
    const [, year, month, day] = match;
    return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(
      new Date(Number(year), Number(month) - 1, Number(day)),
    );
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(date);
}

export function formatGoodMoralDateTime(value: string | null | undefined): string {
  if (!value) return "Not recorded";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}

export function goodMoralErrorCode(error: unknown): string | undefined {
  return error instanceof CompassApiError ? readApiErrorCode(error.body) : undefined;
}

export function goodMoralErrorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof CompassApiError)) return fallback;
  const code = readApiErrorCode(error.body);
  switch (code) {
    case "good_moral_not_found":
      return "Good Moral request not found.";
    case "good_moral_inventory_required":
      return "A submitted Individual Inventory for the current Academic Year is required before requesting this certificate.";
    case "good_moral_affiliation_required":
      return "A current active College affiliation is required for this certificate.";
    case "current_student_required":
      return "Current Student lifecycle is required for this certificate request.";
    case "graduated_student_required":
      return "Graduated Student lifecycle is required for this certificate request.";
    case "good_moral_configuration_conflict":
      return "This certificate cannot be issued because its approved document configuration is not currently available.";
    case "good_moral_document_unavailable":
    case "release_audit_unavailable":
      return "The certificate could not be released right now. Try again later.";
    case "recent_mfa_required":
      return "Recent authenticator verification is required before issuing this certificate.";
    case "permission_denied":
      return "Your current access does not allow this Good Moral action.";
    default:
      return readApiErrorMessage(error.body) ?? fallback;
  }
}

export function uncertainGoodMoralMutation(error: unknown): boolean {
  return !(error instanceof CompassApiError) || error.status >= 500;
}

export function GoodMoralHeading({
  title,
  description,
  action,
  headingId,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
  headingId?: string;
}) {
  return (
    <header className="border-b border-border pb-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 id={headingId} className="font-heading text-3xl font-bold text-ink">{title}</h1>
          {description ? <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">{description}</p> : null}
        </div>
        {action}
      </div>
    </header>
  );
}

export function GoodMoralUnavailable({
  title = "Good Moral unavailable",
  message = "Your current access does not include the Good Moral workspace.",
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
    <div role="alert" className="border-y border-danger/30 py-5">
      <p className="text-sm text-danger">{goodMoralErrorMessage(error, fallback)}</p>
      <Button variant="secondary" className="mt-3" onClick={onRetry}>Retry</Button>
    </div>
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

export function GoodMoralSection({
  title,
  children,
  labelledBy,
}: {
  title: string;
  children: ReactNode;
  labelledBy?: string;
}) {
  const headingId = labelledBy ?? title.toLowerCase().replace(/[^a-z0-9]+/g, "-");
  return (
    <section aria-labelledby={headingId} className="border-t border-border py-6">
      <h2 id={headingId} className="font-heading text-xl font-semibold text-ink">{title}</h2>
      {children}
    </section>
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
