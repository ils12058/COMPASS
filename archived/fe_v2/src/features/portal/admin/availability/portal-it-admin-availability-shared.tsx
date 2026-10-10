import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { getApiErrorMessage } from "@/features/auth/utils/errors";

export function availabilityAdminError(
  error: unknown,
  fallback = "We couldn’t complete that availability change. Please try again.",
) {
  return getApiErrorMessage(error) ?? fallback;
}

export function formatAvailabilityValue(value: string) {
  return value
    .toLowerCase()
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

export function formatAvailabilityTime(value: string) {
  const [hours, minutes] = value.split(":").map(Number);

  if (!Number.isFinite(hours) || !Number.isFinite(minutes)) {
    return value;
  }

  const date = new Date(2000, 0, 1, hours, minutes);
  return new Intl.DateTimeFormat("en-PH", {
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

export function formatAvailabilityDateTime(value: string) {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en-PH", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function AvailabilitySection({
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

export function AvailabilityActionMessage({
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

export function AvailabilityListSkeleton({
  label = "Loading availability",
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

export function AvailabilityQueryError({
  message = "We couldn’t load this availability information right now.",
  onRetry,
}: {
  message?: string;
  onRetry: () => void;
}) {
  return (
    <div className="rounded-2xl border border-dashed border-[var(--compass-border-strong)] bg-[var(--compass-surface-subtle)] p-6 text-center">
      <p role="alert" className="text-sm leading-6 text-muted-foreground">
        {message}
      </p>
      <Button className="mt-4" type="button" variant="outline" onClick={onRetry}>
        Try again
      </Button>
    </div>
  );
}

export function AvailabilityEmptyState({
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

export function AvailabilityManagementRequired() {
  return (
    <div className="rounded-2xl border border-[var(--compass-brand-gold)]/30 bg-[var(--compass-brand-gold)]/10 p-5">
      <p className="font-semibold text-[var(--compass-brand-maroon)]">
        Availability management access is required here.
      </p>
      <p className="mt-1 text-sm leading-6 text-muted-foreground">
        Your account can view some availability data, but changing office or provider settings is limited to authorized availability managers.
      </p>
    </div>
  );
}

export const availabilitySelectClassName =
  "h-10 w-full rounded-lg border border-input bg-card px-2.5 text-sm text-foreground outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50";

export function toDateTimeIso(value: string) {
  return new Date(value).toISOString();
}

export function toTimeInputValue(value: string) {
  return value.slice(0, 5);
}

export function toApiTimeValue(value: string) {
  return value.length === 5 ? `${value}:00` : value;
}

export function toDateInputValue(value: Date) {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}
