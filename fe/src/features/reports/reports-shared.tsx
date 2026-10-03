"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { LoadingRegion } from "@/components/ui/loading-region";
import { Skeleton } from "@/components/ui/skeleton";
import {
  CompassApiError,
  readApiErrorCode,
} from "@/lib/api/errors";
import type { ReportDisclosureWarning } from "@/lib/api/generated/model";
import { formatInstitutionalDateTime } from "@/lib/institutional-time";
import { Notice } from "@/components/ui/notice";
import { WorkspaceTabs, workspaceTabClass } from "@/components/ui/workspace-tabs";
import { PageHeader } from "@/components/ui/page-header";

const REPORT_ERROR_COPY: Record<string, string> = {
  permission_denied: "This report is unavailable for your assigned reporting area.",
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
  return (code && REPORT_ERROR_COPY[code]) || fallback;
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
    <WorkspaceTabs label="Reports navigation">
      {links.map((link) => (
        <Link
          key={link.key}
          href={link.href}
          aria-current={current === link.key ? "page" : undefined}
          className={workspaceTabClass(current === link.key)}
        >
          {link.label}
        </Link>
      ))}
    </WorkspaceTabs>
  );
}

export function ReportsPageHeading({
  title,
  headingId,
  description,
  actions,
  children,
}: {
  title: string;
  headingId?: string;
  description?: ReactNode;
  actions?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <PageHeader title={title} headingId={headingId} description={description} actions={actions}>
      {children}
    </PageHeader>
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
    <LoadingRegion label={`Loading ${title}…`}>
      <ReportsPageHeading title={title} />
      <div className="space-y-5">
        <div className="rounded-sm border border-brand-line bg-surface-raised px-4 py-4 sm:px-5">
          <Skeleton className="h-4 w-40" />
          <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        </div>
        <div className="rounded-sm border border-brand-line bg-surface-raised px-4 py-4 sm:px-5">
          <Skeleton className="h-28 w-full" />
        </div>
        {children}
      </div>
    </LoadingRegion>
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
    <Notice
      tone="danger"
      role="alert"
      action={<Button variant="secondary" onClick={onRetry}>Retry</Button>}
    >
      {reportErrorMessage(error, fallback)}
    </Notice>
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
    <Notice
      tone="warning"
      role="status"
      action={
        <Button variant="secondary" onClick={onRetry}>
          Retry report
        </Button>
      }
    >
      {children}
    </Notice>
  );
}

export function ReportDisclosureNotice({
  warnings,
}: {
  warnings: ReportDisclosureWarning[];
}) {
  if (warnings.length === 0) return null;
  const messages = [
    ...new Set(warnings.map((warning) => warning.message.trim())),
  ].filter(Boolean);
  if (messages.length === 0) return null;

  return (
    <section aria-labelledby="report-disclosure-warning-heading">
      <Notice
        tone="warning"
        title={
          <h2 id="report-disclosure-warning-heading" className="text-sm font-semibold text-ink">
            Small-population privacy notice
          </h2>
        }
      >
        {messages.map((message) => (
          <p key={message} className="max-w-4xl text-ink">
            {message}
          </p>
        ))}
      </Notice>
    </section>
  );
}

// One aggregate table inside a report group's Panel: a short heading band, then the table flush
// with the panel's sides. Sections after the first are separated by the panel's line.
// A report's parts (context, coverage, each group of tables, the methodology) stack with one gap.
export const reportStack = "mt-5 space-y-5";

// The methodology disclosure: framed like a panel, closed by default.
export const reportDetails = {
  root: "rounded-sm border border-brand-line bg-surface-raised",
  summary:
    "cursor-pointer rounded-sm px-4 py-3 font-semibold text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-focus sm:px-5",
  body: "space-y-4 border-t border-brand-line px-4 py-4 text-sm leading-6 sm:px-5",
} as const;

export const reportSection = {
  root: "border-t border-brand-line first:border-t-0 [[data-panel-header]+&]:border-t-0",
  head: "flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 px-4 pb-3 pt-4 sm:px-5",
  title: "font-heading text-base font-semibold text-ink",
  region:
    "overflow-x-auto focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-focus",
  // Program and category names keep their own capitalization in these heads.
  tableHead: "bg-brand-wash text-xs text-brand-strong",
  empty: "px-4 py-3 text-sm text-muted sm:px-5",
} as const;

export function formatReportPercentage(value: number | null): string {
  if (value === null) return "N/A";
  return Number.isFinite(value) ? value.toFixed(2) + "%" : "Unavailable";
}

export function reportGeneratedAt(value: string): string {
  return formatInstitutionalDateTime(value);
}
