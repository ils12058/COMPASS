"use client";

import type { QueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useId, useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { LoadingRegion } from "@/components/ui/loading-region";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { StepUpDialog } from "@/features/account/security/security-shared";
import { GuardedPortalLink } from "@/features/form-safety/guarded-portal-link";
import { usePortalSession } from "@/features/portal/components/portal-session";
import {
  canManagePrivacyGovernance,
  canViewPrivacyGovernance,
} from "@/features/privacy-governance/privacy-governance-access";
import {
  isRecentMfaRequired,
  privacyErrorMessage,
  type PrivacyFieldLabels,
} from "@/features/privacy-governance/privacy-governance-errors";
import { revisionStatusLabels } from "@/features/privacy-governance/privacy-governance-presentation";
import type { RevisionStatusValue } from "@/lib/api/generated/model";
import { PageHeader, pageBackLinkClass } from "@/components/ui/page-header";
import { Notice } from "@/components/ui/notice";
import { PanelMessage, PanelSection } from "@/components/ui/panel";

export const PRIVACY_PAGE_SIZE = 20;

export const primaryLinkClass =
  "inline-flex min-h-10 items-center justify-center rounded-md border border-brand bg-brand px-4 py-2 text-sm font-semibold text-on-brand transition-colors hover:bg-brand-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2 focus-visible:ring-offset-body";

export const secondaryLinkClass =
  "inline-flex min-h-10 items-center justify-center rounded-md border border-border-strong bg-surface-raised px-4 py-2 text-sm font-semibold text-ink transition-colors hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2 focus-visible:ring-offset-body";

export const textLinkClass =
  "font-semibold text-brand underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus";

export function usePrivacyAccess() {
  const { user } = usePortalSession();
  return {
    canView: canViewPrivacyGovernance(user),
    canManage: canManagePrivacyGovernance(user),
  };
}

// Management mutations require recent MFA. Like other COMPASS workspaces, a
// step-up opens the shared verification dialog and the person submits again;
// the mutation is never replayed automatically.
export function usePrivacyAction(labels?: PrivacyFieldLabels) {
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [stepUpOpen, setStepUpOpen] = useState(false);

  async function run<T>(
    operation: () => Promise<T>,
    fallback: string,
    options?: {
      onStepUpRequired?: () => void;
      onError?: (caught: unknown) => void;
    },
  ): Promise<T | undefined> {
    setError(null);
    setNotice(null);
    try {
      return await operation();
    } catch (caught) {
      if (isRecentMfaRequired(caught)) {
        options?.onStepUpRequired?.();
        setNotice(
          "Recent authenticator verification is required. Verify, then submit the action again.",
        );
        setStepUpOpen(true);
      } else {
        setError(privacyErrorMessage(caught, fallback, labels));
        options?.onError?.(caught);
      }
      return undefined;
    }
  }

  function reset() {
    setError(null);
    setNotice(null);
  }

  const stepUpDialog = (
    <StepUpDialog
      open={stepUpOpen}
      onOpenChange={setStepUpOpen}
      onVerified={() =>
        setNotice("Verification complete. Submit the action again to continue.")
      }
    />
  );

  return { error, notice, setError, setNotice, reset, run, stepUpDialog };
}

export function ActionMessages({
  error,
  notice,
  className = "mt-4",
}: {
  error: string | null;
  notice: string | null;
  className?: string;
}) {
  if (!error && !notice) return null;
  return (
    <div className={className}>
      {error ? (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      ) : null}
      {notice ? (
        <p role="status" className="text-sm text-success">
          {notice}
        </p>
      ) : null}
    </div>
  );
}

export function PrivacyPageHeader({
  title,
  description,
  action,
  backHref,
  backLabel,
  context,
  meta,
}: {
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  backHref?: string;
  backLabel?: string;
  context?: ReactNode;
  meta?: ReactNode;
}) {
  return (
    <PageHeader
      title={title}
      context={context}
      description={description}
      actions={action}
      back={backHref ? (
        <GuardedPortalLink href={backHref} className={pageBackLinkClass}>
          ← {backLabel}
        </GuardedPortalLink>
      ) : undefined}
    >
      {meta ? (
        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-2 text-sm text-muted">
          {meta}
        </div>
      ) : null}
    </PageHeader>
  );
}

type BadgeTone = "success" | "info" | "warning" | "neutral";

const badgeTones: Record<BadgeTone, string> = {
  success: "border-success/30 bg-success/10 text-success",
  info: "border-info/30 bg-info/10 text-info",
  warning: "border-warning/30 bg-warning/10 text-warning",
  neutral: "border-border bg-surface-muted text-muted",
};

export function PrivacyBadge({
  tone,
  children,
}: {
  tone: BadgeTone;
  children: ReactNode;
}) {
  return (
    <span
      className={
        "inline-flex w-fit shrink-0 rounded-full border px-2 py-0.5 text-xs font-semibold " +
        badgeTones[tone]
      }
    >
      {children}
    </span>
  );
}

export function ActiveBadge({ active }: { active: boolean }) {
  return (
    <PrivacyBadge tone={active ? "success" : "neutral"}>
      {active ? "Active" : "Retired"}
    </PrivacyBadge>
  );
}

export function RevisionStatusBadge({ status }: { status: RevisionStatusValue }) {
  const tone: BadgeTone =
    status === "PUBLISHED" ? "success" : status === "DRAFT" ? "warning" : "neutral";
  return <PrivacyBadge tone={tone}>{revisionStatusLabels[status]}</PrivacyBadge>;
}

// Inside a results Panel the panel draws the frame; a route fallback frames itself.
export function PrivacyListSkeleton({
  rows = 5,
  label,
  framed = true,
}: {
  rows?: number;
  label: string;
  framed?: boolean;
}) {
  return (
    <LoadingRegion
      label={label}
      className={
        "divide-y divide-border" +
        (framed ? " rounded-sm border border-brand-line bg-surface-raised" : "")
      }
    >
      {Array.from({ length: rows }, (_, index) => (
        <div key={index} className="grid gap-2 px-4 py-4 sm:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_6rem] sm:items-center sm:gap-6 sm:px-5">
          <div>
            <Skeleton className="h-4 w-2/3 max-w-72" />
            <Skeleton className="mt-2 h-3 w-28" />
          </div>
          <Skeleton className="h-4 w-3/4 max-w-48" />
          <Skeleton className="h-5 w-16" />
        </div>
      ))}
    </LoadingRegion>
  );
}

export function PrivacyDetailSkeleton({ label }: { label: string }) {
  return (
    <LoadingRegion label={label} className="max-w-4xl">
      <Skeleton className="h-9 w-72 max-w-full" />
      <Skeleton className="mt-3 h-4 w-40" />
      <div className="mt-6 divide-y divide-brand-line rounded-sm border border-brand-line bg-surface-raised">
        {Array.from({ length: 4 }, (_, index) => (
          <div key={index} className="px-4 py-5 sm:px-5">
            <Skeleton className="h-4 w-40" />
            <Skeleton className="mt-3 h-14 w-full" />
          </div>
        ))}
      </div>
    </LoadingRegion>
  );
}

export function PrivacyQueryError({
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
      {privacyErrorMessage(error, fallback)}
    </Notice>
  );
}

export function PrivacyRecordUnavailable({
  title,
  error,
  fallback,
  backHref,
  backLabel,
  onRetry,
}: {
  title: string;
  error: unknown;
  fallback: string;
  backHref: string;
  backLabel: string;
  onRetry?: () => void;
}) {
  return (
    <section aria-labelledby="privacy-record-unavailable" className="max-w-2xl">
      <PageHeader title={title} headingId="privacy-record-unavailable" className="mb-5" />
      <Notice
        role="alert"
        action={
          <>
            {onRetry ? (
              <Button variant="secondary" onClick={onRetry}>
                Retry
              </Button>
            ) : null}
            <Link href={backHref} className={textLinkClass}>
              Back to {backLabel}
            </Link>
          </>
        }
      >
        {privacyErrorMessage(error, fallback)}
      </Notice>
    </section>
  );
}

export function DetailSection({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  const id = useId();
  return (
    <PanelSection title={title} titleId={id}>
      {children}
    </PanelSection>
  );
}

export function DetailValue({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-semibold text-muted">{label}</dt>
      <dd className="mt-1 break-words text-sm text-ink">{children}</dd>
    </div>
  );
}

export function CategoryList({ items }: { items: readonly string[] }) {
  if (items.length === 0) {
    return <p className="text-sm text-muted">None recorded.</p>;
  }
  return (
    <ul className="flex max-w-3xl flex-wrap gap-2">
      {items.map((item) => (
        <li
          key={item}
          className="rounded-md border border-border bg-surface-subtle px-2.5 py-1 text-sm text-ink"
        >
          {item}
        </li>
      ))}
    </ul>
  );
}

export function FormSection({
  title,
  description,
  children,
}: {
  title: string;
  description?: ReactNode;
  children: ReactNode;
}) {
  const id = useId();
  return (
    <PanelSection title={title} titleId={id} description={description}>
      <div className="grid gap-5">{children}</div>
    </PanelSection>
  );
}

export function FieldHint({ id, children }: { id?: string; children: ReactNode }) {
  return (
    <p id={id} className="text-xs leading-5 text-muted">
      {children}
    </p>
  );
}

export function PrivacyConfirmDialog({
  open,
  title,
  description,
  confirmLabel,
  pendingLabel,
  pending,
  error,
  confirmDisabled = false,
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
  confirmDisabled?: boolean;
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
      confirmDisabled={confirmDisabled}
      error={error}
      variant={destructive ? "danger" : "primary"}
      onOpenChange={onOpenChange}
      onConfirm={onConfirm}
    >
      {description}
    </ConsequentialActionDialog>
  );
}

export function useListSearchParams() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const page = (() => {
    const parsed = Number(searchParams.get("page"));
    return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : 1;
  })();

  function update(changes: Record<string, string | null>, resetPage = true) {
    const next = new URLSearchParams(searchParams.toString());
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    if (resetPage) next.delete("page");
    const query = next.toString();
    router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
  }

  function setPage(nextPage: number) {
    update({ page: nextPage > 1 ? String(nextPage) : null }, false);
  }

  return { searchParams, page, update, setPage };
}

export type LifecycleFilterValue = "active" | "retired" | "all";

export function lifecycleFilterFrom(value: string | null): LifecycleFilterValue {
  return value === "retired" || value === "all" ? value : "active";
}

export function lifecycleParams(filter: LifecycleFilterValue): { is_active?: boolean } {
  if (filter === "active") return { is_active: true };
  if (filter === "retired") return { is_active: false };
  return {};
}

export function LifecycleFilter({
  id,
  value,
  onChange,
}: {
  id: string;
  value: LifecycleFilterValue;
  onChange: (value: LifecycleFilterValue) => void;
}) {
  return (
    <div className="grid max-w-56 gap-1.5">
      <label htmlFor={id} className="text-sm font-medium text-ink">
        Status
      </label>
      <Select
        id={id}
        value={value}
        onChange={(event) => onChange(lifecycleFilterFrom(event.target.value))}
      >
        <option value="active">Active</option>
        <option value="retired">Retired</option>
        <option value="all">All</option>
      </Select>
    </div>
  );
}

export function EmptyListState({
  message,
  action,
}: {
  message: string;
  action?: ReactNode;
}) {
  return (
    <PanelMessage action={action ?? undefined}>{message}</PanelMessage>
  );
}

export const recordLinkClass =
  "font-semibold text-ink hover:text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus";

// Generated query keys start with the request path. Invalidating a retained
// record family keeps list/detail projections synchronized after mutations.
export function invalidatePrivacyRecords(queryClient: QueryClient, ...paths: string[]) {
  return queryClient.invalidateQueries({
    predicate: (query) => {
      const root = query.queryKey[0];
      return (
        typeof root === "string" &&
        paths.some((path) => root === path || root.startsWith(path + "/"))
      );
    },
  });
}

export const privacyPaths = {
  notices: "/api/v1/privacy/notices",
  noticeRevisions: "/api/v1/privacy/notice-revisions",
  myNotices: "/api/v1/privacy/my-notices",
  publicNotices: "/api/v1/privacy/public-notices",
  activity: "/api/v1/privacy/activity",
} as const;
