import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { DiagnosticStatus } from "@/lib/api/generated/model";

const diagnosticLabels: Record<DiagnosticStatus, string> = {
  [DiagnosticStatus.HEALTHY]: "Healthy",
  [DiagnosticStatus.DEGRADED]: "Degraded",
  [DiagnosticStatus.UNAVAILABLE]: "Unavailable",
  [DiagnosticStatus.DISABLED]: "Disabled",
  [DiagnosticStatus.NOT_CHECKED]: "Not checked",
};

export function diagnosticStatusLabel(status: DiagnosticStatus): string {
  return diagnosticLabels[status];
}

export function PlatformStatusBadge({
  status,
}: {
  status: DiagnosticStatus | string;
}) {
  const tone =
    status === DiagnosticStatus.HEALTHY
      ? "border-success/30 bg-success/10 text-success"
      : status === DiagnosticStatus.DEGRADED
        ? "border-warning/30 bg-warning/10 text-warning"
        : status === DiagnosticStatus.UNAVAILABLE
        ? "border-danger/30 bg-danger/10 text-danger"
        : status === "FAILED"
          ? "border-danger/30 bg-danger/10 text-danger"
          : status === "SENT"
            ? "border-success/30 bg-success/10 text-success"
            : status === "PENDING" || status === "PROCESSING"
              ? "border-info/30 bg-info/5 text-info"
          : "border-border bg-surface-muted text-muted";

  const label = Object.prototype.hasOwnProperty.call(diagnosticLabels, status)
    ? diagnosticLabels[status as DiagnosticStatus]
    : status
        .replaceAll("_", " ")
        .toLowerCase()
        .replace(/\b\w/g, (letter) => letter.toUpperCase());

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
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <header className="mb-8 flex flex-col gap-4 border-b border-border pb-6 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="font-heading text-3xl font-bold text-ink">{title}</h1>
        {description ? (
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
            {description}
          </p>
        ) : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </header>
  );
}

export function PlatformQueryError({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <div role="alert" className="border-y border-border py-6">
      <p className="text-sm leading-6 text-danger">{message}</p>
      <Button className="mt-3" variant="secondary" onClick={onRetry}>
        Try again
      </Button>
    </div>
  );
}

export function PlatformRowsSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div
      aria-busy="true"
      className="divide-y divide-border border-y border-border"
    >
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className="py-5">
          <Skeleton className="h-4 w-36 rounded-sm" />
          <Skeleton className="mt-3 h-3 w-3/4 rounded-sm" />
        </div>
      ))}
      <p className="sr-only">Loading…</p>
    </div>
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
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return <span>{fallback}</span>;

  return (
    <time dateTime={value}>
      {date.toLocaleString(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
      })}
    </time>
  );
}

export function PlatformPagination({
  page,
  hasNext,
  disabled = false,
  onPageChange,
}: {
  page: number;
  hasNext: boolean;
  disabled?: boolean;
  onPageChange: (page: number) => void;
}) {
  return (
    <nav
      aria-label="Pagination"
      className="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4"
    >
      <p className="text-sm text-muted">Page {page}</p>
      <div className="flex gap-2">
        <Button
          variant="secondary"
          disabled={disabled || page <= 1}
          onClick={() => onPageChange(page - 1)}
        >
          Previous
        </Button>
        <Button
          variant="secondary"
          disabled={disabled || !hasNext}
          onClick={() => onPageChange(page + 1)}
        >
          Next
        </Button>
      </div>
    </nav>
  );
}
