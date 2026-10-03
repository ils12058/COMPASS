import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { CompassApiError, readApiErrorCode } from "@/lib/api/errors";
import { formatDateOnly, formatInstitutionalDateTime } from "@/lib/institutional-time";
import { PageHeader } from "@/components/ui/page-header";
import { Notice } from "@/components/ui/notice";

export function InventoryHeading({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return <PageHeader title={title} description={description} actions={action} className="mb-0" />;
}

export function InventorySectionHeading({
  title,
  children,
}: {
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="border-b border-border pb-4">
      <h2 className="font-heading text-xl font-semibold text-ink">{title}</h2>
      {children ? (
        <p className="mt-2 text-sm leading-6 text-muted">{children}</p>
      ) : null}
    </div>
  );
}

export function InventoryNotice({
  title,
  children,
  tone = "neutral",
  role = "status",
}: {
  title?: string;
  children: ReactNode;
  tone?: "neutral" | "warning" | "danger" | "success";
  role?: "status" | "alert";
}) {
  return (
    <Notice tone={tone} role={role} title={title}>
      {children}
    </Notice>
  );
}

export function InventoryStatus({
  status,
  correctionPending = false,
  missingLabel = "Missing",
}: {
  status: "MISSING" | "DRAFT" | "SUBMITTED";
  correctionPending?: boolean;
  missingLabel?: string;
}) {
  const label =
    status === "MISSING"
      ? missingLabel
      : status === "DRAFT"
        ? correctionPending
          ? "Draft · Correction pending"
          : "Draft"
        : "Submitted";
  const tone =
    status === "SUBMITTED"
      ? "border-success/40 bg-success/5 text-success"
      : status === "DRAFT"
        ? "border-warning/40 bg-warning/5 text-warning"
        : "border-border bg-surface-muted text-muted";

  return (
    <span className={`inline-flex min-h-7 items-center rounded-md border px-2.5 text-xs font-semibold ${tone}`}>
      {label}
    </span>
  );
}

export function InventoryQueryError({
  error,
  fallback,
  onRetry,
}: {
  error: unknown;
  fallback: string;
  onRetry?: () => void;
}) {
  return (
    <InventoryNotice tone="danger" role="alert">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p>{inventoryErrorMessage(error, fallback)}</p>
        {onRetry ? (
          <Button variant="secondary" onClick={onRetry}>
            Try again
          </Button>
        ) : null}
      </div>
    </InventoryNotice>
  );
}

export function inventoryErrorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof CompassApiError)) return fallback;

  const code = readApiErrorCode(error.body);

  switch (code) {
    case "current_academic_year_not_configured":
      return "The current Academic Year has not been configured yet. Your Individual Inventory cannot be started or submitted until the Guidance and Counseling Office completes this setup.";
    case "inventory_form_revision_not_configured":
      return "The official Individual Inventory Form Revision has not been configured for this COMPASS version. Please contact the Guidance and Counseling Office.";
    case "current_student_required":
      return "Only current students can start, edit, or submit this year’s Individual Inventory. Your saved history remains available.";
    case "inventory_conflict":
      return "The Individual Inventory changed while you were working. Refresh it before continuing.";
    case "inventory_invalid":
      return "Some required Individual Inventory details need attention. Review the form and try submitting again.";
    case "psgc_reference_unavailable":
      return "Your Inventory is still saved as a draft. Official location verification is temporarily unavailable. Please try submitting again later.";
    case "inventory_not_submitted":
      return "This Individual Inventory is currently a draft and is not available for Counselor review.";
    case "inventory_document_unavailable":
      return "This official Individual Inventory PDF is temporarily unavailable. Please try again later.";
    case "release_audit_unavailable":
      return "The PDF cannot be released while its required privacy audit is unavailable. Please try again later.";
    case "inventory_not_found":
      return "This Individual Inventory could not be found or is not available to you.";
    case "permission_denied":
      return "You cannot view or change this Individual Inventory.";
    default:
      return fallback;
  }
}

export function formatInventoryDate(value: string | null | undefined): string {
  if (!value) return "Not submitted";
  const formatted = formatInstitutionalDateTime(value);
  return formatted === value ? "Date unavailable" : formatted;
}

export function formatInventoryDateOnly(value: string | null | undefined): string {
  if (!value) return "Not provided";
  return formatDateOnly(value.slice(0, 10), { dateStyle: "long" });
}

export function FieldGroup({
  legend,
  children,
  className = "",
}: {
  legend: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <fieldset className={`min-w-0 border-t border-border pt-5 ${className}`}>
      <legend className="mb-3 px-0 font-semibold text-ink">{legend}</legend>
      {children}
    </fieldset>
  );
}

export function DefinitionValue({
  label,
  value,
}: {
  label: string;
  value: ReactNode;
}) {
  return (
    <div className="min-w-0 border-b border-border/70 py-3">
      <dt className="text-xs font-semibold text-muted">{label}</dt>
      <dd className="mt-1 whitespace-pre-wrap break-words text-sm leading-6 text-ink">
        {value || <span className="text-muted">Not provided</span>}
      </dd>
    </div>
  );
}
