"use client";

import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { RowsSkeleton } from "@/components/ui/rows-skeleton";
import { organizationErrorMessage } from "@/features/organization/components/organization-action";
import { PageHeader } from "@/components/ui/page-header";
import { Notice } from "@/components/ui/notice";
import { PanelMessage } from "@/components/ui/panel";

export { ActiveStatusBadge as StatusBadge } from "@/components/ui/active-status-badge";

export function PageHeading({
  title,
  headingId,
  description,
  action,
  help,
}: {
  title: string;
  headingId?: string;
  description?: ReactNode;
  action?: ReactNode;
  help?: ReactNode;
}) {
  return (
    <PageHeader
      title={title}
      headingId={headingId}
      description={description}
      actions={action} help={help}
    />
  );
}

export function QueryError({
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
      {organizationErrorMessage(error, fallback)}
    </Notice>
  );
}

// The same failure, inside the results Panel that would have held the records.
export function PanelQueryError({
  error,
  fallback,
  onRetry,
}: {
  error: unknown;
  fallback: string;
  onRetry: () => void;
}) {
  return (
    <PanelMessage
      tone="danger"
      role="alert"
      action={<Button variant="secondary" onClick={onRetry}>Retry</Button>}
    >
      {organizationErrorMessage(error, fallback)}
    </PanelMessage>
  );
}

export function TableSkeleton({
  label = "Loading organization records…",
  framed = false,
}: {
  label?: string;
  framed?: boolean;
}) {
  return (
    <RowsSkeleton
      label={label}
      rows={5}
      framed={framed}
      className={framed ? "mt-5" : undefined}
    />
  );
}

export function replaceQueryParam(
  pathname: string,
  searchParams: URLSearchParams,
  key: string,
  value: string,
  resetPage = true,
): string {
  const next = new URLSearchParams(searchParams.toString());
  if (value) next.set(key, value);
  else next.delete(key);
  if (resetPage) next.delete("page");
  const query = next.toString();
  return query ? `${pathname}?${query}` : pathname;
}
