"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  CompassApiError,
  readApiErrorCode,
  readApiErrorMessage,
} from "@/lib/api/errors";
import { formatDateTime } from "@/lib/date-time";

const REPORT_ERROR_COPY: Record<string, string> = {
  permission_denied: "This report request is outside your current Reports scope.",
  report_filter_not_found:
    "A selected report filter could not be found. Review the filters and try again.",
  report_configuration_conflict:
    "The report cannot be generated because Academic Year configuration is unavailable or conflicting.",
  invalid_report_filter: "One or more report filters are invalid.",
  report_document_unavailable: "The Student Profiling PDF is temporarily unavailable.",
  report_workbook_unavailable: "The report XLSX is temporarily unavailable.",
  release_audit_unavailable:
    "The report could not be released because its required privacy audit is unavailable.",
};

export function reportErrorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof CompassApiError)) return fallback;
  const code = readApiErrorCode(error.body);
  const backendMessage = readApiErrorMessage(error.body);
  return backendMessage || (code && REPORT_ERROR_COPY[code]) || fallback;
}

export function isReportScopeDenied(error: unknown): boolean {
  return (
    error instanceof CompassApiError &&
    error.status === 403 &&
    readApiErrorCode(error.body) === "permission_denied"
  );
}

export function ReportNavigation({
  current,
  showGraduateTracer,
}: {
  current: "index" | "student-profile" | "graduate-tracer";
  showGraduateTracer: boolean;
}) {
  const links = [
    { href: "/portal/reports", label: "All Reports", key: "index" },
    {
      href: "/portal/reports/student-profile",
      label: "Student Profiling",
      key: "student-profile",
    },
    ...(showGraduateTracer
      ? [
          {
            href: "/portal/reports/graduate-tracer",
            label: "Graduate Tracer",
            key: "graduate-tracer",
          },
        ]
      : []),
  ] as const;

  return (
    <nav
      aria-label="Reports"
      className="mb-7 flex flex-wrap gap-x-6 gap-y-2 border-b border-border pb-3 text-sm"
    >
      {links.map((link) => (
        <Link
          key={link.key}
          href={link.href}
          aria-current={current === link.key ? "page" : undefined}
          className={
            "font-semibold underline-offset-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus " +
            (current === link.key
              ? "text-ink"
              : "text-brand hover:underline")
          }
        >
          {link.label}
        </Link>
      ))}
    </nav>
  );
}

export function ReportsLoading({
  title,
  children,
}: {
  title: string;
  children?: ReactNode;
}) {
  return (
    <section aria-busy="true" aria-label={"Loading " + title}>
      <h1 className="font-heading text-3xl font-bold text-ink sm:text-4xl">
        {title}
      </h1>
      <div className="mt-7 space-y-4">
        <Skeleton className="h-12 w-full" />
        <Skeleton className="h-32 w-full" />
        {children}
      </div>
      <p className="sr-only">Loading {title}…</p>
    </section>
  );
}

export function ReportQueryError({
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
      <p className="text-sm leading-6 text-danger">
        {reportErrorMessage(error, fallback)}
      </p>
      <Button className="mt-3" variant="secondary" onClick={onRetry}>
        Retry
      </Button>
    </div>
  );
}

export function ReportStaleNotice({
  children,
  onRetry,
}: {
  children: ReactNode;
  onRetry: () => void;
}) {
  return (
    <div
      role="status"
      className="flex flex-wrap items-center justify-between gap-3 border-l-2 border-warning px-3 py-2 text-sm text-muted"
    >
      <p>{children}</p>
      <Button
        className="min-h-8 px-2 text-xs"
        variant="quiet"
        onClick={onRetry}
      >
        Retry report
      </Button>
    </div>
  );
}

export function formatReportPercentage(value: number): string {
  return Number.isFinite(value) ? value.toFixed(2) + "%" : "Unavailable";
}

export function reportGeneratedAt(value: string): string {
  return formatDateTime(value);
}
