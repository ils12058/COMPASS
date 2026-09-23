import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { CompassApiError, readApiErrorCode, readApiErrorMessage } from "@/lib/api/errors";

export const inventoryInputClass =
  "min-h-10 w-full rounded-md border border-border bg-surface-raised px-3 py-2 text-sm text-ink outline-none placeholder:text-muted focus:border-focus focus:ring-2 focus:ring-focus/25 disabled:cursor-not-allowed disabled:bg-surface-muted disabled:opacity-70";

export const inventorySelectClass = inventoryInputClass;

export function InventoryHeading({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <header className="flex flex-col gap-4 border-b border-border pb-6 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="font-heading text-3xl font-semibold text-ink">{title}</h1>
        {description ? (
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
            {description}
          </p>
        ) : null}
      </div>
      {action}
    </header>
  );
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
  const toneClass = {
    neutral: "border-border bg-surface-muted text-ink",
    warning: "border-warning/40 bg-warning/5 text-ink",
    danger: "border-danger/40 bg-danger/5 text-ink",
    success: "border-success/40 bg-success/5 text-ink",
  }[tone];

  return (
    <div role={role} className={`border-l-4 px-4 py-3 text-sm leading-6 ${toneClass}`}>
      {title ? <p className="font-semibold">{title}</p> : null}
      <div className={title ? "mt-1" : undefined}>{children}</div>
    </div>
  );
}

export function InventoryStatus({
  status,
  correctionPending = false,
}: {
  status: "MISSING" | "DRAFT" | "SUBMITTED";
  correctionPending?: boolean;
}) {
  const label =
    status === "MISSING"
      ? "Missing"
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
  const message = readApiErrorMessage(error.body);

  switch (code) {
    case "current_academic_year_not_configured":
      return "The current Academic Year has not been configured yet. Your Individual Inventory cannot be started or submitted until the Guidance and Counseling Office completes this setup.";
    case "inventory_form_revision_not_configured":
      return "The official Individual Inventory Form Revision has not been configured for this COMPASS version. Please contact the Guidance and Counseling Office.";
    case "current_student_required":
      return "Only a Student with a current lifecycle can start, edit, or submit this year's Individual Inventory. Your saved annual history remains available.";
    case "inventory_conflict":
      return message ?? "The Inventory changed while you were working. Refresh its status before continuing.";
    case "inventory_invalid":
      return message ?? "Some required Inventory details need attention. Review the form and try submitting again.";
    case "psgc_reference_unavailable":
      return "Your Inventory is still saved as a draft. Official location verification is temporarily unavailable. Please try submitting again later.";
    case "inventory_not_submitted":
      return "This Individual Inventory is currently a draft and is not available for Counselor review.";
    case "inventory_not_found":
      return "This Individual Inventory could not be found or is not available to you.";
    case "permission_denied":
      return "You do not have access to this Individual Inventory operation.";
    default:
      return message ?? fallback;
  }
}

export function formatInventoryDate(value: string | null | undefined): string {
  if (!value) return "Not submitted";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Date unavailable";
  return new Intl.DateTimeFormat("en-PH", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function formatInventoryDateOnly(value: string | null | undefined): string {
  if (!value) return "Not provided";
  const date = new Date(`${value.slice(0, 10)}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en-PH", { dateStyle: "long" }).format(date);
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
