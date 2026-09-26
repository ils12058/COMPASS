"use client";

import type { QueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useId, useState, type KeyboardEvent, type ReactNode } from "react";

import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { StepUpDialog } from "@/features/account/security/security-shared";
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
import {
  incidentStatusLabels,
  reviewStatusLabels,
  revisionStatusLabels,
} from "@/features/privacy-governance/privacy-governance-presentation";
import type {
  IncidentStatusValue,
  ReviewStatusValue,
  RevisionStatusValue,
} from "@/lib/api/generated/model";

export const PRIVACY_PAGE_SIZE = 20;

export const privacySelectClass =
  "min-h-10 w-full rounded-md border border-border bg-surface-raised px-3 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus";

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
    <header className="mb-7">
      {backHref ? (
        <Link
          href={backHref}
          className="mb-4 inline-flex min-h-10 items-center text-sm font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
        >
          ← {backLabel}
        </Link>
      ) : null}
      {context ? <p className="text-sm font-medium text-muted">{context}</p> : null}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <h1 className="min-w-0 break-words font-heading text-3xl font-bold text-ink">
          {title}
        </h1>
        {action ? <div className="flex flex-wrap gap-2">{action}</div> : null}
      </div>
      {meta ? (
        <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2 text-sm text-muted">
          {meta}
        </div>
      ) : null}
      {description ? (
        <p className="mt-3 max-w-3xl text-sm leading-6 text-muted">{description}</p>
      ) : null}
    </header>
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

export function ReviewStatusBadge({ status }: { status: ReviewStatusValue }) {
  return (
    <PrivacyBadge tone={status === "OPEN" ? "info" : "neutral"}>
      {reviewStatusLabels[status]}
    </PrivacyBadge>
  );
}

export function RevisionStatusBadge({ status }: { status: RevisionStatusValue }) {
  const tone: BadgeTone =
    status === "PUBLISHED" ? "success" : status === "DRAFT" ? "warning" : "neutral";
  return <PrivacyBadge tone={tone}>{revisionStatusLabels[status]}</PrivacyBadge>;
}

export function IncidentStatusBadge({ status }: { status: IncidentStatusValue }) {
  const tone: BadgeTone =
    status === "RESOLVED" ? "neutral" : status === "OPEN" ? "warning" : "info";
  return <PrivacyBadge tone={tone}>{incidentStatusLabels[status]}</PrivacyBadge>;
}

export function PrivacyListSkeleton({ rows = 5, label }: { rows?: number; label: string }) {
  return (
    <div aria-busy="true" className="divide-y divide-border border-y border-border">
      {Array.from({ length: rows }, (_, index) => (
        <div key={index} className="grid gap-2 py-4 sm:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_6rem] sm:items-center sm:gap-6">
          <div>
            <Skeleton className="h-4 w-2/3 max-w-72" />
            <Skeleton className="mt-2 h-3 w-28" />
          </div>
          <Skeleton className="h-4 w-3/4 max-w-48" />
          <Skeleton className="h-5 w-16" />
        </div>
      ))}
      <p className="sr-only">{label}</p>
    </div>
  );
}

