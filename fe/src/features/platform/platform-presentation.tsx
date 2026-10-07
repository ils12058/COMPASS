import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { LoadingRegion } from "@/components/ui/loading-region";
import { Skeleton } from "@/components/ui/skeleton";
import { DiagnosticStatus, EmailDeliveryStatusValue } from "@/lib/api/generated/model";
import { formatInstitutionalDateTime } from "@/lib/institutional-time";
import { PageHeader } from "@/components/ui/page-header";
import { Notice } from "@/components/ui/notice";
import { cn } from "@/lib/utils/cn";

const diagnosticLabels: Record<DiagnosticStatus, string> = {
  [DiagnosticStatus.HEALTHY]: "Healthy",
  [DiagnosticStatus.DEGRADED]: "Degraded",
  [DiagnosticStatus.UNAVAILABLE]: "Unavailable",
  [DiagnosticStatus.DISABLED]: "Disabled",
  [DiagnosticStatus.NOT_CHECKED]: "Not checked",
};

export const emailDeliveryStatusLabels: Record<EmailDeliveryStatusValue, string> = {
  [EmailDeliveryStatusValue.PENDING]: "Pending",
  [EmailDeliveryStatusValue.PROCESSING]: "Processing",
  [EmailDeliveryStatusValue.SENT]: "Sent",
  [EmailDeliveryStatusValue.FAILED]: "Failed",
  [EmailDeliveryStatusValue.CANCELLED]: "Cancelled",
};

export function diagnosticStatusLabel(status: DiagnosticStatus): string {
  return diagnosticLabels[status];
}

type BadgeTone = "success" | "warning" | "danger" | "info" | "neutral";

const toneClasses: Record<BadgeTone, string> = {
  success: "border-success/30 bg-success/10 text-success",
  warning: "border-warning/30 bg-warning/10 text-warning",
  danger: "border-danger/30 bg-danger/10 text-danger",
  info: "border-info/30 bg-info/5 text-info",
  neutral: "border-border bg-surface-muted text-muted",
};

const statusTones: Partial<Record<DiagnosticStatus | EmailDeliveryStatusValue, BadgeTone>> = {
  [DiagnosticStatus.HEALTHY]: "success",
  [DiagnosticStatus.DEGRADED]: "warning",
  [DiagnosticStatus.UNAVAILABLE]: "danger",
  [EmailDeliveryStatusValue.FAILED]: "danger",
  [EmailDeliveryStatusValue.SENT]: "success",
  [EmailDeliveryStatusValue.PENDING]: "info",
  [EmailDeliveryStatusValue.PROCESSING]: "info",
};

function isDiagnosticStatus(
  status: DiagnosticStatus | EmailDeliveryStatusValue,
): status is DiagnosticStatus {
  return Object.prototype.hasOwnProperty.call(diagnosticLabels, status);
}

export function PlatformStatusBadge({
  status,
}: {
  status: DiagnosticStatus | EmailDeliveryStatusValue;
}) {
  const tone = toneClasses[statusTones[status] ?? "neutral"];
  const label = isDiagnosticStatus(status)
    ? diagnosticLabels[status]
    : emailDeliveryStatusLabels[status];

  return (
    <span
      className={`inline-flex min-h-7 items-center rounded-md border px-2.5 text-xs font-semibold ${tone}`}
    >
      {label}
    </span>
  );
}

export function PlatformPageHeader({
  title,
  headingId = "platform-page-heading",
  description,
  action,
  help,
}: {
  title: string;
  headingId?: string;
  description?: string;
  action?: ReactNode;
  help?: ReactNode;
}) {
  return <PageHeader title={title} headingId={headingId} description={description} actions={action} help={help} />;
}

export function PlatformQueryError({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <Notice
      tone="danger"
      role="alert"
      action={<Button variant="secondary" onClick={onRetry}>Try again</Button>}
    >
      {message}
    </Notice>
  );
}

// Inside a results Panel the panel draws the frame; on the canvas the skeleton frames itself.
export function PlatformRowsSkeleton({
  label,
  rows = 4,
  framed = true,
}: {
  label: string;
  rows?: number;
  framed?: boolean;
}) {
  return (
    <LoadingRegion
      label={label}
      className={cn(
        "divide-y divide-border",
        framed && "rounded-sm border border-brand-line bg-surface-raised",
      )}
    >
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className="px-4 py-4 sm:px-5">
          <Skeleton className="h-4 w-36 rounded-sm" />
          <Skeleton className="mt-3 h-3 w-3/4 rounded-sm" />
        </div>
      ))}
    </LoadingRegion>
  );
}

export function PlatformTimestamp({
  value,
  fallback = "Not available",
}: {
  value: string | null | undefined;
  fallback?: string;
}) {
  if (!value) return <span>{fallback}</span>;
  const formatted = formatInstitutionalDateTime(value);
  if (formatted === value) return <span>{fallback}</span>;

  return <time dateTime={value}>{formatted}</time>;
}
