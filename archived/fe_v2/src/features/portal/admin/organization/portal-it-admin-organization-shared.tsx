import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { getApiErrorMessage } from "@/features/auth/utils/errors";

export function organizationAdminError(
  error: unknown,
  fallback = "We couldn’t complete that organization action. Please try again.",
) {
  return getApiErrorMessage(error) ?? fallback;
}

export function OrganizationStatusBadge({ active }: { active: boolean }) {
  return (
    <span
      className={
        active
          ? "inline-flex items-center rounded-full bg-[var(--compass-support-soft)] px-2.5 py-1 text-xs font-bold text-[var(--compass-support-strong)]"
          : "inline-flex items-center rounded-full bg-[var(--compass-brand-maroon)]/10 px-2.5 py-1 text-xs font-bold text-[var(--compass-brand-maroon)]"
      }
    >
      {active ? "Active" : "Disabled"}
    </span>
  );
}

export function OrganizationSection({
  children,
  description,
  icon: Icon,
  title,
}: {
  children: ReactNode;
  description: string;
  icon: LucideIcon;
  title: string;
}) {
  return (
    <section className="rounded-3xl border border-[var(--compass-border)] bg-card p-5 shadow-sm sm:p-7">
      <header className="flex items-start gap-3">
        <span className="flex size-10 shrink-0 items-center justify-center rounded-2xl bg-[var(--compass-support-soft)] text-[var(--compass-support-strong)]">
          <Icon aria-hidden="true" className="size-5" />
        </span>
        <div className="min-w-0">
          <h2 className="font-heading text-2xl font-bold tracking-tight">{title}</h2>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-muted-foreground">
            {description}
          </p>
        </div>
      </header>
      <div className="mt-6">{children}</div>
    </section>
  );
}

export function OrganizationActionMessage({
  error,
  message,
}: {
  error?: string | null;
  message?: string | null;
}) {
  if (!error && !message) {
    return null;
  }

  return (
    <Alert
      className={
        error
          ? "border-destructive/30 text-destructive"
          : "border-[var(--compass-support)]/30 text-[var(--compass-support-strong)]"
      }
      role={error ? "alert" : "status"}
    >
      <AlertDescription>{error ?? message}</AlertDescription>
    </Alert>
  );
}

export function OrganizationListSkeleton({
  label = "Loading organization records",
}: {
  label?: string;
}) {
  return (
    <div className="space-y-3" aria-live="polite" aria-label={label}>
      {Array.from({ length: 4 }, (_, index) => (
        <div
          key={index}
          className="h-24 animate-pulse rounded-2xl bg-muted"
          aria-hidden="true"
        />
      ))}
    </div>
  );
}

export function OrganizationQueryError({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="rounded-2xl border border-dashed border-[var(--compass-border-strong)] bg-[var(--compass-surface-subtle)] p-6 text-center">
      <p role="alert" className="text-sm leading-6 text-muted-foreground">
        We couldn’t load this part of the organization structure.
      </p>
      <Button className="mt-4" type="button" variant="outline" onClick={onRetry}>
        Try again
      </Button>
    </div>
  );
}

export function OrganizationEmptyState({
  action,
  description,
  title,
}: {
  action?: ReactNode;
  description: string;
  title: string;
}) {
  return (
    <div className="rounded-2xl border border-dashed border-[var(--compass-border-strong)] bg-[var(--compass-surface-subtle)] p-8 text-center">
      <h3 className="font-heading text-xl font-bold">{title}</h3>
      <p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-muted-foreground">
        {description}
      </p>
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}

export const organizationSelectClassName =
  "h-10 w-full rounded-lg border border-input bg-card px-2.5 text-sm text-foreground outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50";
