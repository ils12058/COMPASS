"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { LoadingRegion } from "@/components/ui/loading-region";
import { Skeleton } from "@/components/ui/skeleton";
import {
  publicationAudienceDescriptions,
  publicationAudienceLabels,
  publicationAudienceOrder,
  publicationStatusLabels,
  type PublicationAudience,
  type PublicationStatus,
} from "@/features/content/content-presentation";
import { PageHeader, pageBackLinkClass } from "@/components/ui/page-header";
import { Notice } from "@/components/ui/notice";

export const contentPrimaryLinkClass =
  "inline-flex min-h-10 items-center justify-center rounded-md border border-brand bg-brand px-4 py-2 text-sm font-semibold text-on-brand transition-colors hover:bg-brand-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2 focus-visible:ring-offset-body motion-reduce:transition-none";

export const contentSecondaryLinkClass =
  "inline-flex min-h-10 items-center justify-center rounded-md border border-border-strong bg-surface-raised px-4 py-2 text-sm font-semibold text-ink transition-colors hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2 focus-visible:ring-offset-body motion-reduce:transition-none";

export const contentRecordLinkClass =
  "font-semibold text-ink hover:text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus";

const statusTones: Record<PublicationStatus, string> = {
  DRAFT: "border-warning/40 bg-warning/5 text-warning",
  PUBLISHED: "border-success/40 bg-success/5 text-success",
  ARCHIVED: "border-border bg-surface-muted text-muted",
};

export function PublicationStatusBadge({ status }: { status: PublicationStatus }) {
  return (
    <span
      className={`inline-flex w-fit shrink-0 items-center rounded-md border px-2 py-0.5 text-xs font-semibold ${statusTones[status]}`}
    >
      {publicationStatusLabels[status]}
    </span>
  );
}

export function ContentPageHeading({
  title,
  headingId,
  backHref,
  backLabel,
  action,
  children,
}: {
  title: string;
  headingId?: string;
  backHref?: string;
  backLabel?: string;
  action?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <PageHeader
      title={title}
      headingId={headingId}
      actions={action}
      className="mb-0"
      back={backHref ? (
        <Link href={backHref} className={pageBackLinkClass}>
          ← {backLabel}
        </Link>
      ) : undefined}
    >
      {children}
    </PageHeader>
  );
}

export function ContentNotice({
  tone,
  children,
}: {
  tone: "success" | "warning" | "info";
  children: ReactNode;
}) {
  return (
    <Notice tone={tone} role="status">
      {children}
    </Notice>
  );
}

export function ContentQueryError({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <Notice
      tone="danger"
      role="alert"
      action={onRetry ? <Button variant="secondary" onClick={onRetry}>Retry</Button> : undefined}
    >
      {message}
    </Notice>
  );
}

// Rows inside a content results panel; the panel draws the frame.
export function ContentListSkeleton({ label, rows = 5 }: { label: string; rows?: number }) {
  return (
    <LoadingRegion label={label} className="divide-y divide-border">
      {Array.from({ length: rows }, (_, index) => (
        <div key={index} className="px-4 py-4 sm:px-5">
          <Skeleton className="h-5 w-2/3 max-w-96" />
          <Skeleton className="mt-2 h-4 w-48" />
        </div>
      ))}
    </LoadingRegion>
  );
}

export function ContentDetailSkeleton({ label }: { label: string }) {
  return (
    <LoadingRegion label={label} className="space-y-6">
      <Skeleton className="h-10 w-80 max-w-full" />
      <Skeleton className="h-24 w-full" />
      <Skeleton className="h-64 w-full" />
    </LoadingRegion>
  );
}

export function ContentConfirmDialog({
  open,
  title,
  description,
  confirmLabel,
  pendingLabel,
  pending,
  error,
  destructive = false,
  onOpenChange,
  onConfirm,
}: {
  open: boolean;
  title: string;
  description: ReactNode;
  confirmLabel: string;
  pendingLabel: string;
  pending: boolean;
  error: string | null;
  destructive?: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
}) {
  return (
    <ConsequentialActionDialog
      open={open}
      title={title}
      confirmLabel={confirmLabel}
      pendingLabel={pendingLabel}
      pending={pending}
      error={error}
      variant={destructive ? "danger" : "primary"}
      onOpenChange={onOpenChange}
      onConfirm={onConfirm}
    >
      {description}
    </ConsequentialActionDialog>
  );
}

export function AudienceField({
  name,
  value,
  onChange,
  error,
  hint,
}: {
  name: string;
  value: PublicationAudience | null;
  onChange: (value: PublicationAudience) => void;
  error?: string | null;
  hint?: ReactNode;
}) {
  const hintId = hint ? `${name}-hint` : undefined;
  const errorId = error ? `${name}-error` : undefined;
  return (
    <fieldset aria-describedby={[hintId, errorId].filter(Boolean).join(" ") || undefined}>
      <legend className="text-sm font-semibold text-ink">Audience</legend>
      {hint ? <p id={hintId} className="mt-1 text-xs leading-5 text-muted">{hint}</p> : null}
      {error ? <p id={errorId} className="mt-1 text-sm text-danger">{error}</p> : null}
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        {publicationAudienceOrder.map((audience) => {
          const id = `${name}-${audience.toLowerCase()}`;
          return (
            <label
              key={audience}
              htmlFor={id}
              className="flex cursor-pointer gap-3 rounded-md border border-border-strong bg-surface-raised px-3 py-3 has-[:checked]:border-brand has-[:checked]:bg-brand-wash has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-focus"
            >
              <input
                id={id}
                type="radio"
                name={name}
                value={audience}
                checked={value === audience}
                aria-labelledby={`${id}-label`}
                aria-describedby={`${id}-description`}
                onChange={() => onChange(audience)}
                className="mt-1 h-4 w-4 shrink-0 accent-brand focus-visible:outline-none"
              />
              <span>
                <span id={`${id}-label`} className="block text-sm font-semibold text-ink">
                  {publicationAudienceLabels[audience]}
                </span>
                <span id={`${id}-description`} className="mt-0.5 block text-xs leading-5 text-muted">
                  {publicationAudienceDescriptions[audience]}
                </span>
              </span>
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}