export function PrivacyDetailSkeleton({ label }: { label: string }) {
  return (
    <div aria-busy="true" className="max-w-4xl">
      <Skeleton className="h-10 w-72 max-w-full" />
      <Skeleton className="mt-4 h-4 w-40" />
      <div className="mt-10 space-y-8">
        {Array.from({ length: 4 }, (_, index) => (
          <div key={index}>
            <Skeleton className="h-5 w-48" />
            <Skeleton className="mt-3 h-16 w-full" />
          </div>
        ))}
      </div>
      <p className="sr-only">{label}</p>
    </div>
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
    <div role="alert" className="border-y border-border py-6">
      <p className="text-sm text-danger">{privacyErrorMessage(error, fallback)}</p>
      <Button variant="secondary" className="mt-4" onClick={onRetry}>
        Retry
      </Button>
    </div>
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
      <h1
        id="privacy-record-unavailable"
        className="font-heading text-3xl font-bold text-ink"
      >
        {title}
      </h1>
      <p role="alert" className="mt-3 text-sm leading-6 text-muted">
        {privacyErrorMessage(error, fallback)}
      </p>
      <div className="mt-5 flex flex-wrap items-center gap-4">
        {onRetry ? (
          <Button variant="secondary" onClick={onRetry}>
            Retry
          </Button>
        ) : null}
        <Link href={backHref} className={textLinkClass}>
          Back to {backLabel}
        </Link>
      </div>
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
    <section aria-labelledby={id} className="py-6">
      <h2 id={id} className="font-heading text-lg font-semibold text-ink">
        {title}
      </h2>
      <div className="mt-2">{children}</div>
    </section>
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

const MAX_CATEGORY_ITEMS = 32;
const MAX_CATEGORY_LENGTH = 80;

export function CategoryInput({
  id,
  label,
  hint,
  values,
  onChange,
}: {
  id: string;
  label: string;
  hint?: string;
  values: string[];
  onChange: (values: string[]) => void;
}) {
  const [draft, setDraft] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const hintId = `${id}-hint`;
  const messageId = `${id}-message`;
  const full = values.length >= MAX_CATEGORY_ITEMS;

  function add() {
    const value = draft.trim();
    if (!value) return;
    if (values.some((item) => item.toLocaleLowerCase() === value.toLocaleLowerCase())) {
      setMessage(`"${value}" is already listed.`);
      return;
    }
    onChange([...values, value]);
    setDraft("");
    setMessage(null);
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") {
      event.preventDefault();
      add();
    }
  }

  return (
    <fieldset className="grid gap-2">
      <legend className="text-sm font-medium text-ink">{label}</legend>
      {hint ? (
        <p id={hintId} className="text-xs leading-5 text-muted">
          {hint}
        </p>
      ) : null}
      {values.length > 0 ? (
        <ul className="flex flex-wrap gap-2" aria-label={label}>
          {values.map((item) => (
            <li
              key={item}
              className="inline-flex items-center gap-1 rounded-md border border-border bg-surface-subtle py-0.5 pl-2.5 pr-1 text-sm text-ink"
            >
              <span className="break-all">{item}</span>
              <button
                type="button"
                className="inline-flex min-h-8 min-w-8 items-center justify-center rounded-sm text-muted hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                onClick={() => onChange(values.filter((value) => value !== item))}
              >
                <span aria-hidden="true">×</span>
                <span className="sr-only">Remove {item}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      <div className="flex max-w-xl gap-2">
        <Input
          id={id}
          value={draft}
          maxLength={MAX_CATEGORY_LENGTH}
          disabled={full}
          aria-describedby={[hint ? hintId : null, message ? messageId : null]
            .filter(Boolean)
            .join(" ") || undefined}
          onChange={(event) => {
            setDraft(event.target.value);
            setMessage(null);
          }}
          onKeyDown={onKeyDown}
        />
        <Button
          type="button"
          variant="secondary"
          disabled={full || !draft.trim()}
          onClick={add}
        >
          Add
        </Button>
      </div>
      {message ? (
        <p id={messageId} role="status" className="text-xs text-muted">
          {message}
        </p>
      ) : null}
      {full ? (
        <p className="text-xs text-muted">
          {MAX_CATEGORY_ITEMS} entries is the maximum. Remove one to add another.
        </p>
      ) : null}
    </fieldset>
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
    <section
      aria-labelledby={id}
      className="border-t border-border pt-7 first:border-t-0 first:pt-0"
    >
      <h2 id={id} className="font-heading text-xl font-semibold text-ink">
        {title}
      </h2>
      {description ? (
        <p className="mt-1 max-w-3xl text-sm leading-6 text-muted">{description}</p>
      ) : null}
      <div className="mt-4 grid gap-5">{children}</div>
    </section>
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
  children,
  confirmLabel,
  pendingLabel,
  pending,
  error,
  destructive = false,
  confirmDisabled = false,
  onOpenChange,
  onConfirm,
}: {
  open: boolean;
  title: string;
  description: ReactNode;
  children?: ReactNode;
  confirmLabel: string;
  pendingLabel: string;
  pending: boolean;
  error: string | null;
  destructive?: boolean;
  confirmDisabled?: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
}) {
  return (
    <AlertDialog
      open={open}
      onOpenChange={(next) => {
        if (pending) return;
        onOpenChange(next);
      }}
    >
      <AlertDialogContent>
        <AlertDialogTitle>{title}</AlertDialogTitle>
        <AlertDialogDescription asChild>
          <div className="mt-2 space-y-2 text-sm leading-6 text-muted">{description}</div>
        </AlertDialogDescription>
        {children}
        {error ? (
          <p role="alert" className="mt-4 text-sm text-danger">
            {error}
          </p>
        ) : null}
        <div className="mt-6 flex flex-wrap justify-end gap-2">
          <AlertDialogCancel asChild>
            <Button variant="secondary" disabled={pending}>
              Cancel
            </Button>
          </AlertDialogCancel>
          <Button
            variant={destructive ? "danger" : "primary"}
            disabled={pending || confirmDisabled}
            onClick={onConfirm}
          >
            {pending ? pendingLabel : confirmLabel}
          </Button>
        </div>
      </AlertDialogContent>
    </AlertDialog>
  );
}

// Keeps list filters and the page number in the URL so they survive
// navigation to a record and back.
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
    <div className="grid max-w-56 gap-2">
      <label htmlFor={id} className="text-sm font-medium text-ink">
        Status
      </label>
      <select
        id={id}
        className={privacySelectClass}
        value={value}
        onChange={(event) => onChange(lifecycleFilterFrom(event.target.value))}
      >
        <option value="active">Active</option>
        <option value="retired">Retired</option>
        <option value="all">All</option>
      </select>
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
    <div className="mt-5 border-y border-border py-8">
      <p className="text-sm text-muted">{message}</p>
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}

export function RefreshingNotice({ show, label }: { show: boolean; label: string }) {
  return show ? (
    <p role="status" className="mt-4 text-xs text-muted">
      {label}
    </p>
  ) : null;
}

export const tableHeadClass = "bg-surface-muted text-xs text-muted";
export const tableHeaderCellClass = "px-3 py-3 font-semibold";
export const tableCellClass = "px-3 py-4 align-top";
export const tableRowHeaderClass = "px-3 py-4 text-left align-top font-normal";
export const recordLinkClass =
  "font-semibold text-ink hover:text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus";

// Generated query keys start with the request path. Invalidating a record
// family (list, details, and nested lists) keeps embedded summaries such as a
// Retention Policy name on Processing Activities current after a change.
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
  processingActivities: "/api/v1/privacy/processing-activities",
  reviews: "/api/v1/privacy/reviews",
  retentionPolicies: "/api/v1/privacy/retention-policies",
  notices: "/api/v1/privacy/notices",
  noticeRevisions: "/api/v1/privacy/notice-revisions",
  myNotices: "/api/v1/privacy/my-notices",
  publicNotices: "/api/v1/privacy/public-notices",
  incidents: "/api/v1/privacy/incidents",
  activity: "/api/v1/privacy/activity",
} as const;
